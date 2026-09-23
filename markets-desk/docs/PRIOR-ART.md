# Prior art — what to take, what to skip

Nine repositories assessed 2026-09-22 against one question: does this make the
markets desk better, or is it adjacent software that merely looks relevant?

Star counts below come from page scrapes and some looked implausible, so they
are not cited. Licence, what the thing actually is, and fit are the criteria.

## The finding that decides most of it

**Four of the nine are AGPL-3.0; a fifth requires a commercial licence.** For a
product studio, AGPL on a dependency you *build on and deploy* obliges you to
release your source. That is a business decision, not a technical one, and it
disqualifies several otherwise interesting repos from being anything more than
reading material.

The four permissively licensed ones are, not coincidentally, the four worth
anything here.

| Repo | Licence | Verdict |
|---|---|---|
| anthropics/financial-services | Apache 2.0 | **Take the patterns** |
| kestra-io/kestra | Apache 2.0 | **Maybe — for cadence** |
| yetone/cumora | MIT | Maybe — for fleet coordination |
| lidge-jun/opencodex | MIT | Only if quota-bound |
| Open-Dev-Society/OpenStock | AGPL-3.0 | Skip |
| koala73/worldmonitor | AGPL-3.0 | Skip the code, skim the source list |
| isair/jarvis | commercial licence required | Skip |
| AppFlowy-IO/AppFlowy | AGPLv3 | Not relevant |
| Leantime/leantime | AGPLv3 | Not relevant |

---

## Take: anthropics/financial-services

*"Reference agents, skills, and data connectors for the financial-services
workflows we see most."* Apache 2.0.

The most useful thing on the list, but **not for its agents.** Those target
sell-side and buy-side deal work — pitch decks, DCF and LBO models, IC memos,
KYC screening, GL reconciliation. None of that is a proprietary trading desk.

What is worth taking is the **plumbing**:

**1. `.mcp.json` as a committed artifact.** The repo centralises eleven data
connectors in
`plugins/vertical-plugins/financial-analysis/.mcp.json` and shares them across
plugins. That is precisely the gap in this desk: connectors currently live in
account settings, invisible to the repo, which is how six of them ended up
stuck in `connect_incomplete` without anything noticing. A committed connector
manifest is reviewable, diffable, and can be asserted against.

Its eleven also overlap hard with what `docs/CONNECTORS.md` recommends and what
is already half-attached: **Daloopa, Morningstar, S&P Global, FactSet, Moody's,
MT Newswires, Aiera, LSEG, PitchBook, Chronograph, Egnyte/Box.**

**2. Skills as markdown, authored once and synced.** Vertical plugins hold the
canonical skill; agent bundles get copies. The desk's seat briefs
(`BRIEF-GROK.md`, `HANDOFF-CODEX.md`) are ad-hoc markdown by comparison — this
is a better shape for them, and it is the shape Cowork and the Managed Agents
API already consume.

**3. `managed-agent-cookbooks/<slug>/agent.yaml`.** A deployment spec per agent.
If the Grok Bot fleet ever moves off its own box, this is the format to move it
into rather than inventing one.

**Concretely worth doing:** lift the `.mcp.json` pattern into
`codex-feed/connectors.json`, and have `desk validate` assert that every
connector a seat depends on is present in it. That closes the loop between
`docs/CONNECTORS.md` (advice) and reality (what is actually attached).

---

## Maybe: kestra-io/kestra

*"Event Driven Orchestration & Scheduling Platform for Mission Critical
Applications."* Apache 2.0, open-core with an Enterprise Edition. Java, YAML
workflows, Docker or Kubernetes.

**Real fit for a real gap.** The desk's cadence lives in prose — weekdays 07:00,
09:45, 12:30, 13:15, Monday 08:00, weekend crypto — and nothing enforces it.
Nothing retries a failed fetch, and nothing tells you a session was skipped.
Kestra would run `preflight → fetch → challenge → stamp → pack` as a scheduled
workflow with run history and failure alerting.

**But be honest about the cost.** It is a JVM service wanting Docker and a
database, on a one-person box. `cron` plus the existing CLI gets most of the
way, and the CLI already exits non-zero when a source is dark.

**Take it if** you want run history and to be told when a session failed rather
than discovering it at the open. **Skip it if** cron plus `preflight --strict`
is enough, which for now it probably is.

---

## Maybe: yetone/cumora

*"Where agent teams gather. Cross-platform team chat where AI agents are
first-class participants alongside humans."* MIT. BYOA supports Claude Code and
Codex.

The most interesting answer to a problem this desk has not solved: **the fleet
coordinates through nothing formal.** Seats file reports into a directory, which
is durable and auditable but not conversational — there is no place for Jev to
ask Chain a question, or for Rails to push back on Odds in the open.

