"""Assignments: how the desk tells a research seat what to work on.

Every other seat on this desk is pointed at something. Odds has a market
slug, Shadow has a CIK, Ledger has a series. Grok had a standing brief and
its own judgement about what mattered today — which is the one arrangement
guaranteed to drift, because a social seat left to choose its own subjects
will choose whatever is loudest, and whatever is loudest is what the desk
least needs a second opinion on.

So the desk issues the work order. An assignment is derived from live state:
the open book, the caps that apply to it, and what the seat has already
answered recently. It is a contract file like a ticket or a challenge, which
means it can be validated, diffed, and audited against what came back.

Two task kinds, both mechanically derivable from the book:

    crowding   Is this name already known? One per symbol carrying risk.
    catalyst   Is this scheduled catalyst being discussed at all?

Nothing here asks the seat for an opinion on direction. An assignment is a
question, and the answer is evidence — the seat still never originates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .loader import FieldSpec, ValidationError, check_fields, load_document, parse_instant
from .mode import Mode
from .report import SeatReport
from .ticket import Ticket

TASK_KINDS = ("crowding", "catalyst")

# The evidence kind an assignment's answer will arrive as, and therefore the
# freshness budget it inherits from MODE.yaml.
ANSWER_KIND = "social"


@dataclass(frozen=True)
class Task:
    """One question the desk wants answered, and what it is worth."""

    task_id: str
    kind: str
    subject: str
    ticket_id: str
    why: str
    at_stake_pct: float
    max_age_hours: float
    theme: str = ""
    answer_by: datetime | None = None

    def line(self) -> str:
        due = f" by {self.answer_by:%Y-%m-%d %H:%MZ}" if self.answer_by else ""
        return (
            f"{self.task_id:<22} {self.kind:<9} {self.subject:<28} "
            f"{self.at_stake_pct:>5.2f}%{due}"
        )


@dataclass(frozen=True)
class Assignment:
    """One seat's work order for one session."""

    seat: str
    issued_at: datetime
    tasks: tuple[Task, ...]
    note: str = ""
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def subjects(self, kind: str | None = None) -> tuple[str, ...]:
        return tuple(t.subject for t in self.tasks if kind is None or t.kind == kind)

    def task_for(self, subject: str, kind: str) -> Task | None:
        needle = subject.strip().lower()
        for task in self.tasks:
            if task.kind == kind and task.subject.strip().lower() == needle:
                return task
        return None

    @property
    def at_stake_pct(self) -> float:
        """Total risk waiting on this assignment, counted once per theme.

        Summing the per-name figures would report 4.5% for three legs sharing
        one 1.5% theme cap — the exact double-count the risk engine exists to
        prevent, and it would be odd to reintroduce it in the module that
        tells a seat where to look. Correlated legs share a ceiling, so the
        ceiling is counted once.

        Crowding tasks only: a catalyst task rides the same ticket's risk as
        the crowding task on that name.
        """
        by_theme: dict[str, float] = {}
        for task in self.tasks:
            if task.kind != "crowding":
                continue
            key = task.theme or f"(untagged:{task.subject})"
            by_theme[key] = max(by_theme.get(key, 0.0), task.at_stake_pct)
        return sum(by_theme.values())


