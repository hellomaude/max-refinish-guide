# Moving the desk onto this

Written for the Grok Bot box at `/workspace/finance-team/`. Nothing here is
urgent — the old desk keeps working while this runs alongside it.

## Order of operations

**1. Land it read-only.** Copy `markets-desk/` next to `finance-team/`, install
PyYAML, run `python -m desk validate`. Nothing is wired to anything yet.

**2. Run the prober and believe it.**

```bash
export DESK_USER_AGENT="Max Motif max@maxmotif.com"
python -m desk preflight --out health-report.json
```

This settles by measurement what the Monday checklist carried by memory: which
of CoinGlass, Binance and Bybit are missing keys versus geo-blocked versus fine.
Expect `no_auth` on CoinGlass and `geo_blocked` on the two venues. If
Hyperliquid comes back `ok`, Chain's funding and OI problem is solved and the
geo-blocked venues can stay in the registry as documentation.

**3. Reconcile `MODE.yaml` against the current Rails stamp.** The committed
version encodes the 2026-09-20 weekend stamp: 1.5% crypto-beta, 1.0% single
name, SBLK 0.75%, RWT 0.25%, flat into the Wednesday PMI. Rails should read it
line by line and correct anything that drifted. This file is now the authority,
so an error here is an error everywhere.

**4. Convert tickets one session at a time.** Do not bulk-convert the archive.
Convert the live ones as they come up for re-stamping; the contract will refuse
some of them, and each refusal is worth reading rather than working around.
`tickets/2026-09-20-WKND-002-clarity.ticket.yaml` is the worked example.

**5. Start the ledger on the next ticket, not retroactively.** Backfilled
outcomes are reconstructed memory and will flatter the desk. Score forward.

**6. Run `stamp` alongside Rails for a week or two.** Where the engine and Rails
disagree, one of them is wrong and the disagreement is the interesting part. Only
after they agree consistently should `pack` feed Codex directly.

## What changes for each seat

| Seat | Change |
|---|---|
| Wire, Ledger, Chain, Odds, Pulse, Shadow | Evidence now carries `as_of` and a source. That is the whole change, and it is the one that catches frozen feeds |
| Rails | Stops hand-deriving sizes. Owns `MODE.yaml` instead, and reviews stamps rather than producing them |
| CoS | `python -m desk pack` renders what was compressed by hand |
| Codex | Reads structured tickets with a named ceiling per ticket, instead of parsing prose for a size hint |

## Cadence

The existing schedule maps straight across; only the command changes.

| When | Was | Now |
|---|---|---|
| Weekdays 07:00 | Morning wire → pack | `preflight` then `pack` |
| Weekdays 09:45 | Open pulse | `stamp --now` against the open tape |
| Weekdays 12:30 | Midday revise | `stamp` with `--open-risk` |
| Weekdays 13:15 | Close prep | `stamp`, then record outcomes |
| Mondays 08:00 | Weekly Rails | Review and edit `MODE.yaml` |
| Weekends | Crypto research | `pack`; the crypto sources need no market hours |

Run `preflight` first in any session that will size something. A seat citing a
source that was dark all morning is the failure mode this replaces.

## Two things to decide

**The equity venue.** `MODE.yaml` has `equity` and `etf` disabled because no
venue is named. When one is, set `enabled: true`, move `execution` to
`broker_sheets`, and update the assertion in `tests/test_boundary.py` that
currently pins `research_packs_only`. That assertion exists to make this a
deliberate diff rather than a drift.

**The risk budget.** Not in the repo on purpose. Decide where the number lives
and how Codex reads it; everything in the engine is a percentage until then.
