# Markets Desk → Codex handoff

**From:** Claude (research/plumbing) · **To:** Codex (tickets, prep, execution path)
**Written:** Sun 2026-09-20, America/Los_Angeles
**Purpose:** what changed on the desk, what you now consume, and what you owe back.

Nothing here changes your mandate. You still own the trade-ticket and execution
path, and Max still confirms every capital action. What changed is that you no
longer parse prose to find out how much you may work with.

---

## 0. Read first, now that it exists

`markets-desk/AGENTS.md` is your native instruction file — hard rules, hot
files, acceptance, reporting. `prompts/CODEX_IMPLEMENTATION_PROMPT.md` is the
paste-in for desk code work; branch as `codex/desk-<topic>`. `.motif/STATE.md`
is the current state. This file is what changed for you on the desk itself.

## 1. The one-line version

The desk's caps, freshness rules and correlation buckets moved out of markdown
and into `codex-feed/MODE.yaml`, which a risk engine executes. You get a
structured ticket plus a named ceiling per ticket instead of a paragraph and a
size hint.

---

## 2. What you read now

```bash
python -m desk stamp --json    # machine-readable allowances
python -m desk pack            # the human pack, same numbers
```

`stamp --json` gives you, per ticket:

| field | meaning for you |
|---|---|
| `allowed_pct` | **ceiling** on % of risk budget. Never an instruction |
| `verdict` | `pass` · `pending` · `fail` |
| `binding_constraint` | why it is that number, in one token |
| `theme` | the correlation bucket it draws from |
| `reasons[]` | the human-readable trail |

If `verdict` is anything but `pass`, or `allowed_pct` is 0, there is no order
sheet to write. Do not round up, do not average two tickets, do not treat a
`pending` as a small `pass`.

---

## 2b. The confirm — read before §3

You format a sheet only for a ticket with a confirm on file. Not a message,
not a chat reply: a file in `confirmations/`, written by `desk confirm` or by
the page's confirm button, that carries a digest of the stamp Max was looking
at. `python -m desk sheet <TICKET>` is the only path to a sheet and it refuses
without one, or with one whose digest no longer matches the book, or one that
has expired. `desk confirm --list` shows what is usable right now.

If the book moves after Max confirms — a seat files, Jev revises, a window
opens — the digest changes and the confirm is void. The daemon pushes him.
You do not proceed on the old one.

## 3. Converting a ceiling into a position

Percentages are of the **risk budget** — capital at risk if the invalidation
level trades — never notional.

```python
from desk.ticket import load_ticket
t = load_ticket("tickets/2026-09-21-WKND-005-btc-ladder.ticket.yaml")
notional = t.notional_for_risk(allowed_pct / 100 * risk_budget_usd)
```

`notional_for_risk` returns **`None`** when the ticket lacks the price
structure to do the arithmetic. That is the answer, not an error to route
around: a ticket that cannot be sized does not get sized. Kick it back to the
originating seat.

The risk budget number is deliberately not in the repo. `MODE.yaml` says where
it comes from; you inject it at runtime.

---

## 4. The execution boundary, as it stands today

| venue | enabled | live | what that means for you |
|---|---|---|---|
| `equity`, `etf` | **no** | no | Research and stamps only. No order sheets. No venue has been named |
| `kraken` | yes | **no** | Paper and intel only |
| `polymarket` | yes | **no** | Gamma + CLOB **reads**. PublicClient only, never SecureClient, never POST `/order` |
| `crypto_spot` | yes | no | Read-only pricing; any sheet routes to Kraken paper |
| `crypto_perp` | **no** | no | Funding/OI intel only. The desk does not size perps |
| `option` | **no** | no | No venue, and the greeks feed is not yet trusted |

`execution: research_packs_only`. Moving off that is a `MODE.yaml` edit plus
deleting an assertion in `tests/test_boundary.py`, and it is Max's call, not
yours or mine.

**Interactive Brokers is connected-but-unfinished in the workspace and is
staying that way.** Its server carries order-placing tools; finishing that
OAuth silently moves the desk off research-packs-only. Do not complete it.

---

## 5. New in the pipeline: Jev

There is a ninth seat. Jev is the adversary — it challenges every ticket before
Rails stamps it, and it may not originate tickets.

What this means downstream: a ticket's conviction may already have been docked
before you see it, and the stamp will say so (`challenge_verdict`, and a
`challenged:` line in `reasons[]`). A `kill` is a hard FAIL. With
`require_challenge: true`, an **unchallenged ticket is PENDING at 0%** — so a
fast Monday-open idea can arrive at zero purely because Jev has not run yet.
That is not a bug; if it bites, the fix is Max relaxing the flag, not you
working around it.

Full contract: `docs/SEATS.md`.

---

## 6. Board state as of this handoff

`python -m desk stamp --now 2026-09-21T06:30:00-07:00`:

| ticket | verdict | allowed | binding |
|---|---|---:|---|
| WKND-002 · Polymarket Clarity **No** | PENDING | 0.20% | `conviction[2]` (Jev docked it) |
| WKND-001A · COIN | FAIL | 0.00% | `venue.equity.disabled` |
| WKND-001B · HOOD | FAIL | 0.00% | `venue.equity.disabled` |
| WKND-004 · SBLK | FAIL | 0.00% | `venue.equity.disabled` |
| WKND-005 · BTC ladder | PENDING | 0.00% | `unchallenged` |

