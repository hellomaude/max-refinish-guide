"""Shared HTTP plumbing for the seat adapters.

Every adapter returns `Evidence` — the same object a hand-written ticket
carries — so a fetched fact and a typed one are indistinguishable downstream
and both go through the same freshness gate.

## On POST

`READ_ONLY_POST` exists because Hyperliquid's read endpoint takes a POST body.
The invariant the desk actually wants is "no mutating request", not "no POST",
so the boundary test allowlists this module for the verb and separately asserts
that every request body an adapter sends comes from a declared read-only set.
PUT, PATCH and DELETE stay banned outright, everywhere, with no allowlist.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ..ticket import Evidence

# Allowlisted read-only verb. See the module docstring and tests/test_boundary.py.
READ_ONLY_POST = "POST"

USER_AGENT = os.environ.get("DESK_USER_AGENT", "Max Motif max@maxmotif.com")

# SEC asks for <=10 req/s across all your machines and will block an IP that
# ignores it. Everything else here is politeness rather than policy.
_MIN_INTERVAL_SECONDS = {
    "data.sec.gov": 0.15,
    "efts.sec.gov": 0.15,
    "www.deribit.com": 0.5,
    "gamma-api.polymarket.com": 1.0,
    "clob.polymarket.com": 0.6,
}
_last_call: dict[str, float] = {}


class FetchError(Exception):
    """An adapter could not get what it went for."""


@dataclass
class FetchResult:
    """What an adapter brings back.

    `ok=False` is a normal outcome, not an exception to swallow: a seat that
    cannot reach its source should produce a ticket without that evidence and
    let Rails refuse it, rather than substituting a stale or guessed number.
    """

    source_id: str
    ok: bool
    evidence: list[Evidence] = field(default_factory=list)
    error: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw: Any = None

    def by_key(self, key: str) -> Evidence | None:
        for item in self.evidence:
            if item.key == key:
                return item
        return None

    def as_ticket_evidence(self) -> list[dict[str, Any]]:
        """Serialised for pasting straight into a ticket file."""
        return [
            {
                "key": e.key,
                "kind": e.kind,
                "value": e.value,
                "source": e.source,
                "as_of": e.as_of.isoformat(),
                **({"url": e.url} if e.url else {}),
            }
            for e in self.evidence
        ]


def _throttle(url: str) -> None:
    host = urllib.parse.urlparse(url).netloc
    interval = _MIN_INTERVAL_SECONDS.get(host)
    if not interval:
        return
    elapsed = time.monotonic() - _last_call.get(host, 0.0)
    if elapsed < interval:
        time.sleep(interval - elapsed)
    _last_call[host] = time.monotonic()


def fetch_json(
    url: str,
    *,
    body: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 15.0,
    retries: int = 2,
) -> Any:
    """GET, or POST when `body` is given. Returns parsed JSON.

    Retries only on transient conditions — a timeout, a 5xx, or a 429. A 4xx is
    a fact about the request and retrying it just burns the rate limit.
    """
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        **(headers or {}),
    }
    data = None
    method = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
        method = READ_ONLY_POST

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        _throttle(url)
        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
            return json.loads(payload.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            transient = exc.code == 429 or 500 <= exc.code < 600
            if not transient or attempt == retries:
                raise FetchError(f"{url}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError) as exc:
            last_error = exc
            if attempt == retries:
                raise FetchError(f"{url}: {type(exc).__name__}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise FetchError(f"{url}: response was not JSON") from exc
        time.sleep(0.5 * (2**attempt))
    raise FetchError(f"{url}: {last_error}")


def fetch_text(url: str, *, timeout: float = 15.0) -> str:
    """Plain GET returning text, for the sources that do not serve JSON."""
    _throttle(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError) as exc:
        raise FetchError(f"{url}: {type(exc).__name__}: {exc}") from exc


def evidence(
    key: str,
    kind: str,
    value: Any,
    *,
    source: str,
    as_of: datetime,
    url: str = "",
) -> Evidence:
    """Build an Evidence record, normalising the instant to UTC."""
    if as_of.tzinfo is None:
        raise FetchError(f"{key}: as_of must carry a timezone")
    return Evidence(key=key, kind=kind, value=value, source=source,
                    as_of=as_of.astimezone(timezone.utc), url=url)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def first_number(mapping: Mapping[str, Any], names: Sequence[str]) -> float | None:
    """First parseable number under any of `names`.

    Upstream JSON shapes drift — a field is a string one week and a float the
    next, or gets renamed. Adapters tolerate that rather than crashing a
    morning session over it.
    """
    for name in names:
        if name not in mapping:
            continue
        raw = mapping[name]
        if raw is None or isinstance(raw, bool):
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None