@dataclass(frozen=True)
class Coverage:
    """What came back against what was asked.

    `unsolicited` is not a failure — a seat noticing something the desk did not
    think to ask about is the upside of having a seat rather than a script. It
    is counted because a seat that answers nothing it was asked and volunteers
    plenty is the drift this whole mechanism exists to catch.
    """

    seat: str
    answered: tuple[str, ...]
    unanswered: tuple[str, ...]
    stale: tuple[str, ...]
    unsolicited: tuple[str, ...]
    assigned: int

    @property
    def answer_rate(self) -> float | None:
        return len(self.answered) / self.assigned if self.assigned else None

    @property
    def complete(self) -> bool:
        return not self.unanswered and not self.stale

    def lines(self) -> list[str]:
        out: list[str] = []
        rate = self.answer_rate
        shown = "  -  " if rate is None else f"{rate:.0%}"
        out.append(
            f"{self.seat}: answered {len(self.answered)}/{self.assigned} ({shown})"
        )
        if self.unanswered:
            out.append(f"  unanswered: {', '.join(self.unanswered)}")
        if self.stale:
            out.append(
                f"  answered but stale: {', '.join(self.stale)} — past the freshness "
                "budget, so the engine will refuse a ticket leaning on it"
            )
        if self.unsolicited:
            out.append(
                f"  unsolicited: {', '.join(self.unsolicited)} — not asked for; "
                "fine in itself, drift if it replaces the asks"
            )
        return out


def build_assignment(
    seat: str,
    tickets: Sequence[Ticket],
    mode: Mode,
    *,
    now: datetime,
    prior: SeatReport | None = None,
    note: str = "",
) -> Assignment:
    """Derive a work order from the open book.

    Priority is the risk a name could *earn* — its theme cap taken down by the
    conviction ladder — not the risk it declared. The declared hint is the
    wrong signal and running this proved it: four of the five tickets in the
    book declare `size_hint_pct: 0.0`, meaning "Rails, you size it", which
    sorted exactly the tickets most in need of a crowding read to the bottom.
    A declared hint still caps the figure when there is one; a ticket asking
    for 0.25% does not become a 1.5% priority.

    This deliberately stops short of a Rails allowance, which would need a
    seat report to exist — and this is the thing that asks for one.
    """
    budget = mode.max_age(ANSWER_KIND) or timedelta(hours=72)
    hours = budget.total_seconds() / 3600.0
    fresh_since = now - budget

    tasks: list[Task] = []
    seen: set[tuple[str, str]] = set()

    for ticket in sorted(
        tickets, key=lambda t: -_at_stake(t, mode.cap_for_theme(t.theme))
    ):
        symbol = ticket.instrument.symbol
        cap = mode.cap_for_theme(ticket.theme)
        at_stake = _at_stake(ticket, cap)

        key = ("crowding", symbol.lower())
        if key not in seen and not _answered_fresh(prior, symbol, fresh_since):
            seen.add(key)
            tasks.append(
                Task(
                    task_id=f"{ticket.id}:crowding",
                    kind="crowding",
                    subject=symbol,
                    ticket_id=ticket.id,
                    why=(
                        f"{ticket.direction} {symbol} under {ticket.theme or 'no theme'} "
                        f"(shared cap {cap:.2f}%, up to {at_stake:.2f}% at stake "
                        f"here) — is it already known?"
                    ),
                    at_stake_pct=at_stake,
                    max_age_hours=hours,
                    theme=ticket.theme,
                    answer_by=_deadline(ticket, now),
                )
            )

        # Absence of chatter around a dated catalyst is weak evidence, and the
        # brief says to label it weak. It is still the cheapest check the seat
        # can run, and a catalyst nobody has noticed may not be priced.
        if ticket.catalyst_at and ticket.catalyst_at > now:
            label = _gist(ticket.catalyst)
            ckey = ("catalyst", label.lower())
            if ckey not in seen:
                seen.add(ckey)
                tasks.append(
                    Task(
                        task_id=f"{ticket.id}:catalyst",
                        kind="catalyst",
                        subject=label,
                        ticket_id=ticket.id,
                        why=(
                            f"resolves {ticket.catalyst_at:%Y-%m-%d} and carries "
                            f"{symbol}; is anyone discussing it?"
                        ),
                        at_stake_pct=at_stake,
                        max_age_hours=hours,
                        theme=ticket.theme,
                        answer_by=_deadline(ticket, now),
                    )
                )

    tasks.sort(key=lambda t: (-t.at_stake_pct, t.kind, t.subject))
    return Assignment(seat=seat, issued_at=now, tasks=tuple(tasks), note=note)


