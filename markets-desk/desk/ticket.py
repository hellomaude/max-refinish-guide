"""The ticket: the only object that may ask Max for capital.

A ticket is machine-checkable on purpose. The old markdown template let a seat
write "size_hint: small" and a catalyst with no date; both are now refusals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from .loader import FieldSpec, ValidationError, check_fields, load_document, parse_instant

INSTRUMENT_KINDS = (
    "equity",
    "etf",
    "crypto_spot",
    "crypto_perp",
    "option",
    "prediction_market",
)
DIRECTIONS = ("long", "short")
# Horizon drives the overnight gate, so it is a closed vocabulary.
HORIZONS = ("intraday", "overnight", "swing", "position")
HORIZON_SPANS = {
    "intraday": timedelta(hours=7),
    "overnight": timedelta(days=1),
    "swing": timedelta(days=10),
    "position": timedelta(days=90),
}
RAILS_STATES = ("pass", "fail", "pending")


@dataclass(frozen=True)
class Evidence:
    """One fact a thesis leans on, with the receipt attached.

    `as_of` is when the underlying data was true, not when the seat fetched it.
    That distinction is what catches an options feed frozen at Friday's OpEx.
    """

    key: str
    kind: str
    value: Any
    source: str
    as_of: datetime
    url: str = ""

    def age(self, now: datetime) -> timedelta:
        return now - self.as_of


@dataclass(frozen=True)
class Instrument:
    kind: str
    symbol: str
    venue: str = ""
    outcome: str = ""

    def label(self) -> str:
        if self.outcome:
            return f"{self.symbol}:{self.outcome}"
        return self.symbol


@dataclass(frozen=True)
class Ticket:
    """A validated trade idea awaiting a Rails stamp and Max's gate."""

    id: str
    created_at: datetime
    source_seats: tuple[str, ...]
    instrument: Instrument
    direction: str
    theme: str
    thesis: str
    catalyst: str
    catalyst_at: datetime | None
    invalidation: str
    horizon: str
    size_hint_pct: float
    confidence: int
    evidence: tuple[Evidence, ...]
    sources: tuple[str, ...]
    rails_check: str
    max_gate: bool
    entry: float | None = None
    stop: float | None = None
    defined_risk: bool = False
    notes: str = ""
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def horizon_window(self, now: datetime) -> tuple[datetime, datetime]:
        """The span of time this idea intends to hold risk."""
        return now, now + HORIZON_SPANS[self.horizon]

    def holds_overnight(self) -> bool:
        return self.horizon != "intraday"

    def risk_per_unit(self) -> float | None:
        """Loss per unit if the invalidation level trades. None when unknown."""
        if self.defined_risk and self.entry is not None:
            return self.entry
        if self.entry is None or self.stop is None:
            return None
        return abs(self.entry - self.stop)

    def notional_for_risk(self, risk_dollars: float) -> float | None:
        """Convert a dollar risk allowance into position notional.

        Returns None when the ticket has not declared enough price structure —
        which is itself the answer: Codex must not guess a size.
        """
        per_unit = self.risk_per_unit()
        if per_unit is None or per_unit <= 0 or self.entry is None or self.entry <= 0:
            return None
        units = risk_dollars / per_unit
        return units * self.entry


_TICKET_SPECS = (
    FieldSpec("schema_version", int, minimum=2, maximum=2),
    FieldSpec("id", str),
    FieldSpec("created_at", (str, datetime)),
    FieldSpec("source_seats", list, item_kind=str, min_items=1),
    FieldSpec("instrument", dict),
    FieldSpec("direction", str, choices=DIRECTIONS),
    FieldSpec("theme", str),
    FieldSpec("thesis", str),
    FieldSpec("catalyst", str),
    FieldSpec("catalyst_at", (str, datetime), required=False),
    FieldSpec("invalidation", str),
    FieldSpec("horizon", str, choices=HORIZONS),
    FieldSpec("size_hint_pct", (int, float), minimum=0, maximum=100),
    FieldSpec("confidence", int, minimum=1, maximum=5),
    FieldSpec("evidence", list, item_kind=dict),
    FieldSpec("sources", list, item_kind=str, min_items=1),
    FieldSpec("rails_check", str, choices=RAILS_STATES),
    FieldSpec("max_gate", bool),
    FieldSpec("entry", (int, float), required=False, minimum=0),
    FieldSpec("stop", (int, float), required=False, minimum=0),
    FieldSpec("defined_risk", bool, required=False),
    FieldSpec("notes", str, required=False),
    # Which model wrote this. Optional; the roster assigns one per seat when it
    # is absent. When present it lets the adversary rule bite exactly.
    FieldSpec("model", str, required=False),
)

_INSTRUMENT_SPECS = (
    FieldSpec("kind", str, choices=INSTRUMENT_KINDS),
    FieldSpec("symbol", str),
    FieldSpec("venue", str, required=False),
    FieldSpec("outcome", str, required=False),
)

