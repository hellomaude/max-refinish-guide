"""Grading a research seat, and turning the grade into instructions.

Every other seat is scored. A seat named in a ticket's `source_seats` lands in
the outcome ledger and carries its own expectancy; Jev is scored by whether
contested tickets did worse than cleared ones. Grok was scored by nothing,
because a seat that never originates a ticket never appears in the ledger at
all — so it could be wrong indefinitely at no cost, which is precisely the
condition the rest of this desk was built to remove.

A crowding call is falsifiable, which is what makes this possible. Saying
`consensus` or `crowded` on a name is a claim that the edge is gone. If the
desk then took that name and it worked, the call was wrong, and wrong in the
expensive direction: it argued a winner down. `differentiated` is the weak
opposite claim.

So the test is the one already used on Jev — does the call separate winners
from losers — and the output is the seat's next brief rather than a score
nobody reads.

Two honest limits, stated rather than smoothed over:

  * A call only counts if it predates the decision. A crowding read filed
    after Max sized the ticket is hindsight and is dropped.
  * A call on a ticket the desk skipped cannot be scored. Grok talking the
    desk out of a trade is the seat working as designed, and the desk does not
    get to know what it avoided. That blind spot is reported, not papered over.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Mapping, Sequence

from .assign import Assignment, Coverage, audit
from .ledger import Outcome
from .report import CROWDING, SeatReport
from .ticket import Ticket

# The two calls that assert an idea is already priced. Both are bearish on the
# desk's own thesis, which is the output the seat exists to produce.
BEARISH = ("consensus", "crowded")

# How far apart the two buckets must sit before the difference is called a
# finding rather than noise. Matches the ledger's threshold on Jev.
MARGIN_R = 0.25
MIN_SIDE = 3


@dataclass(frozen=True)
class Call:
    """One crowding call matched to one resolved ticket."""

    symbol: str
    level: str
    ticket_id: str
    called_at: datetime
    result_r: float


@dataclass
class Grade:
    """How a seat's crowding calls have actually done."""

    seat: str
    bearish: list[float] = field(default_factory=list)
    differentiated: list[float] = field(default_factory=list)
    unrated: list[float] = field(default_factory=list)
    skipped_after_bearish: int = 0
    hindsight_dropped: int = 0
    calls: list[Call] = field(default_factory=list)

    @property
    def scored(self) -> int:
        return len(self.bearish) + len(self.differentiated)

    @property
    def bearish_mean(self) -> float | None:
        return statistics.fmean(self.bearish) if self.bearish else None

    @property
    def differentiated_mean(self) -> float | None:
        return statistics.fmean(self.differentiated) if self.differentiated else None

    @property
    def separation_r(self) -> float | None:
        """How much worse the names it called known did.

        Positive is the seat working: `consensus` marked the losers.
        """
        lo, hi = self.bearish_mean, self.differentiated_mean
        if lo is None or hi is None:
            return None
        return hi - lo


def grade_crowding(
    outcomes: Iterable[Outcome],
    history: Sequence[SeatReport],
    tickets: Sequence[Ticket],
    *,
    seat: str = "Grok",
) -> Grade:
    """Score a seat's crowding calls against realised R.

    The call used is the newest one filed *before* the ticket was decided. A
    seat that revises toward the outcome should not be rewarded for the
    revision, and a seat that was right early should not be punished for
    later noise.
    """
    grade = Grade(seat=seat)
    by_id = {t.id: t for t in tickets}
    mine = [r for r in history if r.seat.strip().lower() == seat.strip().lower()]

    for outcome in outcomes:
        ticket = by_id.get(outcome.ticket_id)
        if ticket is None:
            continue
        symbol = ticket.instrument.symbol
        level, any_call = _call_before(mine, symbol, outcome.decided_at)

        if not outcome.taken:
            if level in BEARISH:
                grade.skipped_after_bearish += 1
            continue
        if not outcome.resolved:
            continue

        value = float(outcome.result_r or 0.0)
        if level is None:
            if any_call:
                grade.hindsight_dropped += 1
            grade.unrated.append(value)
            continue

        grade.calls.append(
            Call(
                symbol=symbol,
                level=level,
                ticket_id=outcome.ticket_id,
                called_at=outcome.decided_at,
                result_r=value,
            )
        )
        if level in BEARISH:
            grade.bearish.append(value)
        else:
            grade.differentiated.append(value)

    return grade


def grade_report(grade: Grade) -> list[str]:
    """The finding, in the ledger's voice."""
    lines: list[str] = []

    if grade.skipped_after_bearish:
        lines.append(
            f"{grade.seat}: {grade.skipped_after_bearish} ticket(s) skipped after a "
            "consensus or crowded call and therefore unscoreable — the desk cannot "
            "see what it avoided"
        )
    if grade.hindsight_dropped:
        lines.append(
            f"{grade.seat}: {grade.hindsight_dropped} call(s) dropped as hindsight — "
            "filed after the ticket was decided, so they predicted nothing"
        )

    if len(grade.bearish) < MIN_SIDE or len(grade.differentiated) < MIN_SIDE:
        lines.append(
            f"{grade.seat}: too thin to judge (called-known n={len(grade.bearish)}, "
            f"differentiated n={len(grade.differentiated)}); needs {MIN_SIDE}+ resolved "
            "on each side"
        )
        return lines

    bear = grade.bearish_mean or 0.0
    diff = grade.differentiated_mean or 0.0
    gap = grade.separation_r or 0.0
    lines.append(
        f"{grade.seat}: called-known {bear:+.2f}R (n={len(grade.bearish)}) vs "
        f"differentiated {diff:+.2f}R (n={len(grade.differentiated)})"
    )

    if gap > MARGIN_R:
        lines.append(
            f"{grade.seat} is earning its seat — names it called known ran {gap:.2f}R "
            "worse, so the crowding read is carrying information"
        )
    elif gap < -MARGIN_R:
        lines.append(
            f"{grade.seat} is inverted — the names it called consensus outperformed "
            "the ones it called differentiated. It is reading loudness as positioning: "
            "attention arrives with a move, and an idea being discussed is not the "
            "same as it being owned"
        )
    else:
        lines.append(
            f"{grade.seat}'s crowding calls are not separating winners from losers. "
            "The seat is producing a field the desk acts on and it means nothing yet"
        )
    return lines


