"""The daemon: the desk's cadence, run by a clock instead of by memory.

`docs/MIGRATION.md` had the schedule as a table nobody enforced. Nothing
retried a failed preflight, nothing said a session had been skipped, and
nothing told Max a ticket had cleared while he was away from the pack. This
runs `codex-feed/CADENCE.yaml`, writes every session's outputs to disk, and
pushes on the handful of conditions that need him.

It never fetches on a seat's behalf and never confirms. It stamps, packs,
assigns, probes, and watches for change.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from .assign import build_assignment, render_assignment
from .challenge import load_challenges, unchallenged
from .confirm import load_confirms, usable
from .loader import DeskError, FieldSpec, ValidationError, check_fields, load_document
from .mode import load_mode
from .notify import Dedup, Push, deliver
from .report import load_reports, seats_reporting
from .risk import PASS, Book, stamp_book
from .roster import load_roster
from .sources import load_sources, probe_all, write_report
from .ticket import load_tickets

STEPS = ("preflight", "assign", "challenge", "stamp", "pack", "expire", "validate")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class Slot:
    id: str
    days: tuple[str, ...]
    at: str          # "HH:MM"
    steps: tuple[str, ...]

    def next_after(self, now: datetime, tz: ZoneInfo) -> datetime:
        """The next instant this slot fires, strictly after `now`."""
        local = now.astimezone(tz)
        hour, minute = (int(x) for x in self.at.split(":"))
        for offset in range(0, 8):
            day = (local + timedelta(days=offset)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if DAYS[day.weekday()] in self.days and day > local:
                return day.astimezone(timezone.utc)
        raise RuntimeError(f"slot {self.id} never fires")


@dataclass(frozen=True)
class Cadence:
    timezone: ZoneInfo
    slots: tuple[Slot, ...]
    cooldown: timedelta
    seat_grace: timedelta

    def next_slot(self, now: datetime) -> tuple[Slot, datetime]:
        best: tuple[Slot, datetime] | None = None
        for slot in self.slots:
            when = slot.next_after(now, self.timezone)
            if best is None or when < best[1]:
                best = (slot, when)
        if best is None:
            raise RuntimeError("cadence has no slots")
        return best

    def slot(self, slot_id: str) -> Slot:
        for slot in self.slots:
            if slot.id == slot_id:
                return slot
        raise KeyError(slot_id)


_SPECS = (
    FieldSpec("schema_version", int, minimum=1, maximum=1),
    FieldSpec("timezone", str),
    FieldSpec("slots", list, item_kind=dict, min_items=1),
    FieldSpec("push", dict, required=False),
)


def parse_cadence(doc: Mapping[str, Any], *, where: str = "cadence") -> Cadence:
    problems = check_fields(doc, _SPECS, where=where)
    if problems:
        raise ValidationError(problems, where=where)
    try:
        tz = ZoneInfo(doc["timezone"])
    except Exception as exc:  # pragma: no cover - zoneinfo error types vary
        raise ValidationError([f"timezone: {doc['timezone']!r} unknown ({exc})"], where=where)

    extra: list[str] = []
    slots: list[Slot] = []
    for i, item in enumerate(doc["slots"]):
        sid = str(item.get("id", f"slot[{i}]"))
        days = tuple(str(d).lower() for d in (item.get("days") or ()))
        bad_days = [d for d in days if d not in DAYS]
        if bad_days or not days:
            extra.append(f"{sid}: days must be from {list(DAYS)}, got {list(days)}")
        at = str(item.get("at", ""))
        try:
            h, m = (int(x) for x in at.split(":"))
            assert 0 <= h < 24 and 0 <= m < 60
        except (ValueError, AssertionError):
            extra.append(f"{sid}: at must be HH:MM, got {at!r}")
        steps = tuple(str(s) for s in (item.get("steps") or ()))
        unknown = [s for s in steps if s not in STEPS]
        if unknown or not steps:
            extra.append(f"{sid}: steps must be from {list(STEPS)}, got {list(steps)}")
        if "fetch" in steps or "confirm" in steps:
            extra.append(f"{sid}: the daemon never fetches for a seat or confirms for Max")
        slots.append(Slot(id=sid, days=days, at=at, steps=steps))
    ids = [s.id for s in slots]
    if len(set(ids)) != len(ids):
        extra.append("slots: duplicate ids")
    if extra:
        raise ValidationError(extra, where=where)

    push = doc.get("push") or {}
    return Cadence(
        timezone=tz,
        slots=tuple(slots),
        cooldown=timedelta(hours=float(push.get("cooldown_hours", 4))),
        seat_grace=timedelta(minutes=float(push.get("required_seat_grace_minutes", 15))),
    )


def load_cadence(path: str | Path) -> Cadence:
    return parse_cadence(load_document(path), where=str(path))


@dataclass
class Paths:
    """Where the daemon reads and writes. All under one root."""

    root: Path

    @property
    def mode(self) -> Path: return self.root / "codex-feed" / "MODE.yaml"
    @property
    def roster(self) -> Path: return self.root / "codex-feed" / "ROSTER.yaml"
    @property
    def sources(self) -> Path: return self.root / "codex-feed" / "sources.yaml"
    @property
    def cadence(self) -> Path: return self.root / "codex-feed" / "CADENCE.yaml"
    @property
    def tickets(self) -> Path: return self.root / "tickets"
    @property
    def challenges(self) -> Path: return self.root / "challenges"
    @property
    def reports(self) -> Path: return self.root / "reports"
    @property
    def assignments(self) -> Path: return self.root / "assignments"
    @property
    def confirmations(self) -> Path: return self.root / "confirmations"
    @property
    def preflight(self) -> Path: return self.root / "preflight"
    @property
    def stamps(self) -> Path: return self.root / "stamps"
    @property
    def packs(self) -> Path: return self.root / "packs"
    @property
    def state(self) -> Path: return self.root / "state"
    @property
    def log(self) -> Path: return self.state / "daemon.log"
    @property
    def dedup(self) -> Path: return self.state / "push.json"
    @property
    def last_stamp(self) -> Path: return self.state / "last-stamp.json"


@dataclass
class SessionResult:
    slot: str
    started_at: datetime
    steps: list[tuple[str, str]] = field(default_factory=list)   # (step, outcome)
    pushes: list[tuple[Push, str]] = field(default_factory=list)
    book: Book | None = None

    @property
    def ok(self) -> bool:
        return all(not o.startswith("failed") for _, o in self.steps)


def run_slot(
    slot: Slot,
    paths: Paths,
    cadence: Cadence,
    *,
    now: datetime,
    dry_run_push: bool = False,
    probe: Callable[..., Any] | None = None,
) -> SessionResult:
    """Run one slot's steps. Every step writes something or says why not."""
    result = SessionResult(slot=slot.id, started_at=now)
    pushes: list[Push] = []
    # Loading is a step too. A ticket the contract refuses must not take the
    # whole session down silently — that is the skipped-session failure this
    # daemon exists to remove. It logs, pushes, and returns a failed result.
    try:
        mode = load_mode(paths.mode)
        tickets = load_tickets(paths.tickets) if paths.tickets.exists() else []
        reports = load_reports(paths.reports)
        challenges = load_challenges(paths.challenges)
        if paths.roster.exists():
            roster = load_roster(paths.roster)
            challenges, _ = roster.independent_challenges(tickets, challenges)
    except (DeskError, OSError) as exc:
        result.steps.append(("load", f"failed: {exc}"))
        dedup = Dedup(paths.dedup, cooldown=cadence.cooldown)
        result.pushes = deliver(
            [Push(key=f"step-failed:{slot.id}:load", title=f"{slot.id}: book failed to load",
                  message=str(exc)[:300], priority="high")],
            dedup, now=now, dry_run=dry_run_push,
        )
        _log(paths, result)
        return result

    for step in slot.steps:
        try:
            if step == "preflight":
                sources = load_sources(paths.sources)
                health = (probe or probe_all)(sources)
                path = write_report(health, paths.preflight / f"{now:%Y-%m-%d-%H%M}.json")
                dark = [h for h in health if h.state in ("unreachable", "no_auth")]
                for h in dark:
                    pushes.append(Push(
                        key=f"source:{h.source_id}:{h.state}",
                        title=f"{h.source_id} {h.state}",
                        message=h.detail or "no detail",
                        priority="high" if h.state == "unreachable" else "default",
                    ))
                result.steps.append((step, f"wrote {path.name}; {len(dark)} dark"))
            elif step == "assign":
                assignment = build_assignment(
                    "Grok", tickets, mode, now=now, prior=reports.get("Grok")
                )
                if assignment.tasks:
                    path = paths.assignments / f"{now:%Y-%m-%d}-grok.assignment.yaml"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(render_assignment(assignment), encoding="utf-8")
                    result.steps.append((step, f"wrote {path.name}; {len(assignment.tasks)} tasks"))
                else:
                    result.steps.append((step, "nothing to assign"))
            elif step == "challenge":
                pending = unchallenged([t.id for t in tickets], challenges)
                result.steps.append((step, f"{len(pending)} awaiting Jev"))
                for ticket_id in pending:
                    ticket = next(t for t in tickets if t.id == ticket_id)
                    if now - ticket.created_at > timedelta(hours=12):
                        pushes.append(Push(
                            key=f"unchallenged:{ticket_id}",
                            title=f"{ticket_id} unchallenged 12h+",
                            message="No model has argued against it; it carries no size until one does.",
                        ))
            elif step == "stamp":
                book = stamp_book(
                    tickets, mode, now=now, challenges=challenges,
                    available_seats=seats_reporting(reports) or None,
                )
                result.book = book
                payload = _book_payload(book)
                paths.stamps.mkdir(parents=True, exist_ok=True)
                (paths.stamps / f"{now:%Y-%m-%d-%H%M}.json").write_text(
                    json.dumps(payload, indent=2), encoding="utf-8"
                )
                pushes.extend(_stamp_pushes(book, paths, now=now))
                paths.state.mkdir(parents=True, exist_ok=True)
                paths.last_stamp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                # Required seats late past grace
                for seat in mode.required_seats:
                    if seat not in seats_reporting(reports):
                        pushes.append(Push(
                            key=f"seat-dark:{seat}",
                            title=f"{seat} has not filed",
                            message=f"Required seat dark at {slot.id}; the book stays PENDING on it.",
                            priority="high",
                        ))
                result.steps.append((step, f"allocated {book.portfolio_allowed_pct:.2f}%"))
            elif step == "pack":
                from .cli import render_pack  # late import: cli imports this module

                text = render_pack(mode, tickets, reports, challenges, now=now)
                paths.packs.mkdir(parents=True, exist_ok=True)
                path = paths.packs / f"{now:%Y-%m-%d-%H%M}.md"
                path.write_text(text, encoding="utf-8")
                result.steps.append((step, f"wrote {path.name}"))
            elif step == "expire":
                if result.book is None:
                    result.book = stamp_book(tickets, mode, now=now, challenges=challenges,
                                             available_seats=seats_reporting(reports) or None)
                confirms = load_confirms(paths.confirmations)
                good, bad = usable(confirms, result.book, now=now)
                result.steps.append((step, f"{len(good)} usable, {len(bad)} void"))
            elif step == "validate":
                problems: list[str] = []
                for ticket in tickets:
                    if mode.theme_by_id(ticket.theme) is None:
                        problems.append(f"{ticket.id}: theme {ticket.theme!r} undefined")
                result.steps.append((step, "ok" if not problems else f"{len(problems)} problems"))
        except (DeskError, OSError) as exc:
            result.steps.append((step, f"failed: {exc}"))
            pushes.append(Push(
                key=f"step-failed:{slot.id}:{step}",
                title=f"{slot.id}: {step} failed",
                message=str(exc)[:300],
                priority="high",
            ))
            break

    dedup = Dedup(paths.dedup, cooldown=cadence.cooldown)
    result.pushes = deliver(pushes, dedup, now=now, dry_run=dry_run_push)
    _log(paths, result)
    return result


