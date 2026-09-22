# Connectors and data sources

Audited 2026-09-20. Connector states change; re-run the audit before trusting
this page, and run `python -m desk preflight` for the HTTP sources.

## The finding

Ten market-data connectors were added to the workspace. Two were usable.
Six sat in `connect_incomplete` — an OAuth flow begun and never finished, which
presents as an installed connector that returns nothing. One needed reconnecting.

More importantly, **all ten served one seat**. The desk has eight seats; six of
the additions landed on Ledger, which was already the best-covered. The four
seats that actually differentiate the desk stayed dark.

| Seat | Needs | Coverage after the additions |
|---|---|---|
| Ledger | equities, fundamentals | six overlapping providers |
| Wire | news, calendar | partial |
| **Chain** | funding, OI, liquidations, ETF flows | prices only |
| **Odds** | Polymarket | none |
| **Pulse** | options positioning | none |
| **Shadow** | Form 4, 13F | none |

## Why six fundamentals providers is worse than two

They will disagree. Vendors differ on restatements, fiscal-period alignment,
adjusted-versus-GAAP, and when a filing lands in their pipeline. A desk with
six sources for one revenue figure has no source for it — someone has to pick,
and if that someone is whichever seat asked first, the number is arbitrary.

Two is the right number: one primary, one for the cross-check, and
`sec_companyfacts` as the tiebreak because XBRL comes from the filing itself.

## Recommended state

**Keep and finish:** FMP (broadest single equity feed) · Bigdata.com (news,
filings, events, and it cites, which the doctrine requires) · Zacks (already
live; estimates and ranks) · Crypto.com (already live; spot reference pricing).

**Add:** Aiera — live events, filings, earnings-call transcripts and an
upcoming-events calendar. Closes Wire's calendar gap, which nothing else here
touches. Alpha Vantage — options chains, SEC filings, FX and commodities under
one key; partially fills Pulse.

**Drop:** Black Diamond (advisor portfolio accounting — wrong product for a
one-person research desk) · FactSet (institutional pricing, redundant against
FMP plus Zacks) · Morningstar (redundant) · Crunchbase (private-company data,
no markets use) · Daloopa (only if KPIs get modelled by hand).

**Hold:** Interactive Brokers. See below.

## Interactive Brokers is a doctrine change, not a connector

IBKR's server carries order-placing tools. Connecting it moves the desk off
`research_packs_only` whether or not anyone intends that, because the capability
is then present in the session and only convention keeps it unused.

The handoff already sets the correct sequence: name the venue in `MODE.yaml`,
then arm it, and keep every order Max-gated. Until that happens, leaving IBKR
unfinished is the safe state, and `tests/test_boundary.py` asserts the policy
has not drifted.

## What no connector fixes

Searched the directory on 2026-09-20 for Polymarket, Kalshi, Unusual Whales,
CoinGlass, Alpaca, Kraken and FRED. None exists. The four dark seats run on
direct HTTP, registered in `codex-feed/sources.yaml` and implemented in
`desk/adapters/` behind `python -m desk fetch <seat>`:

| Seat | Source | Auth | Why this one |
|---|---|---|---|
| Odds | Polymarket Gamma + CLOB reads | none | Free, public, ~60/100 req/min. PublicClient path only |
| Chain | Hyperliquid `/info` | none | Funding and OI with no geo gate — routes around the Binance/Bybit block rather than fighting it |
| Chain | Deribit public | none | DVOL and the crypto options surface; rate-limits unauthenticated callers hard |
| Chain | Farside / SoSoValue | none | Daily spot BTC/ETH ETF flows |
| Pulse | CBOE delayed chain | none | ~15-minute full chain with OI and greeks. Compute GEX yourself |
| Shadow | `data.sec.gov` | none | 10 req/s ceiling, User-Agent naming a real contact is mandatory |
| Ledger | FRED | free key | The macro spine. Nothing in the vendor stack replaces it |

Two notes carried from the old checklist, now encoded as registry state rather
than remembered:

- **CoinGlass** is registered with `auth_env: COINGLASS_API_KEY` and no key set.
  The prober reports `no_auth`, which is the honest answer, instead of the seat
  discovering it mid-session.
- **Binance and Bybit** are registered with `geo_risk: true` and Hyperliquid as
  the fallback. They are in the file so the prober names them, not so anything
  depends on them.

## Why Pulse should compute its own GEX

The old desk read GEX from a dashboard and got a number frozen at the previous
Friday's expiry. The number looked fine; only its `as_of` gave it away, and
the dashboard did not surface one.

Computing from the CBOE delayed chain costs a little arithmetic and buys the
timestamp. `desk/risk.py` then refuses any ticket leaning on greeks older than
20 hours, so the same failure cannot recur silently.

## A name to avoid

"Insider One" in the connector directory is marketing-campaign software, not
insider filings. Shadow's data comes from EDGAR.
