"""Ledger: macro series from FRED.

Free key, no MCP connector, and nothing in the vendor stack replaces it — the
rates and PMI spine every macro ticket leans on lives here.
"""

from __future__ import annotations

import os
from datetime import datetime, time, timezone
from typing import Any, Mapping

from .base import FetchError, FetchResult, evidence, fetch_json

OBSERVATIONS = "https://api.stlouisfed.org/fred/series/observations"
SOURCE_ID = "fred"

# The handful Ledger actually quotes, so a seat does not have to remember ids.
SERIES = {
    "10y": "DGS10",
    "2y": "DGS2",
    "2s10s": "T10Y2Y",
    "real_10y": "DFII10",
    "breakeven_10y": "T10YIE",
    "fed_funds": "DFF",
    "cpi_yoy": "CPIAUCSL",
    "unemployment": "UNRATE",
    "financial_conditions": "NFCI",
}


def fetch_series(series_id: str, *, limit: int = 2) -> FetchResult:
    """Latest observations for one series, newest first.

    `as_of` is the observation date, not the fetch time. A monthly print is
    weeks old the day you read it and should be judged against the tolerance
    for its kind, not flattered by a fresh timestamp.
    """
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        return FetchResult(SOURCE_ID, ok=False, error="FRED_API_KEY is unset")

    url = (
        f"{OBSERVATIONS}?series_id={series_id}&api_key={key}"
        f"&file_type=json&sort_order=desc&limit={limit}"
    )
    try:
        payload = fetch_json(url)
    except FetchError as exc:
        # Never let the key reach a log line or a ticket.
        return FetchResult(SOURCE_ID, ok=False, error=str(exc).replace(key, "<redacted>"))

    observations = payload.get("observations") if isinstance(payload, Mapping) else None
    if not isinstance(observations, list) or not observations:
        return FetchResult(SOURCE_ID, ok=False, error=f"no observations for {series_id}")

    public_url = f"https://fred.stlouisfed.org/series/{series_id}"
    items = []
    previous: float | None = None
    for index, observation in enumerate(observations):
        if not isinstance(observation, Mapping):
            continue
        raw = observation.get("value")
        # FRED marks missing prints with ".", which is not zero.
        if raw in (None, ".", ""):
            continue
        try:
            value = float(raw)
            observed_on = datetime.fromisoformat(str(observation["date"]))
        except (TypeError, ValueError, KeyError):
            continue
        as_of = datetime.combine(observed_on.date(), time(0, 0), tzinfo=timezone.utc)
        if index == 0:
            items.append(evidence(series_id, "macro_print", value,
                                  source=f"FRED {series_id}", as_of=as_of, url=public_url))
        else:
            previous = value

    if not items:
        return FetchResult(SOURCE_ID, ok=False, error=f"{series_id}: no numeric observation")
    if previous is not None:
        latest = float(items[0].value)
        items.append(evidence(
            f"{series_id}_change", "macro_print", round(latest - previous, 4),
            source=f"FRED {series_id} (latest less prior)",
            as_of=items[0].as_of, url=public_url,
        ))
    return FetchResult(SOURCE_ID, ok=True, evidence=items, raw=observations)


def fetch_named(name: str, **kwargs: Any) -> FetchResult:
    """Fetch by the desk's shorthand, e.g. "2s10s"."""
    series_id = SERIES.get(name, name)
    return fetch_series(series_id, **kwargs)