def _stamp_pushes(book: Book, paths: Paths, *, now: datetime) -> list[Push]:
    """What changed since the last stamp that Max should hear about."""
    previous: dict[str, dict[str, Any]] = {}
    if paths.last_stamp.exists():
        try:
            raw = json.loads(paths.last_stamp.read_text(encoding="utf-8"))
            previous = {s["ticket_id"]: s for s in raw.get("stamps", [])}
        except (ValueError, OSError, KeyError):
            previous = {}
    out: list[Push] = []
    for stamp in book.stamps:
        before = previous.get(stamp.ticket_id, {})
        was_pass = before.get("verdict") == PASS and float(before.get("allowed_pct", 0)) > 0
        is_pass = stamp.verdict == PASS and stamp.allowed_pct > 0
        if is_pass and not was_pass:
            out.append(Push(
                key=f"cleared:{stamp.ticket_id}:{stamp.allowed_pct:.2f}",
                title=f"{stamp.ticket_id} cleared — {stamp.allowed_pct:.2f}% ceiling",
                message=f"{stamp.binding_constraint}. Confirm?",
                priority="high",
            ))
        if stamp.challenge_verdict == "kill" and before.get("challenge_verdict") != "kill":
            out.append(Push(
                key=f"killed:{stamp.ticket_id}",
                title=f"{stamp.ticket_id} killed by Jev",
                message=(stamp.reasons[0] if stamp.reasons else "kill on record")[:200],
            ))
    # A confirmed ticket whose digest changed is a void confirm.
    confirms = load_confirms(paths.confirmations)
    _, bad = usable(confirms, book, now=now)
    for line in bad:
        if "book moved" in line:
            ticket_id = line.split(":", 1)[0]
            out.append(Push(
                key=f"confirm-void:{ticket_id}",
                title=f"{ticket_id} re-stamped — confirm void",
                message="The book moved since you confirmed. Re-confirm if it still stands.",
                priority="high",
            ))
    return out


