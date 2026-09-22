"""The seat report: how a seat hands its work to the desk.

Tickets and challenges had contracts. Seat output did not — `required_seats`
in MODE.yaml checked only that a name was present, never that the seat had
said anything. So a seat could be "available" while having produced nothing.

This is also how a fleet that is not this process becomes a seat. Grok Bot
runs on its own box with its own agents; it joins the desk by writing report
files in this schema, not by exposing an API. Any researcher — another model,
another machine, a person with a text editor — is a seat the moment its output
satisfies this contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .loader import FieldSpec, ValidationError, check_fields, load_document, parse_instant
from .ticket import Evidence

# Evidence kinds that can carry a thesis on their own. Everything else may
# corroborate but not originate — see `has_hard_evidence`.
HARD_KINDS = (
    "price",
    "filing",
    "funding_oi",
    "liquidations",
    "options_greeks",
    "macro_print",
    "order_book",
    "etf_flow",
    "legislative",
)

# Kinds that describe what people are saying rather than what happened.
SOFT_KINDS = ("social", "news", "sentiment")

READS = ("clear", "mixed", "no_read")

# How well-known an idea already is. This is the structured form of the most
# valuable thing a social seat can say, and it is always bad news: an idea that
# is already consensus has less edge left than the author thinks.
CROWDING = ("differentiated", "consensus", "crowded")


@dataclass(frozen=True)
class SeatReport:
    """One seat's output for one session."""

    seat: str
    produced_at: datetime
    read: str
    headline: str
    evidence: tuple[Evidence, ...]
    covers: tuple[str, ...] = ()
    crowding: Mapping[str, str] = field(default_factory=dict)
    excluded_sources: tuple[str, ...] = ()
    unavailable: tuple[str, ...] = ()
    notes: str = ""
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def crowding_for(self, symbol: str) -> str | None:
        needle = symbol.strip().lower()
        for key, value in self.crowding.items():
            if key.strip().lower() == needle:
                return value
        return None

    @property
    def has_read(self) -> bool:
        return self.read != "no_read"

    def for_symbol(self, symbol: str) -> bool:
        needle = symbol.strip().lower()
        return any(c.strip().lower() == needle for c in self.covers)

    def line(self) -> str:
        gap = f" [dark: {', '.join(self.unavailable)}]" if self.unavailable else ""
        return f"{self.seat} ({self.read}): {self.headline}{gap}"


_SPECS = (
    FieldSpec("schema_version", int, minimum=2, maximum=2),
    FieldSpec("seat", str),
    FieldSpec("produced_at", (str, datetime)),
    FieldSpec("read", str, choices=READS),
    FieldSpec("headline", str),
    FieldSpec("evidence", list, item_kind=dict),
    FieldSpec("covers", list, required=False, item_kind=str),
    FieldSpec("crowding", dict, required=False),
    FieldSpec("excluded_sources", list, required=False, item_kind=str),
    FieldSpec("unavailable", list, required=False, item_kind=str),
    FieldSpec("notes", str, required=False),
)

_EVIDENCE_SPECS = (
    FieldSpec("key", str),
    FieldSpec("kind", str),
    FieldSpec("source", str),
    FieldSpec("as_of", (str, datetime)),
    FieldSpec("url", str, required=False),
)

_MIN_HEADLINE = 25


def parse_report(doc: Mapping[str, Any], *, where: str = "report") -> SeatReport:
    problems = check_fields(doc, _SPECS, where=where)
    if problems:
        raise ValidationError(problems, where=where)

    extra: list[str] = []
    headline = doc["headline"].strip()
    if len(headline) < _MIN_HEADLINE:
        extra.append(
            f"headline: needs at least {_MIN_HEADLINE} characters — a read the desk "
            "can act on, not a status word"
        )

    # A seat claiming a clear read on nothing is the failure this contract
    # exists to catch: silence and confidence are different things.
    if doc["read"] == "clear" and not doc["evidence"]:
        extra.append("read: 'clear' requires at least one piece of evidence")
    if doc["read"] == "no_read" and not (doc.get("unavailable") or doc.get("notes")):
        extra.append(
            "read: 'no_read' must say why — list what was unavailable, or explain in notes"
        )

    crowding: dict[str, str] = {}
    for symbol, level in (doc.get("crowding") or {}).items():
        if level not in CROWDING:
            extra.append(
                f"crowding.{symbol}: {level!r} not one of {list(CROWDING)}"
            )
            continue
        crowding[str(symbol)] = level
    unknown = sorted(set(crowding) - {str(c) for c in (doc.get("covers") or [])})
    if unknown:
        extra.append(
            f"crowding: names not in `covers`: {unknown} — assess only what you looked at"
        )

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

    return SeatReport(
        seat=doc["seat"],
        produced_at=parse_instant(doc["produced_at"], field="produced_at"),
        read=doc["read"],
        headline=headline,
        evidence=tuple(evidence),
        covers=tuple(doc.get("covers") or ()),
        crowding=crowding,
        excluded_sources=tuple(doc.get("excluded_sources") or ()),
        unavailable=tuple(doc.get("unavailable") or ()),
        notes=doc.get("notes", ""),
        raw=doc,
    )


def load_report(path: str | Path) -> SeatReport:
    return parse_report(load_document(path), where=str(path))


def load_reports(directory: str | Path) -> dict[str, SeatReport]:
    """Newest report per seat, keyed by seat name.

    A seat may file more than once in a session — Chain re-pulls at 06:30 and
    again at the open — and the desk should act on the current read.
    """
    directory = Path(directory)
    if not directory.exists():
        return {}
    newest: dict[str, SeatReport] = {}
    for path in sorted(directory.rglob("*.report.*")):
        if path.suffix not in (".yaml", ".yml", ".json"):
            continue
        report = load_report(path)
        existing = newest.get(report.seat)
        if existing is None or report.produced_at > existing.produced_at:
            newest[report.seat] = report
    return newest


def load_report_history(
    directory: str | Path, *, seat: str | None = None
) -> list[SeatReport]:
    """Every report on file, oldest first — not just the current read.

    `load_reports` answers "what does the desk know now", which is what gating
    needs. Grading needs the opposite: every call a seat has ever made,
    including the ones it has since revised, because a seat that is scored only
    on its latest word is never scored on being wrong.
    """
    directory = Path(directory)
    if not directory.exists():
        return []
    out: list[SeatReport] = []
    for path in sorted(directory.rglob("*.report.*")):
        if path.suffix not in (".yaml", ".yml", ".json"):
            continue
        report = load_report(path)
        if seat is not None and report.seat.strip().lower() != seat.strip().lower():
            continue
        out.append(report)
    return sorted(out, key=lambda r: r.produced_at)


def has_hard_evidence(evidence: Iterable[Evidence]) -> bool:
    """Whether anything here is a fact about the market rather than about talk.

    Social and news describe attention. Attention moves price and is worth
    watching, but a thesis supported only by what people are saying has no
    falsifiable content — the invalidation would have to be "people stopped
    saying it", which is not a level. So soft evidence corroborates and never
    originates.
    """
    return any(item.kind in HARD_KINDS for item in evidence)


def seats_reporting(reports: Mapping[str, SeatReport]) -> set[str]:
    """Seats that filed something, for MODE.yaml's required_seats gate."""
    return {name for name, report in reports.items() if report.has_read}
