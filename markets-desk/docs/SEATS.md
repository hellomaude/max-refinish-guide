# Seats

Ten seats. Eight find things, one attacks what they found, one sizes it. Codex
turns the survivors into order sheets and Max gates every one.

Every seat files a **report** (`desk/report.py`) each session. That contract is
what makes a seat a seat: a name in `required_seats` is satisfied by a filed
report with a read, not by a process being up. A seat that produces nothing is
`no_read` and must say why.

| Seat | Owns | Files |
|---|---|---|
| Wire | news, calendar, event→ticker mapping | what happened and what is scheduled |
| Ledger | equities, fundamentals, EDGAR, FRED | valuation and macro evidence |
| Chain | crypto funding, OI, liquidations, ETF flows | positioning evidence |
| Odds | prediction markets, resolution rules | mispricing and resolution wording |
| Pulse | options positioning | GEX, walls, flip |
| Shadow | Form 4, 13F | disclosure evidence |
| **Grok** | **social, attention, breaking chatter** | **what is being said, and how loudly** |
| **Jev** | **the case against** | **challenges** |
| Rails | risk caps, stamps | allowances |
| CoS | compression, sequencing | the pack |
| Codex | tickets, prep, execution path | order sheets, Max-gated |

---

## The two rules that shape everything

**Hard evidence originates; soft evidence corroborates.** A ticket asking for
size must rest on at least one fact about the market — a price, a filing, a
funding rate, a greek, a macro print, order-book depth, an ETF flow, a
legislative action. `social`, `news` and `sentiment` may support a thesis but
never carry it, because a thesis built on talk has no falsifiable content: its
invalidation would have to be "people stopped saying it", which is not a level
anyone can watch. Rails enforces this as `soft_evidence_only`.

**Freshness is per-kind.** Every piece of evidence declares when the underlying
fact was true, not when it was fetched. `MODE.yaml` sets the tolerance;
past it, the ticket fails rather than being discounted.

---

## Wire — news and the calendar

**Owns** the mapping from event to instrument. Its real job is not finding
news, it is deciding what the news is *about* in a way another seat can act on.

**Files** scheduled catalysts with times, and the event→ticker/slug mapping.

**Refused if** a catalyst has no date, or an event is filed without naming the
instrument it prices.

**Cadence** weekdays 07:00, with a calendar refresh Monday 08:00.

---

## Ledger — equities, fundamentals, macro

**Owns** the numbers a valuation argument rests on, and the macro spine.

**Files** fundamentals with the filing they came from, and rates / PMI / CPI
with observation dates.

**Refused if** a vendor figure is filed without a primary-source tiebreak
available. When vendors disagree, `sec_companyfacts` decides — XBRL comes from
the filing itself.

**Cadence** weekdays 07:00; macro on print days.

```bash
python -m desk fetch Ledger --series 2s10s --series 10y
```

---

## Chain — crypto positioning

**Owns** funding, open interest, liquidations and ETF flows. Its read is about
*crowding*, not direction.

**Files** funding (hourly and annualised — both, so nobody has to remember the
convention), OI, and the three-way crowding call: crowded long, shorts paying,
or calm.

**Refused if** it reports a funding number without saying which venue and
which interval, or treats a weekend ETF-flow read as confirmation of a weekday
flow.

**Cadence** weekdays 06:30 and again at the cash open. Weekends, since the
crypto sources have no market hours.

```bash
python -m desk fetch Chain --coin BTC --coin ETH
```

Hyperliquid is primary because it needs no key and has no geo gate — it works
from the box Binance and Bybit refuse.

---

## Odds — prediction markets

**Owns** resolution wording. Everything else about a prediction market is
secondary to what the contract actually says.

**Files** the resolution text from the Gamma record (not the market title),
the outcome prices, CLOB midpoint and depth, and the resolution date.

**Refused if** it files a price without the resolution text. The WKND-002
argument turned entirely on wording — "signed into law" is not "Senate
passage" and not "an SEC exemption" — and a seat cannot rules-lawyer terms it
never fetched.

