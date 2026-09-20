"""The data-source registry and its preflight prober.

The Monday checklist in the handoff carried three lines that were really the
same line: a CoinGlass key that was never set, two venues geo-blocked from the
box, and an options feed frozen at Friday's expiry. Those are not notes for a
human to remember — they are the health state of the data layer, and the desk
should refuse to size an idea that leans on a source it cannot reach.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .loader import FieldSpec, ValidationError, check_fields, load_document

# Health states, worst last. The prober reports the state; MODE and Rails
# decide what each one costs a ticket.
OK = "ok"
DEGRADED = "degraded"
NO_AUTH = "no_auth"
GEO_BLOCKED = "geo_blocked"
UNREACHABLE = "unreachable"

USER_AGENT = os.environ.get("DESK_USER_AGENT", "Max Motif max@maxmotif.com")


@dataclass(frozen=True)
class Source:
    """One upstream the desk reads from."""

    id: str
    seat: str
    kind: str
    url: str
    auth_env: str = ""
    cost: str = "free"
    geo_risk: bool = False
    fallbacks: tuple[str, ...] = ()
    note: str = ""
    expect_status: tuple[int, ...] = (200,)

    @property
    def needs_auth(self) -> bool:
        return bool(self.auth_env)

    @property
    def has_auth(self) -> bool:
        return bool(self.auth_env) and bool(os.environ.get(self.auth_env, "").strip())


@dataclass
class Health:
    """The result of probing one source."""

    source_id: str
    state: str
    status_code: int | None = None
    latency_ms: float | None = None
    detail: str = ""
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def usable(self) -> bool:
        return self.state in (OK, DEGRADED)

    def row(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "state": self.state,
            "status_code": self.status_code,
            "latency_ms": None if self.latency_ms is None else round(self.latency_ms, 1),
            "detail": self.detail,
            "checked_at": self.checked_at.isoformat(),
        }


_SOURCE_SPECS = (
    FieldSpec("id", str),
    FieldSpec("seat", str),
    FieldSpec("kind", str),
    FieldSpec("url", str),
    FieldSpec("auth_env", str, required=False),
    FieldSpec("cost", str, required=False),
    FieldSpec("geo_risk", bool, required=False),
    FieldSpec("fallbacks", list, required=False, item_kind=str),
    FieldSpec("note", str, required=False),
    FieldSpec("expect_status", list, required=False, item_kind=int),
)


def parse_sources(doc: Mapping[str, Any], *, where: str = "sources.yaml") -> list[Source]:
    entries = doc.get("sources")
    if not isinstance(entries, list):
        raise ValidationError(["missing top-level 'sources' list"], where=where)
    sources: list[Source] = []
    for i, entry in enumerate(entries):
        problems = check_fields(entry, _SOURCE_SPECS, where=f"{where}:sources[{i}]")
        if problems:
            raise ValidationError(problems, where=where)
        sources.append(
            Source(
                id=entry["id"],
                seat=entry["seat"],
                kind=entry["kind"],
                url=entry["url"],
                auth_env=entry.get("auth_env", ""),
                cost=entry.get("cost", "free"),
                geo_risk=bool(entry.get("geo_risk", False)),
                fallbacks=tuple(entry.get("fallbacks") or ()),
                note=entry.get("note", ""),
                expect_status=tuple(entry.get("expect_status") or (200,)),
            )
        )
    known = {s.id for s in sources}
    dangling = [
        f"{s.id} -> {fb}" for s in sources for fb in s.fallbacks if fb not in known
    ]
    if dangling:
        raise ValidationError(
            ["fallback points at an unknown source: " + ", ".join(dangling)], where=where
        )
    return sources


def load_sources(path: str | Path) -> list[Source]:
    return parse_sources(load_document(path), where=str(path))


def probe(source: Source, *, timeout: float = 12.0) -> Health:
    """Check one source without asking it for anything expensive.

    Deliberately crude: a single GET against a cheap endpoint. The prober's job
    is to distinguish "we cannot read this" from "we forgot the key" from
    "this venue does not serve our country", which is exactly the distinction
    the old checklist kept re-learning by hand.
    """
    if source.needs_auth and not source.has_auth:
        return Health(
            source.id,
            NO_AUTH,
            detail=f"environment variable {source.auth_env} is unset",
        )

    request = urllib.request.Request(source.url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            latency = (time.monotonic() - started) * 1000
            code = response.getcode()
            state = OK if code in source.expect_status else DEGRADED
            detail = "" if state == OK else f"unexpected status {code}"
            return Health(source.id, state, status_code=code, latency_ms=latency, detail=detail)
    except urllib.error.HTTPError as exc:
        latency = (time.monotonic() - started) * 1000
        if exc.code in source.expect_status:
            return Health(source.id, OK, status_code=exc.code, latency_ms=latency)
        if exc.code in (401, 403) and source.needs_auth:
            return Health(source.id, NO_AUTH, status_code=exc.code, latency_ms=latency,
                          detail="credential rejected")
        # 451 is the explicit legal-block code; 403 from a venue we already
        # flagged as geo-sensitive means the same thing in practice.
        if exc.code == 451 or (exc.code == 403 and source.geo_risk):
            return Health(source.id, GEO_BLOCKED, status_code=exc.code, latency_ms=latency,
                          detail="venue refuses this egress location")
        if exc.code == 429:
            return Health(source.id, DEGRADED, status_code=exc.code, latency_ms=latency,
                          detail="rate limited")
        return Health(source.id, UNREACHABLE, status_code=exc.code, latency_ms=latency,
                      detail=f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        state = GEO_BLOCKED if source.geo_risk else UNREACHABLE
        return Health(source.id, state, detail=f"{type(reason).__name__}: {reason}")
    except (socket.timeout, TimeoutError):
        return Health(source.id, UNREACHABLE, detail=f"timed out after {timeout:.0f}s")
    except ssl.SSLError as exc:
        return Health(source.id, UNREACHABLE, detail=f"TLS failure: {exc}")


def probe_all(sources: Iterable[Source], *, timeout: float = 12.0) -> list[Health]:
    return [probe(source, timeout=timeout) for source in sources]


def resolve_chain(source_id: str, sources: Iterable[Source], health: Iterable[Health]) -> str | None:
    """The first usable source in `source_id`'s fallback chain, or None.

    Walks breadth-first and refuses to revisit, so a pair of sources listing
    each other as fallbacks cannot spin.
    """
    by_id = {s.id: s for s in sources}
    state = {h.source_id: h for h in health}
    seen: set[str] = set()
    queue = [source_id]
    while queue:
        current = queue.pop(0)
        if current in seen or current not in by_id:
            continue
        seen.add(current)
        entry = state.get(current)
        if entry is not None and entry.usable:
            return current
        queue.extend(by_id[current].fallbacks)
    return None


def write_report(health: Iterable[Health], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [h.row() for h in health],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