def _book_payload(book: Book) -> dict[str, Any]:
    from .confirm import stamp_digest

    return {
        "stamped_at": book.stamped_at.isoformat(),
        "mode": book.mode,
        "execution": book.execution,
        "portfolio_allowed_pct": round(book.portfolio_allowed_pct, 2),
        "portfolio_cap_pct": book.portfolio_cap_pct,
        "stamps": [
            {
                "ticket_id": s.ticket_id,
                "verdict": s.verdict,
                "requested_pct": s.requested_pct,
                "allowed_pct": s.allowed_pct,
                "theme": s.theme,
                "binding_constraint": s.binding_constraint,
                "challenge_verdict": s.challenge_verdict,
                "effective_confidence": s.effective_confidence,
                "reasons": s.reasons,
                "stale_evidence": s.stale_evidence,
                "missing_seats": s.missing_seats,
                "stamp_sha256": stamp_digest(s, book),
            }
            for s in book.ranked()
        ],
    }


def _log(paths: Paths, result: SessionResult) -> None:
    paths.state.mkdir(parents=True, exist_ok=True)
    lines = [f"[{result.started_at:%Y-%m-%dT%H:%M:%SZ}] slot={result.slot} ok={result.ok}"]
    for step, outcome in result.steps:
        lines.append(f"  {step}: {outcome}")
    for push, outcome in result.pushes:
        lines.append(f"  push[{push.key}]: {outcome}")
    with paths.log.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def run_forever(
    paths: Paths,
    *,
    dry_run_push: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    max_sessions: int | None = None,
) -> int:
    """Sleep until the next slot, run it, repeat. Returns sessions run."""
    cadence = load_cadence(paths.cadence)
    ran = 0
    while max_sessions is None or ran < max_sessions:
        now = clock()
        slot, when = cadence.next_slot(now)
        wait = (when - now).total_seconds()
        if wait > 0:
            sleep(wait)
        run_slot(slot, paths, cadence, now=clock(), dry_run_push=dry_run_push)
        ran += 1
    return ran
