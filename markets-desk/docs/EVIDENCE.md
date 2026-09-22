# Evidence

What the literature and practitioner record say about the bets this desk
makes, checked after the fact, and what changed as a result.

**How this was gathered, honestly.** From this session every paper host
(arXiv, SSRN, NBER, ScienceDirect, Springer), every Substack, and Reddit itself
were egress-blocked. What follows is built from search-engine summaries of the
primary sources, not full reads. That is enough to be directional — the
headline numbers are the ones the papers are cited for — but every figure here
should be treated as "reported by the abstract" until someone on the desk box
opens the paper. Practitioner threads are represented by secondary write-ups of
them, not the threads. Where I found nothing, I say nothing.

---

## 1. The social seat — attention is a contrarian signal, and it decays

**The bet.** Grok's most valuable output is the `crowding` call, and
`consensus` is a claim that the edge is gone. The coach grades a `consensus`
call as wrong if the name then worked.

**The evidence supports the bet, and adds a mechanism.**

- Positions opened when r/wallstreetbets attention on a stock is at its peak
  realise **−8.5%** holding-period returns, against a positive average across
  all positions. Attention concentrates smaller retail trades on
  attention-grabbing names and those trades perform worse.
  ([Social media attention and retail investor behavior](https://www.sciencedirect.com/science/article/pii/S1057521924006537),
  [Dumb money?](https://www.sciencedirect.com/science/article/pii/S2405918825000212))
- Google search volume — a direct retail-attention measure — predicts **higher
  prices over the next two weeks and a reversal within the year**.
  ([Da, Engelberg & Gao, *In Search of Attention*, J. Finance 2011](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1364209))
  This is the signature the brief calls "chatter led price": a short pop, then
  a give-back. It is why a `crowded` call should make the desk *smaller* on a
  swing horizon and is nearly irrelevant intraday.
- WSB due-diligence reports predicted returns before the GameStop episode
  (+1.1% two-day, drifting to ~5% over a quarter) and **stopped predicting
  anything after it**, with the decay concentrated in reports pushing
  price-pressure and attention names.
  ([Bradley, Hanousek, Jame & Xiao, *Place Your Bets?*, RFS 2024](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3806065))
  A social signal decays once it is known. The coach's grade is the only
  defence against Grok continuing to be scored as useful after it has stopped
  being so.
- The practitioner consensus, across every secondary write-up found, is the
  same sentence: *by the time a name trends, the move has happened.* Social
  chatter is coincident-to-lagging, bot- and manipulation-heavy, and should
  never be a standalone signal.
  ([Traders Agency guide](https://tradersagency.com/blog/social-media-sentiment-analysis-tools))

**One thing the evidence changes.** Cookson & Niessner find that
**disagreement**, not net sentiment, is the social variable with a
market-behaviour signature — a one-s.d. rise in overnight disagreement is
followed by ~4% more abnormal volume the next day; disagreement from different
information sets drives 2.5–4× more of it than disagreement from different
philosophies.
([*Why Don't We Agree?*, J. Finance 2020](https://ideas.repec.org/r/bla/jfinan/v75y2020i1p173-228.html))
So `consensus` should mean **low dispersion of opinion** — the same argument
repeated back — and never "high volume". Volume rises *with* a move and flags
momentum, not saturation. The brief now says this in §5, and it is exactly the
failure the coach names as "inverted".

---

## 2. The adversary seat — a structured counter beats "be objective"

**The bet.** Jev must file a counter, a mind-change condition and a verdict
before Rails sizes anything; the format is forced.

**The evidence supports the format specifically.**

- Instructing people to *consider the opposite* corrected biased assimilation
  and biased hypothesis-testing **more than instructing them to be fair and
  unbiased** did.
  ([Lord, Lepper & Preston 1984](https://www.semanticscholar.org/paper/Considering-the-opposite:-a-corrective-strategy-for-Lord-Lepper/e71bbae72f8ad78e97c54f5ec88c9af2c70759f2))
  A seat told to be sceptical is not the same as a seat required to write the
  case against.
- Prospective hindsight — assuming the outcome has already happened and
  explaining why — raised the ability to identify reasons for outcomes by
  **~30%** (Mitchell, Russo & Pennington 1989), which is the mechanism Klein's
  premortem formalises.
  ([Alliance for Decision Education](https://alliancefordecisioneducation.org/resources/conducting-a-pre-mortem/))
  `what_would_change_my_mind` is the premortem question in ticket form.

Nothing found argues against it. The risk the ledger already watches for —
Jev taxing good ideas without buying information — is the only failure mode
the literature warns about, and `desk score` reports it.

---

## 3. Shadow — half of all insider trades carry nothing

**The bet.** A cluster of distinct open-market buyers is a signal.

**The evidence says the count was too generous.**

- Insiders who trade in the **same calendar month in each of the prior three
  years** are "routine". Routine trades are **more than half** the universe
  and predict nothing; the opportunistic remainder carries **all** the
  predictive power — ~**82 bp/month** value-weighted abnormal return, versus
  essentially zero for routine — and predicts firm-level news. The most
  informed are local, non-executive insiders at concentrated, poorly-governed
  firms.
  ([Cohen, Malloy & Pomorski, *Decoding Inside Information*, J. Finance 2012](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1692517))
- Clustered purchases are followed by **>2% abnormal returns in the next
  month**, and clustering is greater under low attention and high
  uncertainty. ([Alldredge et al., J. Financial Research 2019](https://onlinelibrary.wiley.com/doi/10.1111/jfir.12172))
  Lakonishok & Lee (2001) put heavy-insider-buying outperformance at ~7.5%
  over twelve months.
  ([IBKR Campus summary](https://ibkrcampus.com/campus/traders-insight/securities/stocks/what-corporate-insider-buying-can-tell-investors-evidence-from-academic-research/))

**What changed.** `desk/adapters/edgar.py` now carries `is_routine()` with the
Cohen–Malloy–Pomorski test and, given owner histories, reports
`opportunistic_buyers` separately and excludes routine buyers from the cluster
read. An unscreened count now says "routine buyers not yet screened" rather
than presenting as a cluster. Fetching each owner's history is a second
submissions call per reporting-owner CIK; that wiring waits for the desk box
because EDGAR was unreachable here.

---

## 4. Odds — a 92.5¢ No is real, thin, and partly a lock-up price

**The bet.** WKND-002: buy No at 92.5 on a market resolving January 2027.
Jev called it short-vol carry with no sizing regime.

**The evidence is mildly for the direction and squarely for Jev's objection.**

- On Polymarket, purchases **at or above 90¢ earn +0.83¢ per dollar**;
  purchases below 10¢ lose 19.3¢. The favourite–longshot bias is robust in
  Crypto and Politics and absent in Sports. 588M trades, 2.48M accounts.
  ([*The Favorite–Longshot Bias in Prediction Markets: Evidence from Polymarket*](https://arxiv.org/html/2609.12878))
  Buying the favourite is the right side. The edge is under a cent.
- Politics markets are **persistently under-confident** — calibration slope
  ~1.45, prices compressed toward 50% — so a favourite is worth more than its
  price at long horizons; the horizon effect is universal (slope 0.99 within
  an hour of resolution, 1.32 beyond a month). Large trades are *more*
  under-confident than small ones.
  ([*Domain-Specific Calibration Dynamics in Prediction Markets*](https://arxiv.org/abs/2602.19520))
- But a near-certain dollar with locked collateral is a **delayed** dollar:
  prices follow P = E[X]·D(τ), and adjusting for the recovered settlement
  discount removes **48–88%** of the apparent under-confidence in
  near-certain contracts. Much of the gap between 92.5 and 100 is the price of
  lock-up, not mispricing.
  ([*When Certainty Is Not Worth It*](https://arxiv.org/abs/2605.31431))

**What changed.** Odds' contract in `docs/SEATS.md` now refuses a ticket at
≥90¢ that does not state the annualised return net of lock-up against a
risk-free alternative for the same tenor. If the number does not clear that
bar, the ticket is a savings account with resolution risk, and Jev was right.

---

## 5. Pulse — GEX is a volatility regime, not a direction

**The bet.** Pulse computes dealer gamma and the flip from the raw chain.

**The evidence supports the number and narrows what it may be used for.**

- Negative ex-ante dealer gamma interacting with illiquidity explains
  **intraday momentum**; positive gamma explains **reversal**. Strongest in
  the least liquid underlyings.
  ([Barbon & Buraschi, *Gamma Fragility*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3725454))
- Hedging demand produces last-30-minute momentum across 60+ futures from
  1974–2020, Sharpe **0.87–1.73**.
  ([Baltussen et al., *Hedging Demand and Market Intraday Momentum*, JFE 2021](https://www.sciencedirect.com/science/article/abs/pii/S0304405X21001598))
- The vendor's own caveat: GEX levels are for scenario-building, not support
  or resistance; the model breaks on unhedged opening prints, regime shifts,
  and headline gaps.
  ([SpotGamma](https://spotgamma.com/gex/))

**What this means for the desk.** A negative-gamma read should widen the
expected range and argue for smaller size or wider stops; it says nothing
about which way. `docs/SEATS.md` already had Pulse filing regime, not
direction; this is the reason.

---

## 6. Chain — funding is a crowding proxy, and the contrarian case is thin

**The bet.** Extreme funding marks crowded positioning.

**The evidence is mostly practitioner, not academic.** Funding-rate *levels*
are predictable (DAR models beat no-change), funding *arbitrage* is well
documented, and every trading guide treats >+0.05%/8h as crowded longs. I did
not find a peer-reviewed result that extreme funding predicts a reversal in
the underlying. Chain's `crowding_read()` should be presented as what it is —
a positioning proxy that becomes an argument for smaller size — and not as a
timing signal. No change made; the contract already frames it that way.
([Predictability of Funding Rates](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5576424),
[Funding rate arbitrage on CEX and DEX](https://www.sciencedirect.com/science/article/pii/S2096720925000818))

---

## 7. What the evidence does *not* support

- **Grok as a reliable reader of X.** Nothing independent found. Every
  article is a how-to from an exchange or a content farm claiming a "15–30
  minute information advantage", with no accuracy figure and no baseline. The
  one concrete data point is a public hallucination episode. This is why the
  report contract demands a source, an `as_of`, and a baseline for every
  volume claim, and why `desk coach` exists: the seat's value is measured, not
  assumed.
- **Any social signal as an originator.** Every result above cuts the same
  way. `soft_evidence_only` stays a hard FAIL.
- **Kestra, cumora, opencodex as proven in this setting.** Assessed on
  licence and fit in `PRIOR-ART.md`; no adoption evidence sought or found.

---

## What changed in the repo because of this

| Where | Change |
|---|---|
| `desk/adapters/edgar.py` | `is_routine()`; opportunistic vs routine buyers reported and read separately |
| `codex-feed/BRIEF-GROK.md` §5 | `consensus` defined by dispersion, `crowded` by position-talk; the volume trap named with the evidence |
| `docs/SEATS.md` Odds | ≥90¢ tickets must state annualised return net of lock-up |
| `docs/SEATS.md` Shadow | routine buyers do not count toward a cluster |
| `desk/coach.py` | the "inverted" finding is now the documented failure mode, not a guess |
