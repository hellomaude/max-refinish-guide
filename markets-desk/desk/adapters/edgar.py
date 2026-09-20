"""Shadow: insider disclosures from EDGAR, read against the primary document.

The weekend pack held a Form 4 cluster at PENDING until someone confirmed it
against the filings themselves rather than an aggregator's summary. That is the
right instinct and this adapter is what makes it cheap: the ownership XML is
the filing, so the count either survives contact with it or it does not.

EDGAR asks for at most 10 requests/second across all your machines and for a
User-Agent naming a real contact. Ignore either and you get a 403 and then a
ten-minute IP block, so `DESK_USER_AGENT` is not optional here.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Mapping

from .base import FetchError, FetchResult, evidence, fetch_json, fetch_text, now_utc

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
SOURCE_ID = "sec_submissions"

# Table I / II transaction codes. P and S are the open-market trades that carry
# signal; A and M are grants and option exercises, which mostly do not.
OPEN_MARKET_BUY = "P"
OPEN_MARKET_SELL = "S"


@dataclass(frozen=True)
class Filing:
    form: str
    filed_on: date
    accession: str
    document: str
    cik: int

    @property
    def url(self) -> str:
        return ARCHIVE.format(
            cik=self.cik, accession=self.accession.replace("-", ""), document=self.document
        )


@dataclass(frozen=True)
class InsiderTrade:
    owner: str
    is_officer: bool
    is_director: bool
    code: str
    shares: float
    price: float | None
    traded_on: date | None

    @property
    def notional(self) -> float | None:
        return None if self.price is None else self.shares * self.price


def recent_filings(cik: int, *, forms: Iterable[str] = ("4",), since: date | None = None) -> list[Filing]:
    """Filing history for one CIK, newest first."""
    url = SUBMISSIONS.format(cik=cik)
    payload = fetch_json(url)
    recent = (payload.get("filings") or {}).get("recent") or {}
    wanted = {f.upper() for f in forms}

    columns = ("form", "filingDate", "accessionNumber", "primaryDocument")
    series = [recent.get(name) or [] for name in columns]
    if not all(isinstance(s, list) for s in series):
        raise FetchError(f"{url}: unexpected submissions shape")

    filings: list[Filing] = []
    for form, filed, accession, document in zip(*series):
        if str(form).upper() not in wanted:
            continue
        try:
            filed_on = date.fromisoformat(str(filed))
        except ValueError:
            continue
        if since and filed_on < since:
            continue
        filings.append(Filing(str(form), filed_on, str(accession), str(document), cik))
    return filings


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def _value(parent: ET.Element | None, path: str) -> str:
    """Form 4 wraps most leaves in a <value> child; tolerate both forms."""
    if parent is None:
        return ""
    node = parent.find(path)
    if node is None:
        return ""
    inner = node.find("value")
    return _text(inner) if inner is not None else _text(node)


def parse_form4(xml_text: str) -> list[InsiderTrade]:
    """Pull the open-market rows out of one ownership document."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise FetchError(f"ownership XML did not parse: {exc}") from exc

    owner_node = root.find("reportingOwner")
    owner = _text(owner_node.find("reportingOwnerId/rptOwnerName")) if owner_node is not None else ""
    relationship = owner_node.find("reportingOwnerRelationship") if owner_node is not None else None
    is_officer = _text(relationship.find("isOfficer")) in ("1", "true") if relationship is not None else False
    is_director = _text(relationship.find("isDirector")) in ("1", "true") if relationship is not None else False

    trades: list[InsiderTrade] = []
    for row in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        amounts = row.find("transactionAmounts")
        code = _value(row.find("transactionCoding"), "transactionCode")
        shares_text = _value(amounts, "transactionShares")
        price_text = _value(amounts, "transactionPricePerShare")
        traded_text = _value(row, "transactionDate")
        try:
            shares = float(shares_text)
        except (TypeError, ValueError):
            continue
        try:
            price = float(price_text) if price_text else None
        except ValueError:
            price = None
        try:
            traded_on = date.fromisoformat(traded_text) if traded_text else None
        except ValueError:
            traded_on = None
        trades.append(InsiderTrade(owner, is_officer, is_director, code, shares, price, traded_on))
    return trades


def _as_instant(day: date) -> datetime:
    """A filing is public from its filing date; treat it as end of that day UTC."""
    return datetime.combine(day, time(23, 59), tzinfo=timezone.utc)


def fetch_insider_cluster(
    cik: int,
    *,
    lookback_days: int = 30,
    ticker: str = "",
) -> FetchResult:
    """Count distinct insiders buying on the open market inside a window.

    A cluster is several *different* people buying, which is why the count is
    of distinct owners rather than of filings — one director filing four times
    is one opinion, not four.
    """
    since = (now_utc() - timedelta(days=lookback_days)).date()
    label = ticker or f"CIK {cik}"
    try:
        filings = recent_filings(cik, forms=("4",), since=since)
    except FetchError as exc:
        return FetchResult(SOURCE_ID, ok=False, error=str(exc))

    if not filings:
        return FetchResult(
            SOURCE_ID, ok=True,
            evidence=[evidence(f"{label}_insider_buyers", "filing", 0,
                               source="SEC EDGAR Form 4", as_of=now_utc(),
                               url=SUBMISSIONS.format(cik=cik))],
            raw=[],
        )

    buys: dict[str, float] = defaultdict(float)
    sells: dict[str, float] = defaultdict(float)
    unread: list[str] = []
    latest = max(f.filed_on for f in filings)

    for filing in filings:
        try:
            trades = parse_form4(fetch_text(filing.url))
        except FetchError:
            unread.append(filing.accession)
            continue
        for trade in trades:
            if not trade.owner:
                continue
            if trade.code == OPEN_MARKET_BUY:
                buys[trade.owner] += trade.notional or 0.0
            elif trade.code == OPEN_MARKET_SELL:
                sells[trade.owner] += trade.notional or 0.0

    as_of = _as_instant(latest)
    source = "SEC EDGAR Form 4 (primary document)"
    items = [
        evidence(f"{label}_insider_buyers", "filing", len(buys),
                 source=source, as_of=as_of, url=SUBMISSIONS.format(cik=cik)),
        evidence(f"{label}_insider_sellers", "filing", len(sells),
                 source=source, as_of=as_of, url=SUBMISSIONS.format(cik=cik)),
        evidence(f"{label}_insider_buy_notional", "filing", round(sum(buys.values()), 2),
                 source=source, as_of=as_of, url=SUBMISSIONS.format(cik=cik)),
        evidence(f"{label}_form4_count", "filing", len(filings),
                 source=source, as_of=as_of, url=SUBMISSIONS.format(cik=cik)),
    ]
    return FetchResult(
        SOURCE_ID, ok=True, evidence=items,
        error=f"{len(unread)} filing(s) unreadable: {unread}" if unread else "",
        raw={"buys": dict(buys), "sells": dict(sells)},
    )


def cluster_read(result: FetchResult, label: str) -> str:
    """Shadow's line. Says plainly when the cluster does not survive the filings."""
    buyers = result.by_key(f"{label}_insider_buyers")
    notional = result.by_key(f"{label}_insider_buy_notional")
    if buyers is None:
        return f"{label}: no Form 4 read"
    count = int(buyers.value)
    if count == 0:
        return f"{label}: no open-market insider buying in the window — the cluster is not there"
    amount = f" totalling ${float(notional.value):,.0f}" if notional else ""
    if count == 1:
        return f"{label}: one insider bought{amount} — one opinion, not a cluster"
    return f"{label}: {count} distinct insiders bought on the open market{amount}"
