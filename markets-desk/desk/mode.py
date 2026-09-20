"""The desk policy file: what is armed, what is capped, what is stale.

`MODE.md` in the old desk was prose, which meant Rails re-read it and re-decided
every session. `MODE.yaml` is the same doctrine expressed so the risk engine can
apply it identically every time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from .loader import FieldSpec, ValidationError, check_fields, load_document, parse_instant

MODES = ("halt", "research_only", "paper", "live_confirm")
EXECUTIONS = ("research_packs_only", "paper_sheets", "broker_sheets")


@dataclass(frozen=True)
class Theme:
    """A correlation bucket. Members share one cap because they share one risk."""

    id: str
    cap_pct: float
    members: tuple[str, ...]
    note: str = ""

    def covers(self, symbol: str) -> bool:
        needle = symbol.strip().lower()
        for member in self.members:
            pattern = member.strip().lower()
            if pattern.endswith("*"):
                if needle.startswith(pattern[:-1]):
                    return True
            elif needle == pattern:
                return True
        return False


@dataclass(frozen=True)
class EventWindow:
    """A scheduled catalyst that suppresses risk around it.

    A window only binds instruments that can actually gap on the print. An
    empty `applies_to_kinds` means every kind, which is the safe default; the
    narrower form exists because "flat into the Wednesday PMI" is incoherent
    advice for a defined-risk binary that resolves in December.
    """

    id: str
    starts_at: datetime
    ends_at: datetime
    overnight_risk_pct: float
    max_pct_around_event: float
    note: str = ""
    applies_to_kinds: tuple[str, ...] = ()
    applies_to_themes: tuple[str, ...] = ()

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return start < self.ends_at and end > self.starts_at

    def binds(self, instrument_kind: str, theme_id: str) -> bool:
        if self.applies_to_kinds and instrument_kind not in self.applies_to_kinds:
            return False
        if self.applies_to_themes and theme_id not in self.applies_to_themes:
            return False
        return True


@dataclass(frozen=True)
class Venue:
    """An execution surface and whether the desk may format orders for it."""

    id: str
    enabled: bool
    live: bool
    note: str = ""


@dataclass(frozen=True)
class Mode:
    """Parsed, validated desk policy."""

    mode: str
    execution: str
    updated_at: datetime
    portfolio_heat_pct: float
    single_name_pct: float
    default_theme_pct: float
    conviction_ladder: dict[int, float]
    themes: tuple[Theme, ...]
    event_windows: tuple[EventWindow, ...]
    venues: dict[str, Venue]
    staleness_hours: dict[str, float]
    required_seats: tuple[str, ...] = ()
    require_challenge: bool = False
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    # -- lookups ---------------------------------------------------------
    def theme_for(self, symbol: str) -> Theme | None:
        """First theme whose membership covers `symbol`.

        Order in MODE.yaml is significant: put the tightest bucket first.
        """
        for theme in self.themes:
            if theme.covers(symbol):
                return theme
        return None

    def theme_by_id(self, theme_id: str) -> Theme | None:
        for theme in self.themes:
            if theme.id == theme_id:
                return theme
        return None

    def cap_for_theme(self, theme_id: str | None) -> float:
        theme = self.theme_by_id(theme_id) if theme_id else None
        return theme.cap_pct if theme else self.default_theme_pct

    def max_age(self, evidence_kind: str) -> timedelta | None:
        hours = self.staleness_hours.get(evidence_kind)
        if hours is None:
            hours = self.staleness_hours.get("default")
        return timedelta(hours=hours) if hours is not None else None

    def venue(self, venue_id: str) -> Venue | None:
        return self.venues.get(venue_id)

    @property
    def trading_halted(self) -> bool:
        return self.mode == "halt"


_MODE_SPECS = (
    FieldSpec("schema_version", int, minimum=2, maximum=2),
    FieldSpec("mode", str, choices=MODES),
    FieldSpec("execution", str, choices=EXECUTIONS),
    FieldSpec("updated_at", (str, datetime)),
    FieldSpec("caps", dict),
    FieldSpec("conviction_ladder", dict),
    FieldSpec("themes", list, required=False, item_kind=dict),
    FieldSpec("event_windows", list, required=False, item_kind=dict),
    FieldSpec("venues", dict, required=False),
    FieldSpec("staleness_hours", dict, required=False),
    FieldSpec("required_seats", list, required=False, item_kind=str),
    FieldSpec("require_challenge", bool, required=False),
)

_CAP_SPECS = (
    FieldSpec("portfolio_heat_pct", (int, float), minimum=0, maximum=100),
    FieldSpec("single_name_pct", (int, float), minimum=0, maximum=100),
    FieldSpec("default_theme_pct", (int, float), minimum=0, maximum=100),
)


def parse_mode(doc: Mapping[str, Any], *, where: str = "MODE.yaml") -> Mode:
    problems = check_fields(doc, _MODE_SPECS, where=where)
    if problems:
        raise ValidationError(problems, where=where)

    caps = doc["caps"]
    problems = check_fields(caps, _CAP_SPECS, where=f"{where}:caps")
    if problems:
        raise ValidationError(problems, where=where)

    ladder: dict[int, float] = {}
    for key, value in doc["conviction_ladder"].items():
        try:
            level = int(key)
        except (TypeError, ValueError):
            raise ValidationError([f"conviction_ladder key {key!r} is not an integer"], where=where)
        if not 1 <= level <= 5:
            raise ValidationError([f"conviction_ladder level {level} outside 1..5"], where=where)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
            raise ValidationError(
                [f"conviction_ladder[{level}] must be a fraction in 0..1, got {value!r}"], where=where
            )
        ladder[level] = float(value)
    missing_levels = sorted({1, 2, 3, 4, 5} - ladder.keys())
    if missing_levels:
        raise ValidationError(
            [f"conviction_ladder missing level(s) {missing_levels}"], where=where
        )

    themes: list[Theme] = []
    for i, entry in enumerate(doc.get("themes") or []):
        bad = check_fields(
            entry,
            (
                FieldSpec("id", str),
                FieldSpec("cap_pct", (int, float), minimum=0, maximum=100),
                FieldSpec("members", list, item_kind=str, min_items=1),
                FieldSpec("note", str, required=False),
            ),
            where=f"{where}:themes[{i}]",
        )
        if bad:
            raise ValidationError(bad, where=where)
        themes.append(
            Theme(
                id=entry["id"],
                cap_pct=float(entry["cap_pct"]),
                members=tuple(entry["members"]),
                note=entry.get("note", ""),
            )
        )
    duplicate = _first_duplicate(t.id for t in themes)
    if duplicate:
        raise ValidationError([f"duplicate theme id {duplicate!r}"], where=where)

    windows: list[EventWindow] = []
    for i, entry in enumerate(doc.get("event_windows") or []):
        bad = check_fields(
            entry,
            (
                FieldSpec("id", str),
                FieldSpec("starts_at", (str, datetime)),
                FieldSpec("ends_at", (str, datetime)),
                FieldSpec("overnight_risk_pct", (int, float), minimum=0, maximum=100),
                FieldSpec("max_pct_around_event", (int, float), minimum=0, maximum=100),
                FieldSpec("note", str, required=False),
                FieldSpec("applies_to_kinds", list, required=False, item_kind=str),
                FieldSpec("applies_to_themes", list, required=False, item_kind=str),
            ),
            where=f"{where}:event_windows[{i}]",
        )
        if bad:
            raise ValidationError(bad, where=where)
        starts = parse_instant(entry["starts_at"], field=f"event_windows[{i}].starts_at")
        ends = parse_instant(entry["ends_at"], field=f"event_windows[{i}].ends_at")
        if ends <= starts:
            raise ValidationError(
                [f"event_windows[{i}] ({entry['id']}): ends_at must be after starts_at"], where=where
            )
        windows.append(
            EventWindow(
                id=entry["id"],
                starts_at=starts,
                ends_at=ends,
                overnight_risk_pct=float(entry["overnight_risk_pct"]),
                max_pct_around_event=float(entry["max_pct_around_event"]),
                note=entry.get("note", ""),
                applies_to_kinds=tuple(entry.get("applies_to_kinds") or ()),
                applies_to_themes=tuple(entry.get("applies_to_themes") or ()),
            )
        )

    venues: dict[str, Venue] = {}
    for venue_id, entry in (doc.get("venues") or {}).items():
        bad = check_fields(
            entry,
            (
                FieldSpec("enabled", bool),
                FieldSpec("live", bool),
                FieldSpec("note", str, required=False),
            ),
            where=f"{where}:venues.{venue_id}",
        )
        if bad:
            raise ValidationError(bad, where=where)
        venues[venue_id] = Venue(
            id=venue_id,
            enabled=bool(entry["enabled"]),
            live=bool(entry["live"]),
            note=entry.get("note", ""),
        )

    staleness: dict[str, float] = {}
    for kind, hours in (doc.get("staleness_hours") or {}).items():
        if not isinstance(hours, (int, float)) or isinstance(hours, bool) or hours <= 0:
            raise ValidationError(
                [f"staleness_hours.{kind} must be a positive number of hours, got {hours!r}"],
                where=where,
            )
        staleness[str(kind)] = float(hours)

    # A live-confirm desk with no venue armed is coherent (research packs only),
    # but a desk claiming to write broker sheets with every venue dark is not.
    if doc["execution"] == "broker_sheets" and not any(v.enabled for v in venues.values()):
        raise ValidationError(
            ["execution is 'broker_sheets' but no venue is enabled"], where=where
        )

    return Mode(
        mode=doc["mode"],
        execution=doc["execution"],
        updated_at=parse_instant(doc["updated_at"], field="updated_at"),
        portfolio_heat_pct=float(caps["portfolio_heat_pct"]),
        single_name_pct=float(caps["single_name_pct"]),
        default_theme_pct=float(caps["default_theme_pct"]),
        conviction_ladder=ladder,
        themes=tuple(themes),
        event_windows=tuple(windows),
        venues=venues,
        staleness_hours=staleness,
        required_seats=tuple(doc.get("required_seats") or ()),
        require_challenge=bool(doc.get("require_challenge", False)),
        raw=doc,
    )


def load_mode(path: str | Path) -> Mode:
    return parse_mode(load_document(path), where=str(path))


def _first_duplicate(values) -> str | None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None
