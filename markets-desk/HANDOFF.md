# Markets Desk — handoff to the next agent

**From:** Claude (this session) · **To:** whoever picks this up · **Owner:** Max Hahn (Max Motif)
**Written:** Tue 2026-09-22 · **Branch:** `claude/financial-system-codex-grokvot-3ho3jh` · **PR:** hellomaude/max-refinish-guide#1

**Your job:** take the desk from "built and tested against fixtures" to "running on
the desk box, every seat reporting, a dashboard Max can read at 06:30, and the
pipeline proven end-to-end so that the day Max arms a venue, the first real
order sheet is correct."

Read §2 before anything else. It is the part that is easy to get wrong.

---

## 1. What exists

`markets-desk/` — ~4,600 lines of stdlib Python plus PyYAML. 229 tests, none
touching the network. CI runs the suite, validates the shipped book, and stamps it.

| Piece | State |
|---|---|
| `codex-feed/MODE.yaml` | The authority. Caps, themes, event windows, freshness, venues. `mode: live_confirm`, `execution: research_packs_only`. Every venue `live: false`; equity/etf/perp/option `enabled: false` |
| `desk/risk.py` | Whole-book stamping, water-filling under theme + portfolio caps. Randomised invariant test over 200 books |
| `desk/ticket.py` · `challenge.py` · `report.py` · `assign.py` | The four contracts: ticket, adversary, seat report, work order. Each refuses on load |
| `desk/ledger.py` · `coach.py` | Outcome scoring; Jev graded on whether contested tickets did worse; Grok graded on whether crowding calls separate winners from losers |
| `desk/adapters/` | Polymarket, Hyperliquid, CBOE (computes GEX itself), EDGAR (distinct owners; routine screen), FRED. **Never run against a live endpoint** |
| `desk/sources.py` | 18-source registry + prober distinguishing `no_auth` / `geo_blocked` / `degraded` / `unreachable` |
| `desk/cli.py` | `validate preflight fetch assign challenge stamp pack score coach` |
| `tests/test_boundary.py` | Fails the build on order-placing machinery, signing material, PUT/PATCH/DELETE, POST outside `adapters/base.py`, Jev originating a ticket, or a shipped policy that arms a venue |
| `docs/` | `SEATS.md` (contracts per seat), `RISK-MODEL.md`, `ARCHITECTURE.md`, `CONNECTORS.md`, `MIGRATION.md`, `EVIDENCE.md` (literature check), `PRIOR-ART.md` |
| `codex-feed/HANDOFF-CODEX.md` · `BRIEF-GROK.md` | Standing instructions for the execution agent and the social seat |
| `tickets/` · `challenges/` · `assignments/` | Five live tickets, one Jev challenge, one machine-issued Grok assignment |

**Board as of this handoff** (`desk stamp --now 2026-09-22T06:30-07:00`):

| ticket | verdict | binding |
|---|---|---|
| WKND-001A COIN · 001B HOOD · 004 SBLK | FAIL | `venue.equity.disabled` |
| WKND-002 clarity No @ 92.5 | FAIL | `staleness` — Gamma price 23.5h past tolerance, never re-verified |
| WKND-005 BTC ladder | PENDING | `unchallenged` — Jev has not filed |

Allocated 0.00% of a 3.00% heat cap. That is correct: nothing on the board has
earned size yet.

---

## 2. What "ready to invest" means here — read this twice

It does **not** mean the system places trades. It never will. The doctrine is
`HANDOFF-CLAUDE.md`'s and it is enforced by CI, not by good intentions:

- Research seats produce info, briefs and tickets. They **never** place trades,
  move money, connect wallets, or post unsupervised.
- Codex owns the ticket → order-sheet path and **never** fires live capital
  without Max's confirm.
- **Max approves every capital action.** `mode: live_confirm`.
- Hard bans: unsupervised live orders · wallet spend by research · pumper X
  sources · eToro · any auto-trade path in a cloned repo stays disabled.

