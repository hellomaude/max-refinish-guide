"""Odds: Polymarket Gamma and CLOB, read paths only.

Gamma is the catalogue — slugs, questions, resolution text, last prices. CLOB
is the book — midpoint and depth per outcome token. Both read paths are
unauthenticated; placing an order needs a signed wallet this desk does not have
and must never acquire.

The adapter deliberately surfaces `resolution_text` as its own piece of
evidence. The WKND-002 argument turned on wording — "signed into law in 2026"
is not "Senate passage" and not "an SEC exemption" — and a seat cannot
rules-lawyer a market whose terms it never fetched.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from .base import FetchError, FetchResult, evidence, fetch_json, first_number, now_utc

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

SOURCE_ID = "polymarket_gamma"


def _decode_list(raw: Any) -> list[Any]:
    """Gamma returns some arrays as JSON-encoded strings. Accept either form."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _outcome_prices(market: Mapping[str, Any]) -> dict[str, float]:
    names = [str(n) for n in _decode_list(market.get("outcomes"))]
    prices = _decode_list(market.get("outcomePrices"))
    paired: dict[str, float] = {}
    for name, price in zip(names, prices):
        try:
            paired[name] = float(price)
        except (TypeError, ValueError):
            continue
    return paired


def fetch_market(slug: str, *, outcome: str | None = None) -> FetchResult:
    """Everything Odds needs about one market, by slug."""
    url = f"{GAMMA}/markets?slug={slug}"
    try:
        payload = fetch_json(url)
    except FetchError as exc:
        return FetchResult(SOURCE_ID, ok=False, error=str(exc))

    markets = payload if isinstance(payload, list) else payload.get("data") or []
    if not markets:
        return FetchResult(SOURCE_ID, ok=False, error=f"no market matched slug {slug!r}")
    market = markets[0]
    as_of = now_utc()

    items = []
    prices = _outcome_prices(market)
    for name, price in prices.items():
        if outcome and name.lower() != outcome.lower():
            continue
        items.append(
            evidence(
                f"price_{name.lower()}", "price", price,
                source=f"Polymarket Gamma ({slug})", as_of=as_of, url=url,
            )
        )

    # Resolution wording is the whole ballgame on a policy market, so it is
    # evidence in its own right rather than a note in the thesis.
    text = (market.get("description") or market.get("question") or "").strip()
    if text:
        items.append(
            evidence("resolution_text", "legislative", text,
                     source=f"Polymarket Gamma ({slug})", as_of=as_of, url=url)
        )

    for key, names, kind in (
        ("volume", ("volume", "volumeNum", "volume24hr"), "price"),
        ("liquidity", ("liquidity", "liquidityNum"), "order_book"),
    ):
        value = first_number(market, names)
        if value is not None:
            items.append(
                evidence(key, kind, value, source=f"Polymarket Gamma ({slug})",
                         as_of=as_of, url=url)
            )

    end_date = market.get("endDate") or market.get("end_date_iso")
    if end_date:
        items.append(
            evidence("resolution_date", "legislative", str(end_date),
                     source=f"Polymarket Gamma ({slug})", as_of=as_of, url=url)
        )

    return FetchResult(SOURCE_ID, ok=True, evidence=items, raw=market)


def token_ids(market: Mapping[str, Any]) -> list[str]:
    return [str(t) for t in _decode_list(market.get("clobTokenIds"))]


def fetch_midpoint(token_id: str) -> FetchResult:
    """CLOB midpoint for one outcome token.

    Gamma's `outcomePrices` is a last-trade figure and can be stale on a thin
    market; the midpoint is what you would actually transact near.
    """
    url = f"{CLOB}/midpoint?token_id={token_id}"
    try:
        payload = fetch_json(url)
    except FetchError as exc:
        return FetchResult("polymarket_clob", ok=False, error=str(exc))
    mid = first_number(payload if isinstance(payload, dict) else {}, ("mid", "midpoint"))
    if mid is None:
        return FetchResult("polymarket_clob", ok=False, error=f"no midpoint in response for {token_id}")
    return FetchResult(
        "polymarket_clob", ok=True,
        evidence=[evidence("clob_midpoint", "price", mid, source="Polymarket CLOB",
                           as_of=now_utc(), url=url)],
        raw=payload,
    )


def fetch_book(token_id: str) -> FetchResult:
    """Top of book and spread — the difference between a quote and a fill."""
    url = f"{CLOB}/book?token_id={token_id}"
    try:
        payload = fetch_json(url)
    except FetchError as exc:
        return FetchResult("polymarket_clob", ok=False, error=str(exc))

    def _best(side: str, pick) -> float | None:
        levels = payload.get(side) or [] if isinstance(payload, dict) else []
        prices = [
            float(level["price"])
            for level in levels
            if isinstance(level, Mapping) and "price" in level
        ]
        return pick(prices) if prices else None

    best_bid = _best("bids", max)
    best_ask = _best("asks", min)
    as_of = now_utc()
    items = []
    if best_bid is not None:
        items.append(evidence("best_bid", "order_book", best_bid,
                              source="Polymarket CLOB", as_of=as_of, url=url))
    if best_ask is not None:
        items.append(evidence("best_ask", "order_book", best_ask,
                              source="Polymarket CLOB", as_of=as_of, url=url))
    if best_bid is not None and best_ask is not None:
        items.append(evidence("spread", "order_book", round(best_ask - best_bid, 4),
                              source="Polymarket CLOB", as_of=as_of, url=url))
    if not items:
        return FetchResult("polymarket_clob", ok=False, error="empty book")
    return FetchResult("polymarket_clob", ok=True, evidence=items, raw=payload)
