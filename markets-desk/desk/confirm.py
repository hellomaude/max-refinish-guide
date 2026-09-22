"""The confirm: how "Max approves every capital action" becomes code.

Before this, the gate lived in a sentence. Codex was told to format a sheet
only after Max confirmed, and the only record of a confirm was wherever Max
happened to say it. That is a rule; this is a mechanism.

A confirm is a file. It names one ticket, one session, one ceiling, and it
carries a digest of the stamp it was made against. Codex formats a sheet only
for a ticket whose confirm is on file, unexpired, signed by Max, and whose
digest still matches the book. If the book moves — a seat files, Jev revises,
a window opens — the digest changes and the confirm is void. Re-stamp,
re-confirm. There is no override and no batch.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .loader import FieldSpec, ValidationError, check_fields, load_document, parse_instant
from .risk import PASS, Book, Stamp
from .ticket import Ticket

# The only party who may confirm. Not a role, not a list — the owner.
CONFIRMER = "max"
DEVICES = ("mac", "iphone", "cli")

# A confirm is good for one session. Eight hours covers 06:30 to close.
DEFAULT_TTL = timedelta(hours=8)


def stamp_digest(stamp: Stamp, book: Book) -> str:
    """A hash of everything about a stamp that a confirm is agreeing to.

    Reasons are left out: they are prose and can be reworded without the
    decision changing. Everything numeric, the verdict, the constraint, and
    the desk's mode are in, so a confirm made under `live_confirm` cannot be
    replayed under anything else.
    """
    core = {
        "ticket_id": stamp.ticket_id,
        "verdict": stamp.verdict,
        "requested_pct": round(stamp.requested_pct, 4),
        "allowed_pct": round(stamp.allowed_pct, 4),
        "theme": stamp.theme,
        "binding_constraint": stamp.binding_constraint,
        "effective_confidence": stamp.effective_confidence,
        "challenge_verdict": stamp.challenge_verdict,
        "mode": book.mode,
        "execution": book.execution,
    }
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Confirm:
    """One deliberate yes from Max, for one ticket, for one session."""

    ticket_id: str
    confirmed_at: datetime
    confirmed_by: str
    device: str
    stamp_sha256: str
    allowed_pct: float
    verdict: str
    expires_at: datetime
    instrument: Mapping[str, Any] = field(default_factory=dict)
    direction: str = ""
    entry: float | None = None
    stop: float | None = None
    note: str = ""
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def matches(self, stamp: Stamp, book: Book) -> bool:
        """Whether the book this confirm agreed to is still the book."""
        return self.stamp_sha256 == stamp_digest(stamp, book) and abs(
            self.allowed_pct - stamp.allowed_pct
        ) < 1e-9

    def problems(self, stamp: Stamp | None, book: Book, *, now: datetime) -> list[str]:
        """Why this confirm cannot be acted on, or nothing."""
        out: list[str] = []
        if self.expired(now):
            out.append(f"{self.ticket_id}: confirm expired {self.expires_at:%Y-%m-%d %H:%MZ}")
        if stamp is None:
            out.append(f"{self.ticket_id}: no stamp for this ticket in the current book")
            return out
        if stamp.verdict != PASS or stamp.allowed_pct <= 0:
            out.append(
                f"{self.ticket_id}: current stamp is {stamp.verdict.upper()} at "
                f"{stamp.allowed_pct:.2f}% — a confirm needs a live PASS"
            )
        if not self.matches(stamp, book):
            out.append(
                f"{self.ticket_id}: the book moved since this confirm — digest no longer "
                "matches; re-stamp and re-confirm"
            )
        return out

    @property
    def usable_now(self) -> bool:  # pragma: no cover - convenience
        return not self.expired(datetime.now(timezone.utc))


_SPECS = (
    FieldSpec("schema_version", int, minimum=1, maximum=1),
    FieldSpec("ticket_id", str),
    FieldSpec("confirmed_at", (str, datetime)),
    FieldSpec("confirmed_by", str),
    FieldSpec("device", str, choices=DEVICES),
    FieldSpec("stamp_sha256", str),
    FieldSpec("allowed_pct", (int, float), minimum=0, maximum=100),
    FieldSpec("verdict", str),
    FieldSpec("expires_at", (str, datetime)),
    FieldSpec("instrument", dict, required=False),
    FieldSpec("direction", str, required=False),
    FieldSpec("entry", (int, float), required=False, minimum=0),
    FieldSpec("stop", (int, float), required=False, minimum=0),
    FieldSpec("note", str, required=False),
)


def parse_confirm(doc: Mapping[str, Any], *, where: str = "confirm") -> Confirm:
    problems = check_fields(doc, _SPECS, where=where)
    if problems:
        raise ValidationError(problems, where=where)

    extra: list[str] = []
    who = str(doc["confirmed_by"]).strip().lower()
    if who != CONFIRMER:
        extra.append(
            f"confirmed_by: {doc['confirmed_by']!r} — only {CONFIRMER!r} confirms. There is no "
            "delegate, no role, and no agent that may stand in"
        )
    if doc["verdict"] != PASS:
        extra.append(
            f"verdict: {doc['verdict']!r} — a confirm is only ever made against a PASS. "
            "Confirming a PENDING or FAIL is confirming nothing"
        )
    if float(doc["allowed_pct"]) <= 0:
        extra.append("allowed_pct: a confirm on a 0.00% ceiling is a confirm on nothing")
    digest = str(doc["stamp_sha256"]).strip().lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        extra.append("stamp_sha256: not a sha256 hex digest")

    confirmed_at = parse_instant(doc["confirmed_at"], field="confirmed_at")
    expires_at = parse_instant(doc["expires_at"], field="expires_at")
    if expires_at <= confirmed_at:
        extra.append("expires_at: must be after confirmed_at")
    if expires_at - confirmed_at > timedelta(hours=24):
        extra.append(
            "expires_at: a confirm is good for one session, not a standing order — "
            "more than 24h is refused"
        )
    if extra:
        raise ValidationError(extra, where=where)

    return Confirm(
        ticket_id=doc["ticket_id"],
        confirmed_at=confirmed_at,
        confirmed_by=who,
        device=doc["device"],
        stamp_sha256=digest,
        allowed_pct=float(doc["allowed_pct"]),
        verdict=doc["verdict"],
        expires_at=expires_at,
        instrument=dict(doc.get("instrument") or {}),
        direction=str(doc.get("direction", "")),
        entry=(None if doc.get("entry") is None else float(doc["entry"])),
        stop=(None if doc.get("stop") is None else float(doc["stop"])),
        note=str(doc.get("note", "")),
        raw=doc,
    )


def load_confirm(path: str | Path) -> Confirm:
    return parse_confirm(load_document(path), where=str(path))


def load_confirms(directory: str | Path) -> dict[str, Confirm]:
    """Newest confirm per ticket. An older one has been superseded."""
    directory = Path(directory)
    if not directory.exists():
        return {}
    newest: dict[str, Confirm] = {}
    for path in sorted(directory.rglob("*.confirm.*")):
        if path.suffix not in (".yaml", ".yml", ".json"):
            continue
        found = load_confirm(path)
        current = newest.get(found.ticket_id)
        if current is None or found.confirmed_at > current.confirmed_at:
            newest[found.ticket_id] = found
    return newest


def make_confirm(
    ticket: Ticket,
    stamp: Stamp,
    book: Book,
    *,
    now: datetime,
    device: str,
    note: str = "",
    ttl: timedelta = DEFAULT_TTL,
) -> Confirm:
    """Build a confirm against the current book, or refuse.

    This is the only constructor a UI or CLI should use. It refuses before it
    writes, so a refused confirm leaves no file behind to be mistaken for one.
    """
    if stamp.ticket_id != ticket.id:
        raise ValidationError([f"stamp is for {stamp.ticket_id}, ticket is {ticket.id}"], where="confirm")
    if stamp.verdict != PASS or stamp.allowed_pct <= 0:
        raise ValidationError(
            [
                f"{ticket.id}: stamp is {stamp.verdict.upper()} at {stamp.allowed_pct:.2f}% — "
                "nothing to confirm. A ceiling of zero is the desk saying no"
            ],
            where="confirm",
        )
    if device not in DEVICES:
        raise ValidationError([f"device: {device!r} not one of {list(DEVICES)}"], where="confirm")
    doc = {
        "schema_version": 1,
        "ticket_id": ticket.id,
        "confirmed_at": now,
        "confirmed_by": CONFIRMER,
        "device": device,
        "stamp_sha256": stamp_digest(stamp, book),
        "allowed_pct": round(stamp.allowed_pct, 4),
        "verdict": stamp.verdict,
        "expires_at": now + ttl,
        "instrument": {
            "kind": ticket.instrument.kind,
            "symbol": ticket.instrument.symbol,
            "venue": ticket.instrument.venue,
            "outcome": ticket.instrument.outcome,
        },
        "direction": ticket.direction,
        "entry": ticket.entry,
        "stop": ticket.stop,
        "note": note,
    }
    return parse_confirm(doc, where=f"confirm:{ticket.id}")


def render_confirm(confirm: Confirm) -> str:
    """Serialise to the YAML on disk. Hand-rolled to keep field order."""
    inst = confirm.instrument
    lines = [
        "# Written by `desk confirm`. One ticket, one session. Do not edit.",
        "schema_version: 1",
        f"ticket_id: {confirm.ticket_id}",
        f"confirmed_at: {_iso(confirm.confirmed_at)}",
        f"confirmed_by: {confirm.confirmed_by}",
        f"device: {confirm.device}",
        f"stamp_sha256: {confirm.stamp_sha256}",
        f"allowed_pct: {confirm.allowed_pct:.4f}",
        f"verdict: {confirm.verdict}",
        f"expires_at: {_iso(confirm.expires_at)}",
        "instrument:",
        f"  kind: {inst.get('kind', '')}",
        f"  symbol: {inst.get('symbol', '')}",
    ]
    if inst.get("venue"):
        lines.append(f"  venue: {inst['venue']}")
    if inst.get("outcome"):
        lines.append(f"  outcome: \"{inst['outcome']}\"")
    lines.append(f"direction: {confirm.direction}")
    lines.append(f"entry: {'null' if confirm.entry is None else confirm.entry}")
    lines.append(f"stop: {'null' if confirm.stop is None else confirm.stop}")
    note = " ".join(confirm.note.split())
    lines.append(f"note: \"{note.replace(chr(34), chr(39))}\"")
    return "\n".join(lines) + "\n"


def write_confirm(confirm: Confirm, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{confirm.confirmed_at:%Y-%m-%d-%H%M%S}-{confirm.ticket_id}.confirm.yaml"
    path.write_text(render_confirm(confirm), encoding="utf-8")
    return path


def usable(
    confirms: Mapping[str, Confirm], book: Book, *, now: datetime
) -> tuple[dict[str, Confirm], list[str]]:
    """Split confirms into those Codex may act on and the reasons for the rest."""
    good: dict[str, Confirm] = {}
    bad: list[str] = []
    for ticket_id, confirm in confirms.items():
        problems = confirm.problems(book.by_id(ticket_id), book, now=now)
        if problems:
            bad.extend(problems)
        else:
            good[ticket_id] = confirm
    return good, bad


def _iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S%z")
