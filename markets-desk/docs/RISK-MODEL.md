# Risk model

## Units

Everything is a percentage **of the risk budget** — capital at risk, not
notional. A 1.0% allowance on a $50k budget is $500 of loss if the invalidation
level trades, whatever notional that implies.

Codex converts. `Ticket.notional_for_risk()` divides the dollar allowance by
the per-unit risk (entry minus stop, or the premium for defined-risk) and
multiplies by entry. When a ticket lacks the structure to do that, it returns
`None` rather than a guess, and the contract refuses such a ticket if it asked
for size at all.

The budget itself is deliberately not in the repo. `MODE.yaml` names where it
comes from; the number stays in the environment.

## Why theme caps, not position caps

The literature on fractional Kelly is consistent on one point: applying Kelly
independently to correlated positions systematically overbets, because the
portfolio's exposure is to the shared factor, not to the individual names. The
practical form is to cap the combined exposure and let the legs share it.

The desk already had this intuition — the weekend Rails stamp treated
crypto-equity, the Clarity market and the BTC ladder as one theme at 1.5%. The
engine makes it structural rather than a note someone has to remember to apply.

September 15 is the argument for it. One Senate cloture vote moved COIN, HOOD,
MSTR, spot BTC and the Clarity market together. Three legs sized at 1.0% each
on their own merits would have been 3.0% of exposure to a single vote.

A single-name override is expressed as a one-member theme. SBLK's 0.75% and
RWT's 0.25% need no second mechanism.

## The conviction ladder

| Confidence | Fraction of single-name cap |
|---|---|
| 1 | 0% — research output, not a position |
| 2 | 20% |
| 3 | 40% |
| 4 | 70% |
| 5 | 100% |

This is a **prior, not a result.** The desk does not yet have reliable
probability estimates, so conviction stands in for one, and a steep bottom
means a weak idea carries nothing.

`python -m desk score` exists to retire this guess. Once roughly thirty tickets
have resolved, re-cut the ladder from realised expectancy. If confidence 5 is
not out-earning confidence 3, the ladder is decoration and the calibration
report says so.

## Water-filling, not flat scaling

When a theme is oversubscribed, the cap is shared pro-rata by conviction —
but nobody exceeds their own ceiling, and room freed by a ceiling-bound leg is
redistributed to the others rather than left unused.

Flat scaling would be simpler and wrong. Consider a 1.5% theme with a
conviction-5 leg wanting 1.0% and a conviction-2 leg ceilinged at 0.2%. Flat
scaling to fit shrinks both; water-filling gives the weak leg its 0.2% and the
strong leg its full 1.0%. The weak idea should not be able to starve the strong
one.

## Event windows

A window suppresses risk around a scheduled catalyst: a cap on size expressed
around the print, and usually zero for anything held overnight through it.

Windows are **scoped to instruments that gap on the print** (`applies_to_kinds`).
Unscoped, "flat into the Wednesday PMI" zeroed a Polymarket position resolving
in December — which is not a risk decision, it is a category error. You cannot
flatten a year-end binary into a Wednesday print, and its risk is defined and
already sized.

The default remains all kinds. Narrowing is a deliberate act per window.

## Freshness as a gate, not a discount

Evidence declares `as_of` — when the fact was true, not when it was fetched —
and `MODE.yaml` sets a tolerance per kind. Past tolerance, the ticket fails.

Failing rather than discounting is the right call because stale market data is
not a weaker version of fresh data, it is a different number. A gamma profile
from the previous expiry is not a noisy estimate of today's; it describes
positioning that no longer exists.

## Fail-closed, everywhere

| Situation | Result |
|---|---|
| Desk halted | 0%, FAIL |
| Venue not armed | 0%, FAIL |
| Evidence past tolerance | 0%, FAIL |
| Required seat report missing | 0%, PENDING |
| Explicit Rails fail on the ticket | 0%, FAIL |
| Caps leave nothing | 0%, FAIL with the binding constraint named |

Every stamp names its binding constraint, so "why is this 0.4%?" has one answer
rather than a reconstruction.
