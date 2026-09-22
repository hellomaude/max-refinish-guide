"""The connector manifest: what each seat depends on, asserted.

The connector audit found six connectors half-attached with nothing
noticing, and `docs/CONNECTORS.md` could only advise. This is the mechanism:
each seat declares the registry sources it needs, `validate` refuses a
manifest naming a source the registry does not have, and — when a preflight
report is on file — names any seat whose dependency was dark at the last
probe. A seat with a dark dependency should be known to be blind before it
files, not after.

MCP connectors are listed for the box's benefit and are not checked here;
the package cannot see the client that hosts a seat.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .loader import ValidationError


@dataclass(frozen=True)
class SeatDeps:
    seat: str
    mcp: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class Manifest:
    seats: Mapping[str, SeatDeps]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def check_registry(self, registry_ids: Iterable[str]) -> list[str]:
        known = set(registry_ids)
        out: list[str] = []
        for seat, deps in self.seats.items():
            for sid in deps.sources:
                if sid not in known:
                    out.append(f"connectors: {seat} depends on {sid!r}, which is not in sources.yaml")
        return out

    def dark_seats(self, health: Mapping[str, str]) -> list[str]:
        """Seats with a dependency that was not `ok` or `degraded` at last probe."""
        out: list[str] = []
        for seat, deps in self.seats.items():
            dark = [s for s in deps.sources if health.get(s, "unprobed") not in ("ok", "degraded")]
            if dark:
                out.append(f"{seat}: dark dependency {dark} — files blind until it is back")
        return out


def parse_manifest(doc: Mapping[str, Any], *, where: str = "connectors") -> Manifest:
    if doc.get("schema_version") != 1:
        raise ValidationError(["schema_version must be 1"], where=where)
    seats_doc = doc.get("seats")
    if not isinstance(seats_doc, dict) or not seats_doc:
        raise ValidationError(["seats: required mapping"], where=where)
    seats: dict[str, SeatDeps] = {}
    problems: list[str] = []
    for seat, spec in seats_doc.items():
        if not isinstance(spec, dict):
            problems.append(f"seats.{seat}: expected a mapping")
            continue
        mcp = spec.get("mcp", [])
        sources = spec.get("sources", [])
        if not isinstance(mcp, list) or not isinstance(sources, list):
            problems.append(f"seats.{seat}: mcp and sources must be lists")
            continue
        seats[str(seat)] = SeatDeps(
            seat=str(seat), mcp=tuple(str(m) for m in mcp), sources=tuple(str(s) for s in sources)
        )
    if problems:
        raise ValidationError(problems, where=where)
    return Manifest(seats=seats, raw=doc)


def load_manifest(path: str | Path) -> Manifest:
    path = Path(path)
    return parse_manifest(json.loads(path.read_text(encoding="utf-8")), where=str(path))


def latest_health(preflight_dir: str | Path) -> dict[str, str]:
    """source_id -> state from the newest preflight report, or {}."""
    directory = Path(preflight_dir)
    if not directory.exists():
        return {}
    reports = sorted(directory.glob("*.json"))
    if not reports:
        return {}
    try:
        payload = json.loads(reports[-1].read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return {row["source_id"]: row["state"] for row in payload.get("sources", []) if "source_id" in row}