Cumora is chat where agents are participants, with Kanban and calendars, and
agents can run on your own machine. That maps onto the Markets Desk and Codex
Feed channels the handoff describes.

**Reservations:** young project, and adopting it means moving fleet
coordination into someone else's product. The report contract in
`desk/report.py` deliberately makes a seat's output a file precisely so no chat
platform is load-bearing. Worth a look; not urgent, and not a replacement for
the file contract.

---

## Only if quota-bound: lidge-jun/opencodex

*"Universal provider proxy for OpenAI Codex & Claude Code — use any LLM with
Codex CLI, App, SDK, and Claude Code."* MIT, TypeScript/Bun.

One narrow use: if you want **Grok to run as a Codex-compatible agent** rather
than as a separate fleet writing files, this is the router that would let it.
Also does account pooling with quota-aware switching.

**Against it:** it inserts a proxy between you and every model — one more thing
that can be down at 06:30 on a Monday, and one more place a request can be
silently rewritten. The desk's whole design is about removing hidden steps
between a fact and a decision. Adopt only if you are actually hitting quota
limits, which is a real reason and the only one here.

---

## Skip: Open-Dev-Society/OpenStock

*"An open-source alternative to expensive market platforms. Track real-time
prices, set personalized alerts, and explore detailed company insights."*
AGPL-3.0. Next.js 15, MongoDB, Finnhub + TradingView widgets.

It is a **retail watchlist app**, not a library. There is no component here to
import — you would fork a web product and maintain it. AGPL-3.0 then obliges
source release on anything you deploy from it.

The only transferable item is **Finnhub** as a data source, and you can use
Finnhub directly without taking the app. Worth adding to
`codex-feed/sources.yaml` as a Ledger fallback if FMP stays unfinished.

---

## Skip the code: koala73/worldmonitor

*"Real-time global intelligence dashboard — AI-powered news aggregation,
geopolitical monitoring, and infrastructure tracking."* AGPL-3.0-only, with
separate commercial licensing available. TypeScript, Tauri, deck.gl.

A **situational-awareness dashboard**, which is a presentation layer. The desk's
problem has never been presentation; it is provenance and sizing.

**One thing worth skimming:** its attributed source list across geopolitics,
energy, climate, aviation and cyber. Wire's calendar is thin, and there may be
feeds there worth registering in `sources.yaml`. Read the list, take no code.

---

## Skip: isair/jarvis

*"A 100% private AI voice assistant that lives on your computer (works
offline)."* Python. Free for personal use, **commercial licence required**.

A local voice assistant. It does no tracking, monitoring or scheduled
collection — the README is explicit that there is no central service, which is
the opposite of what a tracker needs. Nothing here serves the desk, and the
licence rules out commercial use regardless.

---

## Not relevant: AppFlowy, Leantime

**AppFlowy-IO/AppFlowy** — *"The AI collaborative workspace where you achieve
more without losing control of your data."* AGPLv3, Flutter/Rust. A
self-hostable Notion alternative.

**Leantime/leantime** — *"A goals focused project management system for
non-project managers."* AGPLv3, PHP, with a JSON-RPC API and self-hosting.

Both are competent tools for **running a studio** — notes, wikis, projects,
goals. Neither has anything to do with a markets desk: no market data, no risk,
no research contract. If you want them, want them for Max Motif's project
management, and assess them against that, not this.

---

## What this changes

One concrete action falls out: **commit a connector manifest.** Everything else
here is either a maybe with a real cost, or adjacent software.

The manifest is worth doing because it fixes a failure this desk already had —
six connectors half-attached and nothing noticing — and because
`docs/CONNECTORS.md` currently gives advice with no mechanism behind it.

---

## Update 2026-09-23

Routine re-check of the nine, plus a search for new projects. Method: each
repository page was fetched directly on 2026-09-23 and the licence read from
the page. Release dates are as the release pages show them. Nothing below
was taken from a search-engine summary unless it says so.

### The nine: no licence change, no verdict change

| Repo | Licence on 2026-09-23 | Changed? |
|---|---|---|
| anthropics/financial-services | Apache 2.0 | no; README still ships `plugins/vertical-plugins/financial-analysis/.mcp.json` |
| kestra-io/kestra | Apache 2.0 | no |
| yetone/cumora | MIT | no |
| lidge-jun/opencodex | MIT | no |
| Open-Dev-Society/OpenStock | AGPL-3.0 | no; the page now spells out that deploying "as a web service" triggers source release |
| koala73/worldmonitor | AGPL-3.0-only, commercial licence offered | no |
| isair/jarvis | free for personal use, commercial by arrangement | no |
| AppFlowy-IO/AppFlowy | AGPLv3 | no |
| Leantime/leantime | AGPL-3.0, with a plugin-directory exception | no |

No archive or deprecation banner on any of the nine. All nine verdicts stand.
The "one concrete action" from the original assessment is done:
`codex-feed/connectors.json` exists and `desk validate` asserts against it.