def audit(
    assignment: Assignment,
    report: SeatReport | None,
    *,
    now: datetime,
) -> Coverage:
    """Compare a filed report against what the desk asked for.

    A report can satisfy `desk/report.py` completely while answering none of
    this. The schema checks that the seat said something well-formed; only this
    checks that it said something the desk wanted.
    """
    crowding_asks = [t for t in assignment.tasks if t.kind == "crowding"]
    assigned = len(crowding_asks)

    if report is None or not report.has_read:
        return Coverage(
            seat=assignment.seat,
            answered=(),
            unanswered=tuple(t.subject for t in crowding_asks),
            stale=(),
            unsolicited=(),
            assigned=assigned,
        )

    answered: list[str] = []
    unanswered: list[str] = []
    stale: list[str] = []

    for task in crowding_asks:
        level = report.crowding_for(task.subject)
        if level is None:
            unanswered.append(task.subject)
            continue
        cutoff = now - timedelta(hours=task.max_age_hours)
        if _latest_social_as_of(report) is not None and _latest_social_as_of(report) < cutoff:
            stale.append(task.subject)
        else:
            answered.append(task.subject)

    asked = {t.subject.strip().lower() for t in crowding_asks}
    unsolicited = sorted(
        name for name in report.crowding if name.strip().lower() not in asked
    )

    return Coverage(
        seat=assignment.seat,
        answered=tuple(answered),
        unanswered=tuple(unanswered),
        stale=tuple(stale),
        unsolicited=tuple(unsolicited),
        assigned=assigned,
    )


def render_assignment(assignment: Assignment) -> str:
    """Serialise to the YAML the seat reads. Hand-rolled to keep field order."""
    lines = [
        "# Issued by `desk assign`. Do not edit by hand — regenerate it.",
        "schema_version: 1",
        f"seat: {assignment.seat}",
        f"issued_at: {_iso(assignment.issued_at)}",
    ]
    if assignment.note:
        lines += ["note: >-", f"  {assignment.note}"]
    lines.append("tasks:")
    if not assignment.tasks:
        lines[-1] = "tasks: []"
    for task in assignment.tasks:
        lines += [
            f"  - task_id: {task.task_id}",
            f"    kind: {task.kind}",
            f"    subject: {_scalar(task.subject)}",
            f"    ticket_id: {task.ticket_id}",
            f"    why: {_scalar(task.why)}",
            f"    at_stake_pct: {task.at_stake_pct:.2f}",
            f"    max_age_hours: {task.max_age_hours:g}",
        ]
        if task.theme:
            lines.append(f"    theme: {task.theme}")
        if task.answer_by:
            lines.append(f"    answer_by: {_iso(task.answer_by)}")
    return "\n".join(lines) + "\n"


_SPECS = (
    FieldSpec("schema_version", int, minimum=1, maximum=1),
    FieldSpec("seat", str),
    FieldSpec("issued_at", (str, datetime)),
    FieldSpec("tasks", list, item_kind=dict),
    FieldSpec("note", str, required=False),
)

_TASK_SPECS = (
    FieldSpec("task_id", str),
    FieldSpec("kind", str, choices=TASK_KINDS),
    FieldSpec("subject", str),
    FieldSpec("ticket_id", str),
    FieldSpec("why", str),
    FieldSpec("at_stake_pct", (int, float), minimum=0, maximum=100),
    FieldSpec("max_age_hours", (int, float), minimum=0),
    FieldSpec("theme", str, required=False),
    FieldSpec("answer_by", (str, datetime), required=False),
)


