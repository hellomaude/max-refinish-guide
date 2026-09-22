"""Chain: funding and open interest from Hyperliquid's read endpoint.

This is the primary funding/OI source for one reason: `/info` needs no key and
enforces no geo restriction, so it works from a box that Binance and Bybit
refuse. Chasing access to a blocked venue was never going to be the answer.

Funding on Hyperliquid is hourly. Annualising it (x24x365) makes it comparable
to the 8-hour venues Chain used to quote, and the adapter reports both so
nobody has to remember which convention a number is in.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .base import FetchError, FetchResult, evidence, fetch_json, first_number, now_utc

INFO_URL = "https://api.hyperliquid.xyz/info"
SOURCE_ID = "hyperliquid_info"

# Every request body this adapter is permitted to send. All are reads.
# tests/test_boundary.py asserts nothing outside this set is ever sent.
READ_ONLY_REQUESTS = ("metaAndAssetCtxs", "meta", "allMids", "fundingHistory")

_HOURS_PER_YEAR = 24 * 365


def _pairs(payload: Any) -> Iterable[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Zip the universe metadata with the parallel asset-context array."""
    if not isinstance(payload, list) or len(payload) < 2:
        return []
    meta, contexts = payload[0], payload[1]
    universe = meta.get("universe") if isinstance(meta, Mapping) else None
    if not isinstance(universe, list) or not isinstance(contexts, list):
        return []
    return [
        (asset, context)
        for asset, context in zip(universe, contexts)
        if isinstance(asset, Mapping) and isinstance(context, Mapping)
    ]


def fetch_funding_oi(coins: Iterable[str] = ("BTC", "ETH")) -> FetchResult:
    """Mark price, hourly funding and open interest for the named perps."""
    wanted = {c.upper() for c in coins}
    try:
        payload = fetch_json(INFO_URL, body={"type": READ_ONLY_REQUESTS[0]})
    except FetchError as exc:
        return FetchResult(SOURCE_ID, ok=False, error=str(exc))

    as_of = now_utc()
    items = []
    seen: set[str] = set()
    for asset, context in _pairs(payload):
        name = str(asset.get("name", "")).upper()
        if name not in wanted:
            continue
        seen.add(name)
        mark = first_number(context, ("markPx", "midPx", "oraclePx"))
        funding = first_number(context, ("funding",))
        open_interest = first_number(context, ("openInterest",))

        if mark is not None:
            items.append(evidence(f"{name}_mark", "price", mark,
                                  source="Hyperliquid /info", as_of=as_of, url=INFO_URL))
        if funding is not None:
            items.append(evidence(f"{name}_funding_hourly", "funding_oi", funding,
                                  source="Hyperliquid /info", as_of=as_of, url=INFO_URL))
            items.append(evidence(
                f"{name}_funding_apr", "funding_oi",
                round(funding * _HOURS_PER_YEAR, 6),
                source="Hyperliquid /info (annualised from hourly)",
                as_of=as_of, url=INFO_URL,
            ))
        if open_interest is not None:
            items.append(evidence(f"{name}_open_interest", "funding_oi", open_interest,
                                  source="Hyperliquid /info", as_of=as_of, url=INFO_URL))

    missing = sorted(wanted - seen)
    if not items:
        return FetchResult(SOURCE_ID, ok=False,
                           error=f"no asset contexts returned for {sorted(wanted)}")
    return FetchResult(
        SOURCE_ID, ok=True, evidence=items, raw=payload,
        error=f"no context for {missing}" if missing else "",
    )


def crowding_read(result: FetchResult, coin: str = "BTC") -> str:
    """Chain's one-line positioning call, from funding alone.

    Deliberately coarse. Funding says what longs are paying, not where price
    goes, and a three-way read is about as much as the signal supports.
    """
    item = result.by_key(f"{coin.upper()}_funding_apr")
    if item is None:
        return f"{coin}: no funding read"
    apr = float(item.value)
    if apr > 0.30:
        return f"{coin}: crowded long (funding {apr:.1%} APR) — continuation is paying to exist"
    if apr < -0.10:
        return f"{coin}: shorts paying (funding {apr:.1%} APR) — squeeze fuel, not a trend"
    return f"{coin}: funding calm ({apr:.1%} APR) — positioning is not the story"