**Cadence** with the session that needs it; depth re-read before any size.

```bash
python -m desk fetch Odds --slug <slug> --outcome No
```

---

## Pulse — options positioning

**Owns** GEX, the walls, the flip. **Computes them itself** from the CBOE
delayed chain rather than reading a dashboard's number.

**Files** total GEX per 1%, gamma flip, call and put wall, contracts used, and
the chain's own timestamp.

**Refused if** the chain carries no timestamp. The adapter fails closed rather
than stamping data with the wall clock — that substitution is what produced a
gamma profile frozen at the previous Friday's expiry, where the number looked
ordinary and only its `as_of` gave it away.

**Cadence** weekdays 06:30 and 09:45. Greeks go stale in 20 hours by policy.

```bash
python -m desk fetch Pulse --symbol _SPX
```

---

## Shadow — disclosures

**Owns** Form 4 and 13F, read against the **primary document**.

**Files** distinct open-market buyers and sellers, notional, and filing count —
counted by owner, not by filing, because one director filing four times is one
opinion.

**Refused if** a cluster is filed from an aggregator's summary. The ownership
XML is the filing; a count either survives contact with it or it does not.

**Cadence** weekdays 07:00; on any 8-K or price move worth explaining.

```bash
python -m desk fetch Shadow --cik <cik> --ticker <ticker>
```

EDGAR wants ≤10 req/s and a User-Agent naming a real contact. `DESK_USER_AGENT`
is not optional here — ignore it and you get a 403 and then a ten-minute block.

---

## Grok — social and attention

### Why the seat exists

Nothing else on the desk can see what is being said in real time. There is no
X reader in the connector directory and no Grok or xAI server either — I
checked. Grok Bot already runs on its own box with native access to that feed,
so it is the only seat that can answer "is anyone talking about this, and since
when".

### It is not a second opinion

The tempting framing — Grok as an independent model double-checking the
theses — is rejected on purpose. Two models agreeing is not evidence, because
their errors correlate through shared training data and shared sources. Two
models disagreeing is not signal either; it is a tie with no tiebreak. Grok
earns its seat on **capability the desk lacks**, not on being a second vote.

### Its standing brief

[`codex-feed/BRIEF-GROK.md`](../codex-feed/BRIEF-GROK.md) is the instruction to
paste into Grok Bot. The short version: its highest-value output is bearish on
the desk's own ideas, so its primary customer is Jev rather than Wire. A social
seat used to find trades is a hype machine — it hands you whatever is loudest,
which is whatever is already priced. Used to check whether an idea is already
crowded, it is a real edge.

### How it connects

Not through an API. Grok files reports into `reports/` in the
`desk/report.py` schema — the same contract every other seat satisfies. A
researcher joins this desk by writing a file, which is why another model,
another machine, or a person with a text editor can all be seats.

```yaml
# reports/2026-09-21-0630-grok.report.yaml
schema_version: 2
seat: Grok
produced_at: 2026-09-21T06:30:00-07:00
read: mixed
headline: Crypto-policy chatter thinning since the cloture vote; no new revival talk
covers: [COIN, HOOD, BTC, clarity-act-signed-2026]
evidence:
  - key: clarity_mentions_7d
    kind: social
    value: "down ~70% vs the week before the vote"
    source: X, aggregate mention count
    as_of: 2026-09-21T06:15:00-07:00
unavailable: []
notes: >-
  No accounts close to the negotiating bloc are signalling a second attempt.
  Absence of chatter, which is weak evidence of absence.
```

### The hard limit on what it can do

Grok's evidence is `social` / `news` / `sentiment` — all soft kinds. **It
cannot originate a sized ticket.** Rails refuses any ticket asking for size
with no hard evidence behind it, and that rule exists precisely so a loud
timeline cannot become a position.

What Grok *can* do, which is valuable: tell Wire an event is being priced
before it shows in the tape, flag that a thesis is consensus rather than
differentiated, and notice when chatter stops — as above, weakly.

