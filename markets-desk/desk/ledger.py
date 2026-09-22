"""The outcome ledger: the part of a desk that makes it get better.

The handoff described a research organisation with no memory of whether its
research worked. Seats produced tickets, Rails stamped them, and nothing ever
scored them. Without this loop, "confidence 4" is a mood, and a seat that has
been wrong eleven times running carries the same weight as one that has not.
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .loader import FieldSpec, ValidationError, check_fields, load_document, parse_instant
from .ticket import Ticket


@dataclass(frozen=True)
class Outcome:
    """What actually happened to one ticket.

    `result_r` is in R — multiples of the risk the ticket declared — so a 0.25%
    idea and a 1.0% idea are comparable. Skipped tickets are recorded too:
    a desk that only scores the trades it took cannot see its own selection bias.
    """

    ticket_id: str
    decided_at: datetime
    taken: bool
    sized_pct: float = 0.0
    result_r: float | None = None
    closed_at: datetime | None = None
    reason: str = ""
    seats: tuple[str, ...] = ()
    theme: str = ""
    confidence: int = 0

    @property
    def resolved(self) -> bool:
        return self.taken and self.result_r is not None

    @property
    def won(self) -> bool:
        return self.resolved and (self.result_r or 0.0) > 0


@dataclass
class SeatScore:
    """How one seat (or theme, or confidence level) has actually done."""

    key: str
    proposed: int = 0
    taken: int = 0
    resolved: int = 0
    wins: int = 0
    r_values: list[float] = field(default_factory=list)

    @property
    def hit_rate(self) -> float | None:
        return self.wins / self.resolved if self.resolved else None

    @property
    def expectancy_r(self) -> float | None:
        return statistics.fmean(self.r_values) if self.r_values else None

    @property
    def total_r(self) -> float:
        return sum(self.r_values)

    @property
    def worst_r(self) -> float | None:
        return min(self.r_values) if self.r_values else None

    def row(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "proposed": self.proposed,
            "taken": self.taken,
            "resolved": self.resolved,
            "hit_rate": _round(self.hit_rate),
            "expectancy_r": _round(self.expectancy_r),
            "total_r": _round(self.total_r),
            "worst_r": _round(self.worst_r),
        }


_OUTCOME_SPECS = (
    FieldSpec("ticket_id", str),
    FieldSpec("decided_at", (str, datetime)),
    FieldSpec("taken", bool),
    FieldSpec("sized_pct", (int, float), required=False, minimum=0, maximum=100),
    FieldSpec("result_r", (int, float), required=False),
    FieldSpec("closed_at", (str, datetime), required=False),
    FieldSpec("reason", str, required=False),
)


def parse_outcome(
    doc: Mapping[str, Any],
    *,
    ticket: Ticket | None = None,
    where: str = "outcome",
) -> Outcome:
    problems = check_fields(doc, _OUTCOME_SPECS, where=where)
    if problems:
        raise ValidationError(problems, where=where)
    if doc["taken"] and doc.get("result_r") is None and not doc.get("closed_at"):
        pass  # an open position: legitimate, just not yet scoreable
    if not doc["taken"] and not (doc.get("reason") or "").strip():
        raise ValidationError(
            ["reason: required when a ticket was not taken; skips are data too"], where=where
        )
    return Outcome(
        ticket_id=doc["ticket_id"],
        decided_at=parse_instant(doc["decided_at"], field="decided_at"),
        taken=bool(doc["taken"]),
        sized_pct=float(doc.get("sized_pct") or 0.0),
        result_r=(None if doc.get("result_r") is None else float(doc["result_r"])),
        closed_at=(parse_instant(doc["closed_at"], field="closed_at") if doc.get("closed_at") else None),
        reason=doc.get("reason", ""),
        seats=tuple(ticket.source_seats) if ticket else tuple(doc.get("seats") or ()),
        theme=ticket.theme if ticket else doc.get("theme", ""),
        confidence=ticket.confidence if ticket else int(doc.get("confidence") or 0),
    )


def load_outcomes(directory: str | Path, tickets: Sequence[Ticket] = ()) -> list[Outcome]:
    directory = Path(directory)
    by_id = {t.id: t for t in tickets}
    out: list[Outcome] = []
    for path in sorted(directory.rglob("*.outcome.*")):
        if path.suffix not in (".yaml", ".yml", ".json"):
            continue
        doc = load_document(path)
        out.append(parse_outcome(doc, ticket=by_id.get(doc.get("ticket_id", "")), where=str(path)))
    return out


def score(
    outcomes: Iterable[Outcome],
    *,
    dimension: str = "seat",
    seat_to_model: Mapping[str, str] | None = None,
) -> list[SeatScore]:
    """Aggregate outcomes along one dimension: seat, theme, confidence, or model.

    `model` needs `seat_to_model` from the roster. Seats that share a model
    share a failure mode, and a systematic bias in one vendor should show up
    as one row rather than be spread thin across five.
    """
    if dimension not in ("seat", "theme", "confidence", "model"):
        raise ValueError(f"unknown dimension {dimension!r}")
    if dimension == "model" and seat_to_model is None:
        raise ValueError("dimension='model' needs seat_to_model from the roster")

    scores: dict[str, SeatScore] = {}
    for outcome in outcomes:
        if dimension == "seat":
            keys = list(outcome.seats) or ["(unattributed)"]
        elif dimension == "theme":
            keys = [outcome.theme or "(untagged)"]
        elif dimension == "model":
            mapped = {(seat_to_model or {}).get(s, "(unrostered)") for s in outcome.seats}
            keys = sorted(mapped) or ["(unattributed)"]
        else:
            keys = [str(outcome.confidence or "?")]
        for key in keys:
            entry = scores.setdefault(key, SeatScore(key=key))
            entry.proposed += 1
            if outcome.taken:
                entry.taken += 1
            if outcome.resolved:
                entry.resolved += 1
                entry.r_values.append(float(outcome.result_r or 0.0))
                if outcome.won:
                    entry.wins += 1
    return sorted(scores.values(), key=lambda s: (-s.total_r, s.key))


def calibration_report(outcomes: Iterable[Outcome]) -> list[str]:
    """Flag confidence levels that do not behave like confidence.

    The test is deliberately crude — monotonicity of expectancy across levels —
    because with a handful of tickets a month, anything fancier is noise
    dressed as rigour.
    """
    by_level = {s.key: s for s in score(outcomes, dimension="confidence")}
    lines: list[str] = []
    ordered = [by_level[str(i)] for i in range(1, 6) if str(i) in by_level]
    scored = [s for s in ordered if s.resolved > 0]
    if len(scored) < 2:
        return ["calibration: not enough resolved tickets to say anything yet"]
    for lower, higher in zip(scored, scored[1:]):
        lo, hi = lower.expectancy_r or 0.0, higher.expectancy_r or 0.0
        if hi < lo:
            lines.append(
                f"calibration: confidence {higher.key} ({hi:+.2f}R over {higher.resolved}) "
                f"underperforms confidence {lower.key} ({lo:+.2f}R over {lower.resolved}) "
                "— the ladder is not earning its slope"
            )
    thin = [s for s in scored if s.resolved < 5]
    if thin:
        lines.append(
            "calibration: thin samples at confidence "
            + ", ".join(f"{s.key} (n={s.resolved})" for s in thin)
        )
    return lines or ["calibration: expectancy rises with confidence as intended"]


def challenge_report(
    outcomes: Iterable[Outcome],
    challenges: Mapping[str, Any],
) -> list[str]:
    """Is the adversary seat earning its place?

    The test is whether contested tickets went on to do worse than the ones Jev
    let through. If they did, the objections were carrying information and the
    conviction docking was correct. If contested tickets did just as well, Jev
    is taxing the book for nothing and the seat needs recalibrating, not
    respect.

    Killed tickets cannot be scored — they were never taken, and the desk does
    not get to know what would have happened. That is a real blind spot and is
    reported rather than papered over.
    """
    contested: list[float] = []
    cleared: list[float] = []
    killed = 0

    for outcome in outcomes:
        held = challenges.get(outcome.ticket_id)
        if held is not None and getattr(held, "kills", False):
            killed += 1
            continue
        if not outcome.resolved:
            continue
        value = float(outcome.result_r or 0.0)
        if held is not None and getattr(held, "contests", False):
            contested.append(value)
        else:
            cleared.append(value)

    lines: list[str] = []
    if killed:
        lines.append(
            f"challenges: {killed} ticket(s) killed and therefore unscoreable — "
            "the desk cannot see what it avoided"
        )
    if len(contested) < 3 or len(cleared) < 3:
        lines.append(
            f"challenges: too thin to judge (contested n={len(contested)}, "
            f"cleared n={len(cleared)}); needs 3+ resolved on each side"
        )
        return lines

    contested_mean = statistics.fmean(contested)
    cleared_mean = statistics.fmean(cleared)
    gap = cleared_mean - contested_mean
    lines.append(
        f"challenges: contested {contested_mean:+.2f}R (n={len(contested)}) vs "
        f"cleared {cleared_mean:+.2f}R (n={len(cleared)})"
    )
    if gap > 0.25:
        lines.append(
            f"challenges: Jev is earning its seat — objections ran {gap:.2f}R worse, "
            "so the conviction docking is working"
        )
    elif gap < -0.25:
        lines.append(
            "challenges: Jev is inverted — contested tickets outperformed the ones it "
            "cleared. It is taxing good ideas; recut the seat before trusting it further"
        )
    else:
        lines.append(
            "challenges: Jev's objections are not separating winners from losers. "
            "The seat is costing size without buying information"
        )
    return lines


def write_csv(scores: Sequence[SeatScore], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["key", "proposed", "taken", "resolved", "hit_rate", "expectancy_r", "total_r", "worst_r"],
        )
        writer.writeheader()
        for entry in scores:
            writer.writerow(entry.row())
    return path


def _round(value: float | None, digits: int = 3) -> str:
    return "" if value is None else f"{value:.{digits}f}"