"Ready to invest" means: **the day Max names a broker in `MODE.yaml`, the pipeline
from seat report → challenge → stamp → pack → order sheet runs without a human
re-deriving anything, and the first sheet Codex formats is the right size on the
right instrument with the right stop.** Every step before that gate is yours.
The gate itself is Max's. Do not touch it. Do not "temporarily" enable a venue to
test. Test with `live: false` and `research_packs_only` — that is what they are for.

If a task in this document seems to require arming anything, you have misread
the task. Stop and ask Max.

---

## 3. Blocked on Max, not on you

1. **PR #1 is unmerged.** Green, clean, draft, 12 commits. Nothing below can start
   on the desk box until it lands on `main`. If it is still draft when you read
   this, tell Max once, plainly, and then work on whatever does not need the box.
2. **Equity venue.** Three of five tickets FAIL on `venue.equity.disabled`. Max
   decides whether to name IBKR. Do not pre-empt it.
3. **`require_challenge`.** Currently `true`. My recommendation is to keep it.
   Max's call.

---

## 4. The plan, in order

Each phase has a done-condition. Do not start the next until the current one's
condition holds — the phases are ordered so that each one's failure is cheap.

### Phase 0 — Land it

```bash
cd /workspace && git pull   # after PR #1 merges
cd markets-desk && pip install pyyaml
python -m unittest discover -s tests -t . -q      # expect: Ran 229 tests / OK
python -m desk validate
```

**Done when** `validate` passes on the box and the test count matches.

### Phase 1 — Prove the data layer live

This is the highest-value, least-glamorous phase. Every adapter was written
against documented response shapes and fixtures because this session's egress
blocked every market-data host. Expect field drift.

```bash
export DESK_USER_AGENT="Max Motif max@maxmotif.com"
export FRED_API_KEY=…                       # Ledger
python -m desk preflight --out preflight/$(date +%F).json
```

Expect: `no_auth` on CoinGlass, `geo_blocked` on Binance and Bybit, `ok` on
Hyperliquid, Polymarket Gamma, CBOE delayed, EDGAR, FRED. If Hyperliquid is
`ok`, Chain's funding/OI problem is solved.

Then run each fetch and fix what breaks. Keep fixes minimal; when an upstream
field has moved, change the adapter, add a fixture from the real response, and
leave the test that would have caught it.

```bash
python -m desk fetch Odds   --slug clarity-act-signed-2026 --outcome No
python -m desk fetch Chain  --coin BTC --coin ETH
python -m desk fetch Pulse  --symbol _SPX
python -m desk fetch Shadow --cik 883902 --ticker SBLK
python -m desk fetch Ledger --series 2s10s
```

Two things to finish here:

- **EDGAR owner histories.** `is_routine()` exists and is tested, but the
  per-owner history fetch that feeds it is not wired — it needs the reporting
  owner's own CIK and a second `submissions` call. Wire it, respect the 10 req/s
  limit, and make `fetch Shadow` file `opportunistic_buyers` and
  `routine_buyers`. Until then the read says "routine buyers not yet screened",
  which is honest but not useful.
- **Re-verify WKND-002.** Its Gamma price is stale and was never re-fetched. Run
  `fetch Odds`, update the ticket's evidence with the real `as_of`, and read the
  CLOB depth — that depth read is Jev's last open mind-change condition.

**Done when** `preflight` shows every source Max has a key for as `ok`, all five
`fetch` verbs return evidence with real `as_of` stamps, and a Shadow read on SBLK
reports the routine screen.

### Phase 2 — The connector manifest

The one pattern worth taking from the prior-art pass. Six connectors were
half-attached with nothing noticing. Commit `codex-feed/connectors.json`
declaring, per seat, which MCP connectors and which `sources.yaml` entries it
depends on; extend `desk validate` to assert each is present and (for sources)
probed `ok` in the newest `preflight/` report. A seat whose dependency is dark
should fail validation with the dependency named, not file nothing.

**Done when** `validate` refuses a book whose seat dependencies are missing,
and the test suite carries that refusal.

### Phase 3 — Grok live