**Nothing is actionable.** Three tickets cannot become order sheets at all
until an equity venue is named. WKND-002 has a ceiling but two open conditions
(below). WKND-005 needs Jev plus Chain's model number.

WKND-003 is not a ticket — it is the `us-flash-pmi-2026-09-23` event window,
which caps risk at 1.0% around the print and zeroes anything gapping held
overnight through it, for every ticket automatically.

---

## 7. Corrections to anything you were told earlier

- The CLARITY cloture vote was **49–50, Roll Call 234** — eleven short of
  sixty. An earlier draft of WKND-002 said 50–49. If you cached that, drop it.
- WKND-002 is now the **No** side, not Yes. Yes at ~7.55c is not cheap, it is
  nearly dead.
- The **SEC issued a five-year Innovation Exemption on 2026-09-17**, plus a
  CFTC developer no-action position. This does **not** resolve the Polymarket
  market, which turns on a signed statute. Do not let regulatory relief be
  mistaken for the statute — that conflation was the original Rails flag.
- The Sep 20 BTC binary in the old WKND-005 row is dead. Only the ladder
  survives.

---

## 8. What you owe back: the ledger

This is new and it is the part only you can do. Every ticket now gets an
outcome record, including the ones **not** taken — a desk that scores only its
fills cannot see its own selection bias.

```yaml
# ledger/2026-09-21-WKND-002.outcome.yaml
ticket_id: WKND-002
decided_at: 2026-09-21T06:45:00-07:00
taken: false
reason: ceiling held but CLOB depth never confirmed
```

Taken positions add `sized_pct`, and `result_r` plus `closed_at` when closed.
`result_r` is in R — multiples of the risk the ticket declared — so a 0.25%
idea and a 1.0% idea are comparable.

`reason` is **required** on a skip; the contract refuses the record without it.

Then `python -m desk score` reports expectancy by seat, theme and confidence,
flags a conviction ladder that is not earning its slope, and says whether Jev
is earning its seat. None of that works until outcomes start arriving, and you
are the only seat that knows what actually happened.

---

## 9. Before you trust any number

Every adapter in `desk/adapters/` is written against documented response shapes
and tested against fixtures. **None has been run against a live endpoint** —
the session that wrote them had every market-data host blocked.

Run this first, on the box, and read it:

```bash
export DESK_USER_AGENT="Max Motif max@maxmotif.com"
python -m desk preflight --out health-report.json
```

Expect `no_auth` on CoinGlass (the key was never set) and `geo_blocked` on
Binance and Bybit. Hyperliquid should come back `ok` — it needs no key and has
no geo gate, which is why it is Chain's primary funding/OI source instead of
the venues the box cannot reach.

If a field name has drifted upstream, fix the adapter. Do not paper over it
with a hardcoded value.

---

## 10. Two open conditions on WKND-002

1. **Resolution wording.** Confirm the exact text on the Gamma record, not the
   market title. The September 17 SEC action is the live test of this.
2. **CLOB depth on the No side.** Jev's one remaining mind-change condition:
   more than $5k resting within two cents of the midpoint means the ticket's
   exit rule is real and Jev concedes back to 0.40%. Less than that and the
   0.20% ceiling stands regardless of how dead the bill is.

```bash
python -m desk fetch Odds --slug clarity-act-signed-2026 --outcome No
```

Also note: the 7.55c in the ticket is a weekend read that has **not** been
re-verified, and the whole thesis is a comparison against it.

---

## 11. Hard bans, now enforced by CI

Unsupervised live orders · wallet spend by research · Polymarket
`SecureClient` or POST `/order` · Kraken live orders · completing the IBKR
connection · live auto-trade paths in cloned repos.

`tests/test_boundary.py` fails the build if order-placing machinery or signing
material appears in the package, if PUT/PATCH/DELETE shows up anywhere, if
POST escapes its one allowlisted read-only module, if a request body comes from
outside the declared read-only set, if Jev originates a ticket, or if the
shipped policy arms a venue. Every guard was verified to trip.

Lifting a ban means deleting an assertion. That shows up in review, which is
the point.

---

## 12. Where things are

```
markets-desk/
  codex-feed/MODE.yaml            desk policy — the authority
  codex-feed/sources.yaml         the data layer, declared
  codex-feed/DOCTRINE.md          roles and bans
  codex-feed/TICKET_TEMPLATE.yaml
  codex-feed/CHALLENGE_TEMPLATE.yaml
  codex-feed/HANDOFF-CODEX.md     this file
  tickets/*.ticket.yaml           the book
  tickets/CONVERSION-NOTES.md     what was transcribed vs corrected
  challenges/*.challenge.yaml     Jev's case against each ticket
  ledger/*.outcome.yaml           yours to write
  docs/SEATS.md                   Jev's contract
  docs/RISK-MODEL.md              why theme caps, why water-filling
  docs/MIGRATION.md               ordered steps for the box
  docs/CONNECTORS.md              the connector audit
```

Currently on branch `claude/financial-system-codex-grokvot-3ho3jh`, PR #1,
green, unmerged. **The box cannot pull this until it is on `main`.**

---

## 13. Your first five minutes

1. `python -m desk preflight --out health-report.json` — believe the output.
2. `python -m desk validate` — the book should load clean.
3. `python -m desk stamp --json` — read the ceilings, not the theses.
4. Anything non-zero: check `binding_constraint` before writing a sheet.
5. Nothing is non-zero today. Say so to Max rather than finding something.

Standing rule, unchanged: **info moves, money never** — until Max says the word,
per order.
