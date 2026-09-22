"""Seat adapters: turn registered sources into `Evidence`.

Each adapter belongs to a seat and returns the same `Evidence` objects a
hand-written ticket carries, so a fetched fact and a typed one are
indistinguishable downstream and both face the same freshness gate.

Nothing here writes. `base.READ_ONLY_POST` is the single allowlisted mutating
verb and exists only because Hyperliquid's read endpoint takes a body; see
`tests/test_boundary.py`, which pins that allowlist and asserts every request
payload comes from a declared read-only set.
"""

from __future__ import annotations

from . import cboe, edgar, fred, hyperliquid, polymarket
from .base import FetchError, FetchResult, evidence, fetch_json, fetch_text

# seat -> the adapter modules that serve it, for `python -m desk fetch`.
BY_SEAT = {
    "Odds": (polymarket,),
    "Chain": (hyperliquid,),
    "Pulse": (cboe,),
    "Shadow": (edgar,),
    "Ledger": (fred,),
}

__all__ = [
    "BY_SEAT",
    "FetchError",
    "FetchResult",
    "cboe",
    "edgar",
    "evidence",
    "fetch_json",
    "fetch_text",
    "fred",
    "hyperliquid",
    "polymarket",
]
