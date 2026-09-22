# Weekend pack → schema, row by row

How the five rows in the 2026-09-20 weekend Rails stamp map into this repo.
Written 2026-09-20 so Monday's seats can see what was transcribed, what was
corrected, and what was deliberately not created.

| Weekend row | Became | State |
|---|---|---|
| WKND-001 COIN/HOOD continuation vs fade | `WKND-001A` (COIN), `WKND-001B` (HOOD) | stubs, 0% |
| WKND-002 Polymarket Clarity Yes ~7.55c | `WKND-002`, flipped to No | researched, contested, 0.20% |
| WKND-003 Wed flash PMI / rates | **not a ticket** — the `us-flash-pmi-2026-09-23` event window in `MODE.yaml` | encoded |
| WKND-004 SBLK Form 4 cluster | `WKND-004` | stub, 0% |
| WKND-005 BTC ladder / Sep20 binary | `WKND-005` (ladder only) | stub, 0% |

## Why WKND-003 is not a ticket

Rails stamped it "PASS event-map", which is a calendar fact rather than an
expression: no instrument, no direction, no invalidation. Writing it as a
ticket would have required inventing all three.

It is already doing its job as an event window — it caps risk at 1.0% around
the print and zeroes anything gapping held overnight through it, for every
ticket, automatically. That is stronger than a ticket, because a ticket only
constrains itself.

If Rails later wants an actual expression around the print (an index straddle,
a rates leg), that becomes a new ticket and the window keeps applying to it.

## What the stubs are and are not

The four stubs carry `size_hint_pct: 0.0` and `confidence: 1`, so they cannot
draw risk even if something else in the pipeline went wrong. Their thesis
fields say what the weekend summary row said and then state plainly that the
originating seat owes the real reasoning. **None of them contains research I
wrote.** The one-line rows in the handoff were not enough to write a thesis
from, and inventing one would have been worse than an empty slot — it would
have looked like work.

Each stub does carry the parts that were genuinely specified: the Chain HOLD /
SOFT / LOST gate on 001, the aggregator-vs-primary-document problem on 004,
the 55-60% model threshold on 005, and the fetch command that settles each one.

All four show as PENDING awaiting Jev, which is correct — the adversary cannot
attack a thesis nobody has written yet. They get challenged when the seats
fill them.

## Two things that were corrected, not transcribed

**The WKND-002 vote tally.** Revision 1 of that ticket said the cloture vote
failed 50-49. The Senate record is **49-50, Roll Call 234**. Two secondary
sources disagreed on the direction and the primary record settles it. Fixed.

**The WKND-002 side.** The weekend row carried Yes at 7.55c. Odds' question —
does this resolve on a signed statute, or on any regulatory relief — became
live on September 17, when the SEC issued a five-year Innovation Exemption for
onchain trading of tokenized stocks and the CFTC a developer no-action
position. Regulatory relief arrived; the statute did not. A market resolving on
"signed into law" is unaffected, which is exactly the distinction Rails flagged
and the reason the Yes side is retired rather than cheap.

## What Rails deliberately does not yet encode

The weekend stamp set continuation at **≤1.0% combined across COIN and HOOD**,
tighter than the 1.5% `crypto_policy_beta` theme cap. That was a Monday
re-stamp decision, so it is not in `MODE.yaml` — Rails sets it when it
re-stamps. If it becomes standing policy, express it as its own theme
containing only COIN and HOOD; the mechanism is already there.

MSTR and MARA were stamped at zero. No tickets were created for them.
