"""Rails: the risk engine.

Rails never executes. It answers one question per ticket — how much of the risk
budget may this idea consume, and what is the binding reason — and it answers it
the same way every time given the same inputs.

The design follows the one rule the desk already had right: correlated ideas
share a cap. Sizing each leg of a crypto-beta basket on its own merits is the
standard way to end up 3x the intended exposure to a single factor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, Mapping, Sequence

from .challenge import Challenge
from .mode import Mode
from .ticket import Evidence, Ticket

PASS = "pass"
FAIL = "fail"
PENDING = "pending"

# Percentages are of the risk budget. Two decimals is one basis point of a
# 100-unit budget: finer than that is false precision on a discretionary desk.
_QUANTUM = 0.01
_EPS = 1e-9


@dataclass(frozen=True)
class OpenRisk:
    """Risk already deployed, so a new ticket competes against live positions."""

    by_theme: Mapping[str, float] = field(default_factory=dict)
    by_symbol: Mapping[str, float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.by_theme.values())

    def theme(self, theme_id: str) -> float:
        return float(self.by_theme.get(theme_id, 0.0))

    def symbol(self, symbol: str) -> float:
        return float(self.by_symbol.get(symbol, 0.0))


@dataclass
class Stamp:
    """Rails' verdict on one ticket."""

    ticket_id: str
    verdict: str
    requested_pct: float
    allowed_pct: float
    theme: str
    binding_constraint: str
    reasons: list[str] = field(default_factory=list)
    stale_evidence: list[str] = field(default_factory=list)
    missing_seats: list[str] = field(default_factory=list)
    challenge_verdict: str = ""
    # Conviction after Jev's adjustment. Also the weight used when a theme or
    # the heat cap has to be shared, so a contested ticket loses twice: once on
    # the ladder and again on its claim to scarce budget.
    effective_confidence: int = 0

    @property
    def blocked(self) -> bool:
        return self.verdict != PASS or self.allowed_pct <= 0

    def line(self) -> str:
        """One-line summary, the form Rails posts into the Codex feed."""
        return (
            f"{self.ticket_id}: {self.verdict.upper()} "
            f"{self.allowed_pct:.2f}% (asked {self.requested_pct:.2f}%) "
            f"— {self.binding_constraint}"
        )


@dataclass
class Book:
    """The whole desk's stamps plus the aggregate it had to respect."""

    stamped_at: datetime
    mode: str
    execution: str
    stamps: list[Stamp]
    portfolio_allowed_pct: float
    portfolio_cap_pct: float
    theme_allowed_pct: dict[str, float] = field(default_factory=dict)

    def by_id(self, ticket_id: str) -> Stamp | None:
        for stamp in self.stamps:
            if stamp.ticket_id == ticket_id:
                return stamp
        return None

    def ranked(self) -> list[Stamp]:
        """Stamps worth acting on first: most risk allowed, then ticket id."""
        return sorted(
            self.stamps, key=lambda s: (-s.allowed_pct, s.ticket_id)
        )


def stale_evidence(ticket: Ticket, mode: Mode, now: datetime) -> list[tuple[Evidence, timedelta]]:
    """Evidence older than its kind's tolerance, with how far over it is.

    This is the gate that would have caught an options-greeks feed still serving
    Friday's expiry on Monday morning: the number looks valid, its `as_of` does
    not.
    """
    stale: list[tuple[Evidence, timedelta]] = []
    for item in ticket.evidence:
        limit = mode.max_age(item.kind)
        if limit is None:
            continue
        age = item.age(now)
        if age > limit:
            stale.append((item, age - limit))
    return stale


