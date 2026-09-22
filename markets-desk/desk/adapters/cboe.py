"""Pulse: gamma exposure computed from the CBOE delayed chain.

The desk previously read GEX off a dashboard and got a figure frozen at the
previous Friday's expiry. The number looked ordinary; only its `as_of` gave it
away, and the dashboard published none.

So this adapter computes GEX itself. The arithmetic is not the point — owning
the timestamp is. If the payload carries no timestamp, the fetch fails rather
than stamping the data with the wall clock, because a chain that cannot say
when it was true is precisely the input that caused the original problem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from .base import FetchError, FetchResult, evidence, fetch_json, first_number

CHAIN_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json"
SOURCE_ID = "cboe_delayed_chain"

_EXCHANGE_TZ = ZoneInfo("America/New_York")
_CONTRACT_MULTIPLIER = 100

# ROOT + YYMMDD + C|P + strike in thousandths, e.g. SPXW260921C06800000
_OSI = re.compile(r"^(?P<root>[A-Z]+)(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})(?P<cp>[CP])(?P<strike>\d{8})$")


@dataclass(frozen=True)
class Contract:
    strike: float
    is_call: bool
    gamma: float
    open_interest: float
    expiry: date | None = None

    @property
    def signed_gamma(self) -> float:
        """Dealer-convention sign: long gamma from calls, short from puts."""
        return self.gamma if self.is_call else -self.gamma


def parse_contract(row: Mapping[str, Any]) -> Contract | None:
    """Read one chain row, preferring explicit fields over the symbol.

    Upstream shapes drift. Explicit `strike`/`option_type` are used when
    present; otherwise the OSI-style symbol is parsed. A row missing gamma or
    open interest contributes nothing and is skipped rather than zeroed, so a
    partial chain does not silently read as flat positioning.
    """
    gamma = first_number(row, ("gamma",))
    open_interest = first_number(row, ("open_interest", "openInterest", "oi"))
    if gamma is None or open_interest is None:
        return None

    strike = first_number(row, ("strike", "strike_price"))
    raw_type = str(row.get("option_type") or row.get("type") or "").upper()
    is_call = raw_type.startswith("C") if raw_type else None
    expiry: date | None = None

    symbol = str(row.get("option") or row.get("symbol") or "")
    match = _OSI.match(symbol)
    if match:
        if strike is None:
            strike = int(match.group("strike")) / 1000.0
        if is_call is None:
            is_call = match.group("cp") == "C"
        try:
            expiry = date(2000 + int(match.group("yy")), int(match.group("mm")), int(match.group("dd")))
        except ValueError:
            expiry = None

    if strike is None or is_call is None:
        return None
    return Contract(strike=strike, is_call=is_call, gamma=gamma,
                    open_interest=open_interest, expiry=expiry)


def gex_by_strike(contracts: Iterable[Contract], spot: float) -> dict[float, float]:
    """Dollar gamma per 1% move, per strike.

    gamma x OI x multiplier x spot^2 x 1%, calls positive and puts negative.
    This is the common naive-dealer convention: it assumes dealers are long
    call gamma and short put gamma, which is a simplification, not a fact
    about anyone's book. It is useful for locating walls and the flip, and
    should not be read as a measured dealer position.
    """
    scale = _CONTRACT_MULTIPLIER * spot * spot * 0.01
    buckets: dict[float, float] = {}
    for contract in contracts:
        buckets[contract.strike] = buckets.get(contract.strike, 0.0) + (
            contract.signed_gamma * contract.open_interest * scale
        )
    return buckets


def gamma_flip(buckets: Mapping[float, float]) -> float | None:
    """Strike where cumulative GEX crosses zero, by linear interpolation.

    A proxy, not a repricing: a true flip level recomputes every gamma at each
    candidate spot. This walks strikes low to high and finds where the running
    total changes sign, which is close enough to locate the level and cheap
    enough to run every session.
    """
    strikes = sorted(buckets)
    if not strikes:
        return None
    running = 0.0
    previous_strike: float | None = None
    previous_total = 0.0
    for strike in strikes:
        running += buckets[strike]
        if previous_strike is not None and (previous_total < 0 <= running or previous_total > 0 >= running):
            span = running - previous_total
            if span == 0:
                return strike
            weight = -previous_total / span
            return round(previous_strike + weight * (strike - previous_strike), 2)
        previous_strike, previous_total = strike, running
    return None


def _parse_timestamp(payload: Mapping[str, Any]) -> datetime | None:
    raw = payload.get("timestamp") or payload.get("last_updated")
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    for candidate in (text, text.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        # CBOE publishes exchange-local time without an offset.
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=_EXCHANGE_TZ)
    return None


def fetch_gex(symbol: str = "_SPX", *, expiry: date | None = None) -> FetchResult:
    """Fetch the chain and reduce it to the handful of levels Pulse quotes."""
    url = CHAIN_URL.format(symbol=symbol)
    try:
        payload = fetch_json(url)
    except FetchError as exc:
        return FetchResult(SOURCE_ID, ok=False, error=str(exc))
    if not isinstance(payload, Mapping):
        return FetchResult(SOURCE_ID, ok=False, error="unexpected chain payload")

    as_of = _parse_timestamp(payload)
    if as_of is None:
        return FetchResult(
            SOURCE_ID, ok=False,
            error="chain carries no timestamp; refusing to stamp it with the wall clock",
        )

    data = payload.get("data") if isinstance(payload.get("data"), Mapping) else payload
    spot = first_number(data, ("current_price", "close", "last"))
    rows = data.get("options")
    if spot is None or not isinstance(rows, list):
        return FetchResult(SOURCE_ID, ok=False, error="chain missing spot or options array")

    contracts = [c for c in (parse_contract(r) for r in rows if isinstance(r, Mapping)) if c]
    if expiry is not None:
        contracts = [c for c in contracts if c.expiry == expiry]
    if not contracts:
        return FetchResult(SOURCE_ID, ok=False, error="no usable contracts in chain")

    buckets = gex_by_strike(contracts, spot)
    total = sum(buckets.values())
    calls = {s: v for s, v in buckets.items() if v > 0}
    puts = {s: v for s, v in buckets.items() if v < 0}

    source = f"CBOE delayed chain ({symbol}), computed"
    items = [
        evidence("spot", "price", spot, source=source, as_of=as_of, url=url),
        evidence("total_gex", "options_greeks", round(total, 2),
                 source=source, as_of=as_of, url=url),
        evidence("contracts_used", "options_greeks", len(contracts),
                 source=source, as_of=as_of, url=url),
    ]
    flip = gamma_flip(buckets)
    if flip is not None:
        items.append(evidence("gamma_flip", "options_greeks", flip,
                              source=source, as_of=as_of, url=url))
    if calls:
        items.append(evidence("call_wall", "options_greeks", max(calls, key=calls.get),
                              source=source, as_of=as_of, url=url))
    if puts:
        items.append(evidence("put_wall", "options_greeks", min(puts, key=puts.get),
                              source=source, as_of=as_of, url=url))
    return FetchResult(SOURCE_ID, ok=True, evidence=items, raw={"spot": spot, "buckets": buckets})


def positioning_read(result: FetchResult) -> str:
    """One line for the pack. Sign of GEX, plus where the flip sits."""
    total = result.by_key("total_gex")
    spot = result.by_key("spot")
    flip = result.by_key("gamma_flip")
    if total is None or spot is None:
        return "GEX: no read"
    billions = float(total.value) / 1e9
    regime = (
        "positive gamma — dealers dampen moves, expect mean reversion"
        if billions > 0
        else "negative gamma — dealers amplify moves, expect trend and gaps"
    )
    line = f"GEX {billions:+.2f}bn per 1%: {regime}"
    if flip is not None:
        distance = (float(spot.value) - float(flip.value)) / float(spot.value)
        line += f"; flip near {flip.value} ({distance:+.1%} from spot)"
    return line