### New projects that touch a seat

Found by searching for research desks, insider-filing readers,
prediction-market tooling and GEX calculators released since roughly
June 2026. Only permissively licensed, read-only projects are listed; the
AGPL ones found are named at the end so nobody re-discovers them.

**Shadow (Form 4, 13F)**

- **dgunning/edgartools** — MIT. Python library: "Read and analyze SEC EDGAR
  filings in Python. 10-K, 8-K, XBRL financials, Form 3/4/5, 13F, ADV".
  Latest release v5.58.0 on 2026-09-11; v5.51.0 notes a 2.7x speedup on
  Forms 3/4/5 parsing and a 13F unit-ambiguity warning
  ([releases](https://github.com/dgunning/edgartools/releases)). Not new
  (2022), but the most complete permissive parser for exactly the forms
  Shadow reads. **Candidate cross-check** for `desk/adapters/edgar.py`; the
  desk's taste is stdlib plus PyYAML, so this is a question for Max, not a
  dependency to add.
- **LuxAlgo/market-trackers** — MIT code, CC0 data. TypeScript pipeline over
  "congress trades, insider filings, 13F holdings, government contracts,
  lobbying, short-sale volume" with an MCP server; ingests Forms 3/4/5 and
  13F-HR ([repo](https://github.com/LuxAlgo/market-trackers)). Weeks old and
  small; skim the source list, take no code yet.

**Odds (Polymarket)**

- **nahrek/polyledger** — MIT. "A resumable indexer for Polymarket market
  metadata and on-chain trade data, backed by DuckDB." Reads CLOB and Gamma
  plus Polygon `OrderFilled` events; read-only, places no orders
  ([repo](https://github.com/nahrek/polyledger), last commit shown
  2026-09-02). **Maybe**: it is the only permissive way found to get a
  resolved market's full trade history, which Gamma does not serve. It
  needs a Polygon HyperSync endpoint, which is one more upstream.
- **simonlin1212/globalpercent** — Apache-2.0. Reference code, not a
  library: zero-auth reads of Gamma `/markets`, CLOB `/prices-history` and
  `/midpoint`, and Kalshi `/events` and `/markets?series_ticker=`; documents
  Kalshi's 2026-06 move of price fields to `*_dollars`
  ([repo](https://github.com/simonlin1212/globalpercent)). Worth reading
  before any Kalshi adapter is written.

**Pulse (GEX from the CBOE delayed chain)**

- **Darthreign/gex-dashboard** — MIT. Plotly Dash GEX/DEX dashboard for
  SPX/NDX/SPY/QQQ reading the same
  `cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json` the desk
  registers, no key ([repo](https://github.com/Darthreign/gex-dashboard)).
  An application, and the desk's rule is to compute GEX itself; useful only
  as a second implementation to check `desk/adapters/cboe.py` against.
- **itsfabtrading/Gex-Multi** — Apache-2.0, with `cboe_data.py` and
  `gamma_exposure.py` vendored under MIT from GMestreM/gex_data
  ([repo](https://github.com/itsfabtrading/Gex-Multi)). Same use: a
  reference implementation of gamma flip and call/put walls.

**Research-desk frameworks**

- **TauricResearch/TradingAgents** — Apache-2.0. v0.5.0 (released 18 Sep;
  the page omits the year, and the repo's news list places it in September
  2026) adds point-in-time data: "SEC EDGAR serves US company statements as
  they stood on the run's date: a period that has ended but has not been
  filed is not served" and "Dated tools take the run's date from graph
  state, so an omitted or later date cannot reach a vendor"
  ([release](https://github.com/TauricResearch/TradingAgents/releases/tag/v0.5.0)).
  **Skip the code** (it is a trading framework with an execution path);
  the point-in-time rule is the same `as_of` doctrine this desk enforces,
  and the release note is a good statement of it.

**Found and disqualified (AGPL-3.0):** gammagrid/gammagrid (GEX dashboard on
yfinance, [repo](https://github.com/gammagrid/gammagrid)),
rufeng0411/Nova-TradingAgent, COLARDYNIT/quorumtrading. The last two were
seen in the search pass and not fetched directly.

**Seen, not assessed:** kyky2347/ALTA (Apache-2.0, "research-only
multi-agent trading platform", from the search pass only),
simonlin1212/Vibe-Research (MIT; full research flow is A-share only),
carrotly-ai/disclosures (Apache-2.0 EDGAR/GLEIF library plus MCP server,
near-zero adoption), jsconiers/traders-edge-mcp (MIT, key-less CBOE plus
TreasuryDirect MCP server, some tools need a broker session).

### What this changes

Nothing in the verdict table. Two questions for Max, carried in the PR:
whether edgartools becomes Shadow's cross-check, and whether polyledger is
worth an upstream for resolved-market history on Odds.