def _ceiling_for(
    ticket: Ticket,
    mode: Mode,
    now: datetime,
    open_risk: OpenRisk,
    available_seats: set[str],
    challenge: Challenge | None = None,
) -> Stamp:
    """Per-ticket gates. Each one may only lower the allowance."""
    theme = mode.theme_for(ticket.instrument.label()) or mode.theme_for(ticket.instrument.symbol)
    theme_id = theme.id if theme else ticket.theme
    stamp = Stamp(
        ticket_id=ticket.id,
        verdict=PASS,
        requested_pct=ticket.size_hint_pct,
        allowed_pct=ticket.size_hint_pct,
        theme=theme_id,
        binding_constraint="size_hint",
        challenge_verdict=challenge.verdict if challenge else "",
        effective_confidence=ticket.confidence,
    )

    def clamp(limit: float, name: str, note: str = "") -> None:
        if limit < stamp.allowed_pct - _EPS:
            stamp.allowed_pct = max(0.0, limit)
            stamp.binding_constraint = name
            stamp.reasons.append(note or f"{name} caps this at {limit:.2f}%")

    # --- hard stops -----------------------------------------------------
    if mode.trading_halted:
        stamp.verdict = FAIL
        stamp.allowed_pct = 0.0
        stamp.binding_constraint = "mode.halt"
        stamp.reasons.append("desk mode is 'halt'; no ticket may carry size")
        return stamp

    venue_id = ticket.instrument.venue or ticket.instrument.kind
    venue = mode.venue(venue_id)
    if venue is not None and not venue.enabled:
        stamp.verdict = FAIL
        stamp.allowed_pct = 0.0
        stamp.binding_constraint = f"venue.{venue_id}.disabled"
        stamp.reasons.append(venue.note or f"venue {venue_id} is not armed")
        return stamp

    stale = stale_evidence(ticket, mode, now)
    if stale:
        for item, over in stale:
            hours = over.total_seconds() / 3600.0
            stamp.stale_evidence.append(
                f"{item.key} ({item.kind}) from {item.source} is {hours:.1f}h past tolerance"
            )
        stamp.verdict = FAIL
        stamp.allowed_pct = 0.0
        stamp.binding_constraint = "staleness"
        stamp.reasons.append("thesis rests on evidence past its freshness tolerance")
        return stamp

    missing = [seat for seat in mode.required_seats if seat not in available_seats]
    if missing:
        stamp.missing_seats = missing
        stamp.verdict = PENDING
        stamp.allowed_pct = 0.0
        stamp.binding_constraint = "required_seats"
        stamp.reasons.append("waiting on seat report(s): " + ", ".join(missing))
        return stamp

    # --- the adversary ---------------------------------------------------
    if mode.require_challenge and challenge is None:
        stamp.verdict = PENDING
        stamp.allowed_pct = 0.0
        stamp.binding_constraint = "unchallenged"
        stamp.reasons.append(
            "no challenge on record; the desk does not size a thesis nobody argued against"
        )
        return stamp

    if challenge is not None and challenge.kills:
        stamp.verdict = FAIL
        stamp.allowed_pct = 0.0
        stamp.binding_constraint = "challenge.kill"
        stamp.reasons.append(f"Jev killed it: {challenge.strongest_counter}")
        return stamp

    if ticket.rails_check == FAIL:
        stamp.verdict = FAIL
        stamp.allowed_pct = 0.0
        stamp.binding_constraint = "rails_check.fail"
        stamp.reasons.append("ticket carries an explicit Rails fail")
        return stamp

    if ticket.rails_check == PENDING:
        stamp.verdict = PENDING
        stamp.reasons.append("ticket is marked pending; allowance is provisional")

    # --- soft ceilings --------------------------------------------------
    confidence = ticket.confidence
    if challenge is not None and challenge.confidence_adjustment:
        confidence = max(1, confidence + challenge.confidence_adjustment)
        stamp.reasons.append(
            f"challenged: conviction {ticket.confidence} -> {confidence} "
            f"({_gist(challenge.strongest_counter)})"
        )
    stamp.effective_confidence = confidence

    ladder = mode.conviction_ladder[confidence]
    clamp(
        mode.single_name_pct * ladder,
        f"conviction[{confidence}]",
        f"confidence {confidence} earns {ladder:.0%} of the single-name cap",
    )
    already = open_risk.symbol(ticket.instrument.symbol)
    clamp(
        max(0.0, mode.single_name_pct - already),
        "single_name_cap",
        f"single-name cap {mode.single_name_pct:.2f}% less {already:.2f}% already on",
    )

    start, end = ticket.horizon_window(now)
    for window in mode.event_windows:
        if not window.overlaps(start, end):
            continue
        if not window.binds(ticket.instrument.kind, theme_id):
            continue
        clamp(
            window.max_pct_around_event,
            f"event[{window.id}]",
            window.note or f"{window.id} caps risk at {window.max_pct_around_event:.2f}%",
        )
        if ticket.holds_overnight():
            clamp(
                window.overnight_risk_pct,
                f"event[{window.id}].overnight",
                f"{window.id} allows {window.overnight_risk_pct:.2f}% held overnight",
            )

    return stamp


