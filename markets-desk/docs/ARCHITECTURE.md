# Architecture

## Shape

```
seats research  →  reports/*.report.yaml
      ↓                    ↓
tickets/*.ticket.yaml  →  Rails (desk/risk.py)  →  Codex pack  →  Max
      ↑                        ↑
evidence with as_of      codex-feed/MODE.yaml
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
| `report.py` | The seat-report contract — how any researcher, including a fleet that is not this process, hands work to the desk |
| `assign.py` | The desk's work order to a research seat, and the audit of what came back |
| `coach.py` | Grade a seat's crowding calls against the ledger; emit what to change |
| `roster.py` | Which model sits where; the adversary-must-differ rule; score by model |
| `confirm.py` | Max's yes as a file: PASS only, digest of the stamp, one session, `max` only; void when the book moves |
| `sheet.py` | The order/paper sheet; `format_sheet` takes a `Confirm` and there is no version that does not |
| `serve.py` | The desk over HTTP: every GET a view over the loaders; exactly one write, `/confirm`, token-gated |
| `ui.py` | The page, rendered server-side from the snapshot; every timestamp shows its age; one fetch, to `/confirm` |
| `daemon.py` | The cadence from `CADENCE.yaml`; writes every session; never fetches for a seat, never confirms |
| `notify.py` | Push via ntfy or Pushover, deduplicated per condition; may only reach notify hosts |
| `connectors.py` | Per-seat dependency manifest; `validate` refuses unknown sources and names dark seats |
| `apps/apple/` | Native Mac and iPhone clients of `serve`: DeskKit (models mirroring the snapshot, the client with one POST, Keychain pairing, age), DeskUI (views), two app targets. Guarded from Python by `tests/test_apple.py` |
| `risk.py` | Rails. Per-ticket gates, then water-filling allocation under theme and heat caps |
| `sources.py` | The data-source registry and the preflight prober |
| `adapters/` | Per-seat fetchers returning `Evidence`: Polymarket (Odds), Hyperliquid (Chain), CBOE (Pulse), EDGAR (Shadow), FRED (Ledger) |
| `ledger.py` | Outcome scoring and the calibration check |
| `cli.py` | `validate`, `preflight`, `fetch`, `assign`, `challenge`, `stamp`, `pack`, `score`, `coach`, `confirm`, `sheet`, `serve`, `daemon`, `pair` |

Stdlib only, plus PyYAML. Every dependency is something that can break at 06:30
on a Monday, and the desk runs on one box with no one to page.

## Why hand-rolled validation

`jsonschema` would express these contracts adequately and add a dependency plus
an error-message style that reads like a schema rather than like advice. The
contracts here are small and the messages are read by seats under time pressure,
so `loader.check_fields` trades generality for saying "an idea you cannot be
wrong about is not a trade" instead of "invalidation: minLength 20".

## The one allowlisted POST

Hyperliquid's read endpoint takes a POST body. The invariant the desk wants is
"no mutating request", not "no POST", so rather than banning the verb and
either losing the only funding source that works from the box or writing the
verb obliquely to dodge the check, POST is confined to `adapters/base.py` and
the payloads Hyperliquid may receive are pinned to a declared read-only tuple.
PUT, PATCH and DELETE stay banned outright with no allowlist. Both rules are
asserted in `tests/test_boundary.py`, and both were verified to trip.

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
