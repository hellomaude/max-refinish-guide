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

---

## Update 2026-09-23

Routine re-check of the direct-HTTP sources and a search for new free ones.
**Method caveat:** the official documentation hosts (sec.gov,
docs.polymarket.com, docs.kalshi.com, finnhub.io, hyperliquid.gitbook.io,
coinalyze.net, alphavantage.co, financialmodelingprep.com) were all
egress-blocked from this session. Every quote below is the search engine's
excerpt of the named official page, not a direct read. Re-run from the box
before changing `sources.yaml`.

### Polymarket: read endpoints still keyless, but the catalogue route is on notice

- **Auth.** "The Gamma API and Data API are fully public, no authentication
  required"; CLOB read endpoints (order book, prices, spreads) are also
  unauthenticated
  ([getting-started/api](https://docs.polymarket.com/getting-started/api)).
- **Gamma pagination.** Keyset endpoints `GET /markets/keyset` and
  `GET /events/keyset` were added 2026-04-10; the offset-based `GET /markets`
  and `GET /events` "remain available but will be deprecated in a future
  release". On 2026-05-14 the keyset maximum `limit` was cut to 100
  ([changelog](https://docs.polymarket.com/changelog)). The Odds adapter
  reads `GET /markets?slug=`, which is the offset family, so this is a
  future break with no date yet.
- **Price history moved.** `GET /v2/prices-history` on
  `data-api.polymarket.com/v2` replaces the CLOB-hosted route; v1 is
  "frozen"; the API returns 429 with `Retry-After`
  ([data-api overview](https://docs.polymarket.com/api-reference/data-api/overview);
  entry date not captured). The adapter does not read price history today.
- **CLOB V2** went live April 2026 and V1 signed orders are no longer
  supported ([v2-migration](https://docs.polymarket.com/v2-migration)).
  Irrelevant to the desk by doctrine, since it never signs.
- **Rate limits** are IP-based and throttled rather than rejected:
  CLOB "/books 50 requests per 10 seconds, /price 100 requests per 10
  seconds, markets/0x 50 requests per 10 seconds"
  ([rate-limits](https://docs.polymarket.com/api-reference/rate-limits)).
  The "~60/100 req/min" figures in `sources.yaml` are not what the page
  says; the Gamma numeric limit was not captured at all.

### Kalshi: a keyless read API the desk does not use

Kalshi publishes "public endpoints that don't require API keys" at
`https://external-api.kalshi.com/trade-api/v2`
([quick start, market data](https://docs.kalshi.com/getting_started/quick_start_market_data)).
Rate limiting is a token bucket where "Most requests cost the default of 10
tokens" and the Basic tier read budget is "200 tokens-per-second"
([rate limits](https://docs.kalshi.com/getting_started/rate_limits)).
WebSockets need an authenticated session. Price fields moved to
`*_dollars` in June 2026 (see globalpercent in `docs/PRIOR-ART.md`).
This is the obvious second prediction-market source for Odds: free, no key,
no wallet, and a different venue's resolution text to compare against
Polymarket's. Whether Odds should read it is a question for Max.

### Chain: numbers to pin

- **Hyperliquid.** "REST requests share an aggregated weight limit of 1200
  per minute per IP address"; `/info` calls weigh 2 for the light reads and
  20 by default
  ([rate limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits)).
  No change; still no key.
- **Coinalyze.** "The rate limit is 40 API calls per minute per API Key",
  429 with `Retry-After`; free key on sign-up
  ([API doc](https://api.coinalyze.net/v1/doc/)). `sources.yaml` says
  "generous limits"; 40/min is the number.
- **Spot ETF flows.** No official free API found. Farside and SoSoValue
  remain HTML scrapes.

### Pulse, Ledger: the free tiers are thinner than the registry implies

- **Alpha Vantage** free key: "standard usage limit of 25 API requests per
  day" ([support](https://www.alphavantage.co/support/)). As Pulse's chain
  fallback that is one full-chain pull a day at best.
- **FMP** free plan: "250 market data API requests per day", a "trailing
  30 days bandwidth limit of 500MB", about five years of prices and five
  quarters of statements; access was refactored to per-plan endpoint
  restrictions and the legacy v3 endpoints "may not receive regular
  updates" ([pricing](https://site.financialmodelingprep.com/developer/docs/pricing)).
- **Finnhub** (the Ledger fallback the prior-art page suggested): the free
  tier and the `/docs/api/rate-limit` page exist, but the page text was not
  captured. Third parties cite 60 calls/min on the free key; **unverified
  against the page**, so it is not written as a number here. Which of
  quotes, fundamentals, insider transactions and filings are free is also
  unverified.
- **FRED**: free key, no numeric limit found on FRED's own pages; the
  "2 requests per second" line that circulates appears to belong to the
  FRASER API. **Unverified.**
- **CBOE delayed chain JSON**: no official documentation page for the
  `cdn.cboe.com` endpoint was found, and cboe.com's delayed-quotes pages say
  automated extraction is prohibited and IPs may be blocked. The endpoint
  is in use by several open projects (see `docs/PRIOR-ART.md`), but its
  availability is a courtesy, not a contract. Keep the poll interval honest.

### SEC EDGAR: no change

- Rate limit unchanged: "The current maximum request rate is 10 requests
  per second" "regardless of the number of machines used", and a
  User-Agent declaring company and contact
  ([Accessing EDGAR data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)).
- `data.sec.gov` submissions and XBRL APIs "do not require any
  authentication or API keys"; bulk ZIPs republished nightly around 3:00 am
  ET ([EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)).
- Full-text search at `efts.sec.gov` still has no official API page, only
  the UI FAQ. No change found.
- EDGAR Release 26.3 deployed 2026-09-14 covers XBRL taxonomies and filer
  interfaces, nothing on the public data APIs
  ([release notes](https://www.sec.gov/submit-filings/edgar-news-announcements/edgar-release-263)).
  Insider Transactions (Forms 3/4/5) and Form 13F data sets remain
  quarterly; no new bulk dataset was announced.

### What this changes

Nothing today. Three items for `sources.yaml`, proposed as questions in the
PR rather than edited: pin Coinalyze at 40/min and Alpha Vantage at 25/day
in the notes, replace the Polymarket "~60/100 req/min" note with the
documented per-endpoint figures, and decide whether Kalshi's keyless read
API becomes Odds's second source.