def _water_fill(cap: float, items: Sequence[tuple[str, float, float]]) -> dict[str, float]:
    """Share `cap` among (key, ceiling, weight) items.

    Weight sets the pro-rata split; nobody exceeds their own ceiling, and slack
    freed by a ceiling-bound item is redistributed rather than lost. That
    matters on a small desk: the alternative — flat scaling — silently starves
    the highest-conviction idea to keep a low-conviction one at its ask.
    """
    granted = {key: 0.0 for key, _, _ in items}
    remaining = max(0.0, cap)
    active = [(key, ceiling, weight) for key, ceiling, weight in items if ceiling > _EPS and weight > _EPS]

    while active and remaining > _EPS:
        total_weight = sum(weight for _, _, weight in active)
        if total_weight <= _EPS:
            break
        # Anyone whose pro-rata share exceeds their ceiling is filled and
        # removed; the loop then re-splits what is left among the rest.
        saturated = [
            (key, ceiling, weight)
            for key, ceiling, weight in active
            if remaining * (weight / total_weight) >= ceiling - granted[key] - _EPS
        ]
        if not saturated:
            for key, _, weight in active:
                granted[key] += remaining * (weight / total_weight)
            remaining = 0.0
            break
        for key, ceiling, _ in saturated:
            remaining -= ceiling - granted[key]
            granted[key] = ceiling
        saturated_keys = {key for key, _, _ in saturated}
        active = [item for item in active if item[0] not in saturated_keys]
        remaining = max(0.0, remaining)

    return granted


def _gist(text: str, limit: int = 140) -> str:
    """First sentence of an argument, for a one-line reason.

    The full counter belongs in the pack, where there is room to read it; a
    stamp table that wraps for ten lines stops being scannable.
    """
    first = text.strip().split(". ")[0].strip().rstrip(".")
    if len(first) <= limit:
        return first
    return first[: limit - 1].rsplit(" ", 1)[0] + "…"


def _floor_to_quantum(value: float) -> float:
    """Round down to the sizing quantum. Rounding up would breach a cap."""
    if value <= 0:
        return 0.0
    return int((value + _EPS) / _QUANTUM) * _QUANTUM


def stamp_book(
    tickets: Iterable[Ticket],
    mode: Mode,
    *,
    now: datetime,
    open_risk: OpenRisk | None = None,
    available_seats: Iterable[str] | None = None,
    challenges: Mapping[str, Challenge] | None = None,
) -> Book:
    """Stamp a whole book at once.

    Whole-book stamping is the point: a ticket's allowance depends on what else
    is competing for the same theme cap, so tickets cannot be sized one at a
    time and added up.
    """
    tickets = list(tickets)
    open_risk = open_risk or OpenRisk()
    seats = set(available_seats or mode.required_seats)

    challenges = challenges or {}
    stamps = [
        _ceiling_for(t, mode, now, open_risk, seats, challenges.get(t.id)) for t in tickets
    ]
    by_id = {t.id: t for t in tickets}
    weight_of = {s.ticket_id: float(max(1, s.effective_confidence)) for s in stamps}

    # --- theme caps -----------------------------------------------------
    theme_allowed: dict[str, float] = {}
    for theme_id in {s.theme for s in stamps}:
        members = [s for s in stamps if s.theme == theme_id]
        cap = max(0.0, mode.cap_for_theme(theme_id) - open_risk.theme(theme_id))
        shares = _water_fill(
            cap,
            [(s.ticket_id, s.allowed_pct, weight_of[s.ticket_id]) for s in members],
        )
        for stamp in members:
            share = shares[stamp.ticket_id]
            if share < stamp.allowed_pct - _EPS:
                stamp.reasons.append(
                    f"theme '{theme_id}' cap {mode.cap_for_theme(theme_id):.2f}% "
                    f"(with {open_risk.theme(theme_id):.2f}% already on) shares this down "
                    f"from {stamp.allowed_pct:.2f}%"
                )
                stamp.binding_constraint = f"theme[{theme_id}]"
                stamp.allowed_pct = share
        theme_allowed[theme_id] = cap

    # --- portfolio heat -------------------------------------------------
    heat_cap = max(0.0, mode.portfolio_heat_pct - open_risk.total)
    shares = _water_fill(
        heat_cap,
        [(s.ticket_id, s.allowed_pct, weight_of[s.ticket_id]) for s in stamps],
    )
    for stamp in stamps:
        share = shares[stamp.ticket_id]
        if share < stamp.allowed_pct - _EPS:
            stamp.reasons.append(
                f"portfolio heat cap {mode.portfolio_heat_pct:.2f}% "
                f"(with {open_risk.total:.2f}% already on) shares this down "
                f"from {stamp.allowed_pct:.2f}%"
            )
            stamp.binding_constraint = "portfolio_heat"
            stamp.allowed_pct = share

    for stamp in stamps:
        stamp.allowed_pct = _floor_to_quantum(stamp.allowed_pct)
        if stamp.allowed_pct <= 0 and stamp.verdict == PASS:
            stamp.verdict = FAIL
            stamp.reasons.append("no risk budget survives the caps; stand down")

    return Book(
        stamped_at=now,
        mode=mode.mode,
        execution=mode.execution,
        stamps=stamps,
        portfolio_allowed_pct=sum(s.allowed_pct for s in stamps),
        portfolio_cap_pct=mode.portfolio_heat_pct,
        theme_allowed_pct=theme_allowed,
    )