def parse_assignment(doc: Mapping[str, Any], *, where: str = "assignment") -> Assignment:
    problems = check_fields(doc, _SPECS, where=where)
    if problems:
        raise ValidationError(problems, where=where)

    extra: list[str] = []
    tasks: list[Task] = []
    for i, item in enumerate(doc["tasks"]):
        bad = check_fields(item, _TASK_SPECS, where=f"{where}:tasks[{i}]")
        if bad:
            extra.extend(bad)
            continue
        tasks.append(
            Task(
                task_id=item["task_id"],
                kind=item["kind"],
                subject=item["subject"],
                ticket_id=item["ticket_id"],
                why=item["why"],
                at_stake_pct=float(item["at_stake_pct"]),
                max_age_hours=float(item["max_age_hours"]),
                theme=item.get("theme", ""),
                answer_by=(
                    parse_instant(item["answer_by"], field=f"tasks[{i}].answer_by")
                    if item.get("answer_by")
                    else None
                ),
            )
        )

    ids = [t.task_id for t in tasks]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})
    if duplicated:
        extra.append(f"tasks: duplicate task_id {duplicated} — each ask is answered once")

    if extra:
        raise ValidationError(extra, where=where)

    return Assignment(
        seat=doc["seat"],
        issued_at=parse_instant(doc["issued_at"], field="issued_at"),
        tasks=tuple(tasks),
        note=doc.get("note", ""),
        raw=doc,
    )


def load_assignment(path: str | Path) -> Assignment:
    return parse_assignment(load_document(path), where=str(path))


def load_assignments(directory: str | Path) -> dict[str, Assignment]:
    """Newest assignment per seat. An older one has been superseded."""
    directory = Path(directory)
    if not directory.exists():
        return {}
    newest: dict[str, Assignment] = {}
    for path in sorted(directory.rglob("*.assignment.*")):
        if path.suffix not in (".yaml", ".yml", ".json"):
            continue
        found = load_assignment(path)
        current = newest.get(found.seat)
        if current is None or found.issued_at > current.issued_at:
            newest[found.seat] = found
    return newest


def _at_stake(ticket: Ticket, cap: float) -> float:
    """The most risk this name could carry once research resolves it.

    Not taken down by the conviction ladder, which was the second wrong answer
    here. Four of the five tickets in the book sit at confidence 1, whose
    ladder fraction is 0.00 — so discounting by it priced every unresearched
    name at zero and sorted them last. Confidence is the thing a crowding read
    informs; discounting the work by the number the work produces is circular.

    So: the theme cap, capped again by a declared hint when the ticket named
    one. A ticket asking for 0.25% does not become a 1.5% priority.
    """
    if ticket.size_hint_pct > 0:
        return min(ticket.size_hint_pct, cap)
    return cap


def _gist(text: str, limit: int = 90) -> str:
    """First sentence of a catalyst, for use as a subject line.

    A ticket's catalyst is prose and can run to a paragraph. Reading it into a
    YAML `subject` unedited produced a 300-character field that no seat could
    answer against and no terminal could print.
    """
    flat = " ".join(text.split())
    first = flat.split(". ")[0].strip().rstrip(".")
    if len(first) <= limit:
        return first
    return first[: limit - 1].rsplit(" ", 1)[0] + "…"


def _answered_fresh(
    prior: SeatReport | None, symbol: str, fresh_since: datetime
) -> bool:
    """Whether a recent report already carries a usable call on this name."""
    if prior is None or prior.crowding_for(symbol) is None:
        return False
    return prior.produced_at >= fresh_since


def _latest_social_as_of(report: SeatReport) -> datetime | None:
    stamps = [e.as_of for e in report.evidence]
    return max(stamps) if stamps else None


def _deadline(ticket: Ticket, now: datetime) -> datetime | None:
    if ticket.catalyst_at and ticket.catalyst_at > now:
        return ticket.catalyst_at
    _, end = ticket.horizon_window(now)
    return end


def _iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S%z") or value.isoformat()


def _scalar(text: str) -> str:
    """Quote anything YAML would misread, and flatten newlines."""
    flat = " ".join(text.split())
    if not flat:
        return '""'
    if flat[0] in "&*!|>%@`{}[]#-?," or ": " in flat or flat.endswith(":"):
        return '"' + flat.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return flat