**Files** a `crowding` call per covered symbol — `differentiated`, `consensus`
or `crowded` — which is the structured form of its most valuable output and is
always bad news for the ticket. Also `excluded_sources`, since the desk bans
pumper accounts and should see what was filtered rather than only the residue.

**Refused if** it files a `clear` read with no evidence, rates the crowding of
a name it did not look at, or reports volume without a baseline. "Lots of
mentions" is not a number.

**Cadence** weekdays 06:30 with Chain, and on demand when Wire has an event
with no obvious instrument.

**Not in `required_seats`.** Gating the desk on a social feed would be the tail
wagging the dog; Grok being dark should cost the desk nothing.

---

## Jev — the adversary

### Why the seat exists

Every other seat proposes. Each writes up an idea it already likes, having
looked hardest at the evidence that supports it. Rails then checks the *size*
of that idea and never whether it is true. Before Jev, nobody was paid to be
the other side, and the only thing between a confident thesis and a position
was whether someone happened to object in chat.

### The one hard rule

**Jev may not originate a ticket.** A seat that proposes cannot credibly
attack, and a seat that scores its own ideas will always find they were nearly
right. `tests/test_boundary.py` fails the build if "Jev" appears in any
ticket's `source_seats`.

### What a challenge must contain

- **`strongest_counter`** — the other side's best argument, ≥60 characters of
  mechanism. "This seems risky" is refused. Attack the reasoning, the
  liquidity, the exit, or the sizing regime, whichever is weakest.
- **`what_would_change_my_mind`** — checkable. A number, a base rate, a depth
  reading, a filing. An objection nothing could settle is an opinion.
- **`verdict`** — `contest`, `concede`, or `kill`.
- **`confidence_adjustment`** — subtracts or holds, never adds.

A `contest` with a zero adjustment is refused: either it costs the ticket
something or it is a concede. A `concede` with a non-zero adjustment is refused
too — that is the adversary trying to have it both ways.

### The teeth

The adjustment feeds the conviction ladder *before* any cap applies, and the
docked conviction is also the water-filling weight, so a contested ticket loses
twice: on the ladder and on its claim to scarce budget. A `kill` is a hard FAIL.
With `require_challenge: true`, an unchallenged ticket is PENDING at 0%.

### Why it can only subtract

Letting the adversary add conviction would make it a second proposer and reward
it for being agreeable — the failure mode of every review function graded on
throughput. Jev's upside is being right about risk, never about direction.

### Scoring the scorer

`python -m desk score` compares realised expectancy on contested tickets
against the ones Jev cleared: objections that ran materially worse carried
information; contested tickets outperforming means Jev is inverted and taxing
good ideas; no separation means it is costing size without buying anything.

Killed tickets cannot be scored — never taken, so the desk does not get to know
what it avoided. Reported rather than papered over.

**Cadence** between the seats and Rails: after the 07:00 wire, before the 09:45
open pulse. `python -m desk challenge` lists what it owes.

---

## Rails — risk

**Owns** `MODE.yaml`. Since the engine executes that file, Rails no longer
hand-derives sizes; it owns the policy and reviews the stamps.

**Files** the book stamp, and a note on any cap it changed and why.

**Refused if** it edits a cap without saying what changed. A cap edit is a
trade — Max gates it.

**Cadence** Monday 08:00 for the weekly review, and a re-stamp whenever the
tape invalidates a standing gate.

---

## CoS — compression

**Owns** sequencing and the pack. `python -m desk pack` renders what used to be
compressed by hand.

**Files** the pack, and the one-line board status.

**Refused if** it presents a ceiling as a recommendation. Rails' numbers are
ceilings; turning one into "take 0.4%" is the compression error that matters.

---

## Codex — execution path

**Owns** tickets, prep and the Max-gated execution path. Reads
`stamp --json` ceilings, converts % of risk budget to notional, and **writes
the ledger** — including the tickets not taken, since a desk that scores only
its fills cannot see its own selection bias.

Full brief: [`codex-feed/HANDOFF-CODEX.md`](../codex-feed/HANDOFF-CODEX.md).