_EVIDENCE_SPECS = (
    FieldSpec("key", str),
    FieldSpec("kind", str),
    FieldSpec("source", str),
    FieldSpec("as_of", (str, datetime)),
    FieldSpec("url", str, required=False),
)

_MIN_THESIS_CHARS = 40
_MIN_INVALIDATION_CHARS = 20


def parse_ticket(doc: Mapping[str, Any], *, where: str = "ticket") -> Ticket:
    problems = check_fields(doc, _TICKET_SPECS, where=where)
    if problems:
        raise ValidationError(problems, where=where)

    problems = check_fields(doc["instrument"], _INSTRUMENT_SPECS, where=f"{where}:instrument")
    if problems:
        raise ValidationError(problems, where=where)

    extra: list[str] = []
    if len(doc["thesis"].strip()) < _MIN_THESIS_CHARS:
        extra.append(f"thesis: needs at least {_MIN_THESIS_CHARS} characters of actual reasoning")
    if len(doc["invalidation"].strip()) < _MIN_INVALIDATION_CHARS:
        extra.append(
            f"invalidation: needs at least {_MIN_INVALIDATION_CHARS} characters; "
            "an idea you cannot be wrong about is not a trade"
        )
    if doc["max_gate"] is not True:
        extra.append("max_gate: must be true; every capital action is Max-gated")

    instrument = Instrument(
        kind=doc["instrument"]["kind"],
        symbol=doc["instrument"]["symbol"],
        venue=doc["instrument"].get("venue", ""),
        outcome=doc["instrument"].get("outcome", ""),
    )
    if instrument.kind == "prediction_market" and not instrument.outcome:
        extra.append("instrument.outcome: required for a prediction_market ticket")

    defined_risk = bool(doc.get("defined_risk", instrument.kind in ("prediction_market", "option")))
    entry = _as_float(doc.get("entry"))
    stop = _as_float(doc.get("stop"))
    if not defined_risk and doc["size_hint_pct"] > 0 and (entry is None or stop is None):
        extra.append(
            "entry/stop: an undefined-risk ticket asking for size must declare both, "
            "otherwise Codex cannot convert % risk into notional"
        )
    if entry is not None and stop is not None:
        if entry == stop:
            extra.append("stop: equals entry, which implies infinite size")
        elif doc["direction"] == "long" and stop > entry:
            extra.append("stop: above entry on a long")
        elif doc["direction"] == "short" and stop < entry:
            extra.append("stop: below entry on a short")

    evidence: list[Evidence] = []
    for i, item in enumerate(doc["evidence"]):
        bad = check_fields(item, _EVIDENCE_SPECS, where=f"{where}:evidence[{i}]")
        if bad:
            extra.extend(bad)
            continue
        if "value" not in item:
            extra.append(f"evidence[{i}]: missing 'value'")
            continue
        evidence.append(
            Evidence(
                key=item["key"],
                kind=item["kind"],
                value=item["value"],
                source=item["source"],
                as_of=parse_instant(item["as_of"], field=f"evidence[{i}].as_of"),
                url=item.get("url", ""),
            )
        )

    if extra:
        raise ValidationError(extra, where=where)

    catalyst_at = (
        parse_instant(doc["catalyst_at"], field="catalyst_at") if doc.get("catalyst_at") else None
    )

    return Ticket(
        id=doc["id"],
        created_at=parse_instant(doc["created_at"], field="created_at"),
        source_seats=tuple(doc["source_seats"]),
        instrument=instrument,
        direction=doc["direction"],
        theme=doc["theme"],
        thesis=doc["thesis"].strip(),
        catalyst=doc["catalyst"].strip(),
        catalyst_at=catalyst_at,
        invalidation=doc["invalidation"].strip(),
        horizon=doc["horizon"],
        size_hint_pct=float(doc["size_hint_pct"]),
        confidence=int(doc["confidence"]),
        evidence=tuple(evidence),
        sources=tuple(doc["sources"]),
        rails_check=doc["rails_check"],
        max_gate=True,
        entry=entry,
        stop=stop,
        defined_risk=defined_risk,
        notes=doc.get("notes", ""),
        raw=doc,
    )


def load_ticket(path: str | Path) -> Ticket:
    return parse_ticket(load_document(path), where=str(path))


def load_tickets(directory: str | Path) -> list[Ticket]:
    """Load every *.ticket.yaml / *.ticket.json under `directory`, sorted by id."""
    directory = Path(directory)
    found: list[Ticket] = []
    for path in sorted(directory.rglob("*.ticket.*")):
        if path.suffix in (".yaml", ".yml", ".json"):
            found.append(load_ticket(path))
    found.sort(key=lambda t: t.id)
    return found


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
