# Architecture

## Shape

```
seats research  →  tickets/*.ticket.yaml  →  Rails (desk/risk.py)  →  Codex pack  →  Max
                          ↑                        ↑
                   evidence with as_of        codex-feed/MODE.yaml
                          ↑
                 codex-feed/sources.yaml  →  preflight prober
                                                    ↓
                        ledger/*.outcome.yaml  ←  what actually happened
```

Two properties matter and everything else follows from them.

**The policy is data.** `MODE.yaml` holds modes, caps, correlation themes,
event windows and freshness tolerances. Rails reads it and applies it. Nothing
re-derives sizing from prose, so the same book stamps the same way twice.

**The book is stamped whole.** A ticket's allowance depends on what else is
competing for its theme cap, so tickets cannot be sized individually and summed.
This is the difference between a 1.5% crypto-beta cap and three 1.0% positions
in the same factor.

## Modules

| Module | Responsibility |
|---|---|
| `loader.py` | Load YAML/JSON, hand-rolled field checking, timezone-strict instant parsing |
| `mode.py` | Parse and validate the policy; theme lookup, freshness lookup, venue lookup |
| `ticket.py` | The ticket contract, and the risk→notional arithmetic Codex needs |
| `risk.py` | Rails. Per-ticket gates, then water-filling allocation under theme and heat caps |
| `sources.py` | The data-source registry and the preflight prober |
| `ledger.py` | Outcome scoring and the calibration check |
| `cli.py` | `validate`, `preflight`, `stamp`, `pack`, `score` |

Stdlib only, plus PyYAML. Every dependency is something that can break at 06:30
on a Monday, and the desk runs on one box with no one to page.

## Why hand-rolled validation

`jsonschema` would express these contracts adequately and add a dependency plus
an error-message style that reads like a schema rather than like advice. The
contracts here are small and the messages are read by seats under time pressure,
so `loader.check_fields` trades generality for saying "an idea you cannot be
wrong about is not a trade" instead of "invalidation: minLength 20".

## Failure posture

Every gate fails closed. Missing data is `PENDING`, not a pass with a caveat.
Stale data is `FAIL`, not a discount. A disabled venue refuses the ticket
regardless of the ticket's merit. Rounding floors rather than rounds, because
rounding up breaches a cap.

The one deliberate exception: an unknown evidence `kind` inherits the default
tolerance rather than being rejected, so a seat can introduce a new kind of
evidence without editing policy first. It gets 72 hours, which is conservative
for anything that moves.

## What this does not do

No execution, no order formatting, no venue connectivity, no position tracking.
Open risk is an input (`--open-risk`), not something the desk observes, because
observing it would mean holding broker credentials.