def coach(
    grade: Grade,
    coverage: Sequence[Coverage] = (),
    *,
    seat: str = "Grok",
) -> list[str]:
    """What to change, as instructions the seat can act on.

    This is the part that makes the loop a loop. A grade tells the desk how the
    seat did; this tells the seat what to do differently, in terms its brief
    already uses, so the output can be appended to the brief rather than
    interpreted.
    """
    out: list[str] = []

    answered = sum(len(c.answered) for c in coverage)
    assigned = sum(c.assigned for c in coverage)
    unsolicited = sum(len(c.unsolicited) for c in coverage)
    stale = sum(len(c.stale) for c in coverage)

    if assigned:
        rate = answered / assigned
        if rate < 0.8:
            out.append(
                f"Answer the work order. You covered {answered} of {assigned} assigned "
                f"names ({rate:.0%}). An unanswered crowding ask does not leave the desk "
                "neutral on that name — it leaves a sized ticket with no read on whether "
                "it is already known."
            )
        if unsolicited > answered and answered < assigned:
            out.append(
                f"You rated {unsolicited} name(s) nobody asked about while leaving "
                f"{assigned - answered} assigned name(s) blank. That is the drift the "
                "assignment exists to stop: the names you volunteer are the loud ones, "
                "and the loud ones are where a second opinion is worth least."
            )
    if stale:
        out.append(
            f"{stale} answer(s) came back past the freshness budget. A call the engine "
            "refuses is the same as no call, and it costs the desk the ticket. If you "
            "cannot get inside the window, file `no_read` on that name and say so."
        )

    separation = grade.separation_r
    if separation is not None and grade.scored >= 2 * MIN_SIDE:
        if separation < -MARGIN_R:
            out.append(
                "Stop scoring volume. Your consensus calls are landing on winners, "
                "which is what happens when mention count is used as the measure — "
                "volume rises *with* a move, so it flags momentum, not saturation. "
                "Rate `crowded` only on position-talk: entries, targets, size, "
                "people saying what they own. Rate `consensus` only when the "
                "*argument* is repeated back to you unprompted, not when the ticker is."
            )
        elif abs(separation) <= MARGIN_R:
            out.append(
                "Your three levels are not distinguishing anything. Use `crowded` "
                "more sparingly and make it mean one thing — actively pitched with "
                "position-talk — so the desk can act on it. A level that fires on "
                "everything is the same as no level."
            )
        else:
            out.append(
                f"Keep doing what you are doing: the read is worth {separation:.2f}R "
                "of separation. Do not broaden it to cover more names at the cost of "
                "this."
            )

    if grade.skipped_after_bearish and grade.scored < MIN_SIDE:
        out.append(
            "Most of your calls land on tickets the desk then skipped, so they cannot "
            "be scored. That is you working correctly and it is also a measurement "
            "hole. Keep filing a call before the decision, not after — an unscoreable "
            "call still has to be timed right to count later."
        )

    if not out:
        out.append(
            f"Nothing to correct. Not enough scored calls yet to tune {seat} on "
            "anything but compliance, and compliance is clean."
        )
    return out


def coverage_history(
    assignments: Mapping[str, Assignment],
    history: Sequence[SeatReport],
    *,
    now: datetime,
    seat: str = "Grok",
) -> list[Coverage]:
    """Audit each assignment against the report that answered it.

    The answering report is the first one filed after the assignment was
    issued. A report filed before it cannot have been a response to it.
    """
    out: list[Coverage] = []
    assignment = assignments.get(seat)
    if assignment is None:
        return out
    mine = [r for r in history if r.seat.strip().lower() == seat.strip().lower()]
    answering = next((r for r in mine if r.produced_at >= assignment.issued_at), None)
    out.append(audit(assignment, answering, now=now))
    return out


def level_counts(history: Sequence[SeatReport], *, seat: str = "Grok") -> dict[str, int]:
    """How often the seat reaches for each level.

    A seat that has never once said `crowded` is not being careful; it is not
    using the field.
    """
    counts = {level: 0 for level in CROWDING}
    for report in history:
        if report.seat.strip().lower() != seat.strip().lower():
            continue
        for level in report.crowding.values():
            if level in counts:
                counts[level] += 1
    return counts


def _call_before(
    reports: Sequence[SeatReport], symbol: str, cutoff: datetime
) -> tuple[str | None, bool]:
    """Newest call on `symbol` filed before `cutoff`, and whether any exists at all.

    The second value separates "never looked at this name" from "looked, but
    too late to count".
    """
    level: str | None = None
    seen = False
    for report in sorted(reports, key=lambda r: r.produced_at):
        found = report.crowding_for(symbol)
        if found is None:
            continue
        seen = True
        if report.produced_at < cutoff:
            level = found
    return level, seen