1. Paste `codex-feed/BRIEF-GROK.md` into Grok Bot as its standing instruction.
2. Point it at `assignments/2026-09-22-grok.assignment.yaml` — or re-issue:
   `python -m desk assign Grok --out assignments/$(date +%F)-grok.assignment.yaml`.
3. When the first report lands in `reports/`, run
   `python -m desk assign Grok --audit --strict`. Expect it to fail the first
   time; the brief is long and the contract refuses a lot. Read each refusal
   and fix the brief, not the contract.
4. After a week of reports: `python -m desk coach Grok`. It will say "too thin
   to judge" on separation — correct — but it will already report answer rate,
   unsolicited rate, and whether `crowded` has ever fired.

**Done when** an audit passes `--strict` on a real report, and `coach` has a
compliance read to show.

### Phase 4 — The dashboard

Max should be able to open one page at 06:30 and see the desk. Build it as a
new verb, `python -m desk dash --out dash/index.html`, rendering **static HTML**
from the same loaders the CLI uses. No framework, no build step, no server
required — a file Max opens. If a local server is wanted, `python -m http.server`
over the output directory is the whole deployment.

Panels, top to bottom:

| Panel | Source | What it must show |
|---|---|---|
| **Mode** | `MODE.yaml` | `mode`, `execution`, heat cap, allocated %, every venue with `enabled`/`live` — red if anything is `live: true` |
| **Sources** | newest `preflight/*.json` | Each of 18 sources with state, latency, and when last probed; a source dark >24h is red |
| **Book** | `stamp` | The stamp table as-is: ticket, verdict, Jev verdict, asked, allowed, binding constraint, with reasons expandable |
| **Adversary** | `challenge` | Unchallenged tickets by age; a ticket unchallenged >12h at PENDING is yellow |
| **Assignments** | `assign --audit` | Per research seat: issued when, at-stake %, answered / unanswered / stale / unsolicited |
| **Seats** | `reports/` newest per seat | Seat, read, headline, produced_at, staleness vs policy; a required seat with no report is red |
| **Ledger** | `score` | The three score tables, the calibration lines, the Jev line, the Grok line |
| **Event windows** | `MODE.yaml` | Upcoming windows with what kinds they bind |

Rules that are not negotiable:

- **Read-only. No forms, no buttons that do anything, no JavaScript that makes
  a request.** Extend `tests/test_boundary.py` to assert the rendered HTML
  contains no `<form>`, no `fetch(`, no `XMLHttpRequest`, no `onclick`. The
  dashboard is a window, not a console.
- Every number on it comes from the same function the CLI calls. If the
  dashboard and `desk stamp` can disagree, the dashboard is wrong.
- Timestamps shown in America/Los_Angeles with the UTC in a title attribute.
- Render must succeed with an empty `reports/`, an empty `ledger/`, and no
  preflight file — it says "none yet" in the panel rather than crashing.
- Add `dash` to CI: render it against the shipped book and assert the boundary
  test on the output.

Design: match the CLI's voice. Dark background, one accent for PASS, one for
FAIL, one for PENDING, everything else grey. No charts until the ledger has
enough outcomes for a chart to mean anything; a table of five rows does not
need a bar.

**Done when** `dash` renders the shipped book in CI, the boundary test covers
the output, and Max has opened it once and not asked what a column means.

### Phase 5 — The ledger, forward only

Start recording outcomes on the **next** ticket decided, not retroactively.
Backfilled outcomes are reconstructed memory and flatter the desk.

```yaml
# ledger/2026-09-2X-WKND-00N.outcome.yaml
ticket_id: WKND-00N
decided_at: 2026-09-2XT06:45:00-07:00
taken: false
reason: stood down — allowance 0.00% on venue.equity.disabled
```

Skips count. A desk that scores only the trades it took cannot see its own
selection bias. After ten outcomes, `desk score` starts saying things; after
thirty, believe it.

**Done when** every ticket that reaches a verdict has an outcome file the same
day, and `score` runs in the morning session.

### Phase 6 — Run alongside, then in front

