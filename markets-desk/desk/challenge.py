"""Jev: the adversary seat.

Every other seat proposes. Wire finds the story, Chain finds the flow, Odds
finds the mispricing — and each writes up an idea it already likes. Rails then
checks the *size* of that idea, never whether it is true. Nobody on the desk is
paid to be the other side.

Jev is. It is the one seat that may not originate a ticket, because a seat that
proposes cannot credibly attack, and a seat that scores its own ideas will
always find they were nearly right.

The challenge has teeth. `confidence_adjustment` feeds the conviction ladder
before any cap applies, so a contested ticket carries less risk automatically
rather than after an argument. The adjustment can only subtract or hold:
letting the adversary add conviction would make it a second proposer and
reward it for being agreeable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .loader import FieldSpec, ValidationError, check_fields, load_document, parse_instant

# How hard Jev is pushing.
CONTEST = "contest"   # the thesis survives, but weaker than the author thinks
CONCEDE = "concede"   # attacked it properly and it held
KILL = "kill"         # the thesis is broken, not merely optimistic
VERDICTS = (CONTEST, CONCEDE, KILL)

_MIN_COUNTER_CHARS = 60
_MIN_MIND_CHANGE_CHARS = 25


@dataclass(frozen=True)
class Challenge:
    """One adversarial read of one ticket."""

    ticket_id: str
    challenger: str
    challenged_at: datetime
    verdict: str
    strongest_counter: str
    what_would_change_my_mind: str
    confidence_adjustment: int = 0
    missed_invalidation: str = ""
    evidence_disputed: tuple[str, ...] = ()
    notes: str = ""
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def kills(self) -> bool:
        return self.verdict == KILL

    @property
    def contests(self) -> bool:
        return self.verdict in (CONTEST, KILL)

    def line(self) -> str:
        adjustment = (
            f" conviction {self.confidence_adjustment:+d}"
            if self.confidence_adjustment
            else ""
        )
        return f"{self.ticket_id}: {self.verdict.upper()}{adjustment} — {self.strongest_counter}"


_SPECS = (
    FieldSpec("schema_version", int, minimum=2, maximum=2),
    FieldSpec("ticket_id", str),
    FieldSpec("challenger", str),
    FieldSpec("challenged_at", (str, datetime)),
    FieldSpec("verdict", str, choices=VERDICTS),
    FieldSpec("strongest_counter", str),
    FieldSpec("what_would_change_my_mind", str),
    FieldSpec("confidence_adjustment", int, required=False, minimum=-4, maximum=0),
    FieldSpec("missed_invalidation", str, required=False),
    FieldSpec("evidence_disputed", list, required=False, item_kind=str),
    FieldSpec("notes", str, required=False),
)


def parse_challenge(doc: Mapping[str, Any], *, where: str = "challenge") -> Challenge:
    problems = check_fields(doc, _SPECS, where=where)
    if problems:
        raise ValidationError(problems, where=where)

    extra: list[str] = []
    counter = doc["strongest_counter"].strip()
    if len(counter) < _MIN_COUNTER_CHARS:
        extra.append(
            f"strongest_counter: needs at least {_MIN_COUNTER_CHARS} characters. "
            "The job is to build the other side's best argument, not to register doubt"
        )
    if len(doc["what_would_change_my_mind"].strip()) < _MIN_MIND_CHANGE_CHARS:
        extra.append(
            "what_would_change_my_mind: required and substantive. An objection nothing "
            "could settle is an opinion, and the desk already has those"
        )

    verdict = doc["verdict"]
    adjustment = int(doc.get("confidence_adjustment") or 0)
    # A kill is not a soft signal, and a concede that still docks conviction is
    # the adversary trying to have it both ways.
    if verdict == CONCEDE and adjustment != 0:
        extra.append("confidence_adjustment: must be 0 on a concede")
    if verdict == CONTEST and adjustment == 0:
        extra.append(
            "confidence_adjustment: a contest that costs the ticket nothing is a note, "
            "not a challenge — either move it or concede"
        )

    if extra:
        raise ValidationError(extra, where=where)

    return Challenge(
        ticket_id=doc["ticket_id"],
        challenger=doc["challenger"],
        challenged_at=parse_instant(doc["challenged_at"], field="challenged_at"),
        verdict=verdict,
        strongest_counter=counter,
        what_would_change_my_mind=doc["what_would_change_my_mind"].strip(),
        confidence_adjustment=adjustment,
        missed_invalidation=doc.get("missed_invalidation", "").strip(),
        evidence_disputed=tuple(doc.get("evidence_disputed") or ()),
        notes=doc.get("notes", ""),
        raw=doc,
    )


def load_challenge(path: str | Path) -> Challenge:
    return parse_challenge(load_document(path), where=str(path))


def load_challenges(directory: str | Path) -> dict[str, Challenge]:
    """Every challenge under `directory`, keyed by ticket id.

    When a ticket has been challenged more than once the newest wins — Jev is
    allowed to change its mind as evidence arrives, and the desk should act on
    the current read rather than the first one.
    """
    directory = Path(directory)
    if not directory.exists():
        return {}
    newest: dict[str, Challenge] = {}
    for path in sorted(directory.rglob("*.challenge.*")):
        if path.suffix not in (".yaml", ".yml", ".json"):
            continue
        challenge = load_challenge(path)
        existing = newest.get(challenge.ticket_id)
        if existing is None or challenge.challenged_at > existing.challenged_at:
            newest[challenge.ticket_id] = challenge
    return newest


def unchallenged(ticket_ids: Iterable[str], challenges: Mapping[str, Challenge]) -> list[str]:
    return [tid for tid in ticket_ids if tid not in challenges]