Run `stamp` next to Rails' manual stamp for two weeks. Where they disagree, one
is wrong and the disagreement is the finding. Log each one. Only when they agree
consistently does `pack` feed Codex directly.

**Done when** two weeks of stamps agree, or every disagreement has been resolved
into either a `MODE.yaml` correction or an engine fix with a test.

### Phase 7 — The gate (Max's, not yours)

When Max names a broker:

1. Max edits `MODE.yaml`: the venue's `enabled: true`, names the broker in
   `note`, moves `execution` to `broker_sheets`. **`live` stays `false`.**
2. Update `test_boundary.py`'s shipped-policy assertion to the new expected
   state — it will fail on purpose the moment `MODE.yaml` changes, and that
   failure is the review.
3. Codex formats the first sheet from `stamp --json`. Max confirms or does not.
4. `live: true` is a separate, later, Max-only edit, and it changes nothing
   about who confirms.

You may prepare steps 2–3 so they are ready. You may not perform step 1.

---

## 5. Things I know are wrong or thin

- **The adapters are untested live.** Said three times because it matters.
- **`docs/EVIDENCE.md` is built from search summaries**, not full reads —
  every paper host was blocked. Open the four papers that changed the code
  (Cohen–Malloy–Pomorski; Da–Engelberg–Gao; Cookson–Niessner; the Polymarket
  favourite–longshot paper) and correct any number that does not survive.
- **Grok's brief has never been read by Grok.** Expect the first report to be
  refused and the brief to need edits.
- **WKND-002's evidence is stale** and Jev's revision-2 verdict was written
  without the CLOB depth read it asked for.
- **Chain's crowding read** is a positioning proxy, not a timing signal; the
  contract already says so, but no ticket has yet leaned on it, so the wording
  is untested against a real argument.
- **No dashboard exists.** Phase 4 is a spec, not a sketch of something started.

---

## 6. Hard rules, enforced

`tests/test_boundary.py` will fail your build if you:

- name `create_order`, `place_order`, `submit_order`, `SecureClient`,
  `private_key`, `mnemonic`, `withdraw`, or their kin anywhere in `desk/`
- use PUT, PATCH or DELETE anywhere
- POST from anywhere but `desk/adapters/base.py`, or send Hyperliquid a payload
  not in `READ_ONLY_REQUESTS`
- put Jev in any ticket's `source_seats`
- ship a `MODE.yaml` with any venue `live: true` or `execution` off
  `research_packs_only`

Lifting any of these means deleting an assertion, which shows in review. That is
the point. If you find yourself wanting to, you are in Phase 7 and it is not
your phase.

---

## 7. Where things are

```
markets-desk/
  HANDOFF.md                  ← this
  README.md                   the verbs
  codex-feed/
    MODE.yaml                 the authority
    sources.yaml              18 sources
    HANDOFF-CODEX.md          what Codex reads and owes back
    BRIEF-GROK.md             paste into Grok Bot
    DOCTRINE.md               the rules, in prose
    *_TEMPLATE.yaml           ticket, challenge, report
  desk/                       the package
  tests/                      229, incl. test_boundary.py
  tickets/ challenges/ reports/ assignments/ ledger/ preflight/
  docs/
    SEATS.md                  every seat's contract and refusals
    EVIDENCE.md               what the literature says, and what changed
    RISK-MODEL.md ARCHITECTURE.md CONNECTORS.md MIGRATION.md PRIOR-ART.md
```

---

## 8. Your first hour

1. Read `codex-feed/DOCTRINE.md`, then §2 above again.
2. `python -m unittest discover -s tests -t . -q` — 229, OK, or stop.
3. `python -m desk stamp` — read every reason line. If any surprises you, read
   `docs/RISK-MODEL.md` before touching anything.
4. `python -m desk preflight` — this is the first real information you will
   have that I did not. Write down what it says before fixing anything.
5. Pick up Phase 1.

Every allowance the desk produces is a ceiling, not an instruction. Info moves;
money never — until Max says, and then only as far as Max says.
