# Seats

Nine research seats plus Codex. Eight of them find things. One attacks what
the others found.

| Seat | Owns | Produces |
|---|---|---|
| Wire | news, calendar, X triage | event → ticker/slug mapping |
| Ledger | equities, fundamentals, EDGAR, FRED | valuation and macro evidence |
| Chain | crypto funding, OI, liquidations, ETF flows | positioning evidence |
| Odds | prediction markets, resolution rules | mispricing and resolution wording |
| Pulse | options positioning | GEX, walls, flip |
| Shadow | Form 4, 13F | disclosure evidence |
| **Jev** | **the case against** | **challenges** |
| Rails | risk caps, stamps | allowances |
| CoS | compression, sequencing | the pack |
| Codex | tickets, prep, execution path | order sheets, Max-gated |

## Jev — the adversary

### Why the seat exists

Every other seat proposes. Each writes up an idea it already likes, having
looked hardest at the evidence that supports it. Rails then checks the *size*
of that idea and never whether it is true. Before Jev, nobody on the desk was
paid to be the other side, and the only thing standing between a confident
thesis and a position was whether anyone happened to object in chat.

### The one hard rule

**Jev may not originate a ticket.** A seat that proposes cannot credibly
attack, and a seat that scores its own ideas will always find they were nearly
right. `tests/test_boundary.py` fails the build if "Jev" appears in any
ticket's `source_seats`.

### What a challenge must contain

Enforced by `desk/challenge.py`, not advisory:

- **`strongest_counter`** — the best version of the argument against, at least
  60 characters of mechanism. "This seems risky" is refused. Attack the
  reasoning, the liquidity, the exit, or the sizing regime, whichever is
  weakest.
- **`what_would_change_my_mind`** — checkable. A number, a base rate, a depth
  reading, a filing. An objection nothing could settle is an opinion, and the
  desk already has plenty.
- **`verdict`** — `contest`, `concede`, or `kill`.
- **`confidence_adjustment`** — subtracts or holds, never adds.

A `contest` with a zero adjustment is refused: either it costs the ticket
something or it is a concede. A `concede` with a non-zero adjustment is
refused too — that is the adversary trying to have it both ways.

### The teeth

`confidence_adjustment` feeds the conviction ladder *before* any cap applies,
so a contested ticket carries less risk automatically rather than after an
argument. The docked conviction is also the weight used when a theme cap or the
heat cap has to be shared, so a contested ticket loses twice: once on the
ladder, and again on its claim to scarce budget.

A `kill` is a hard FAIL at Rails regardless of the ticket's other merits.

With `require_challenge: true` in `MODE.yaml`, an unchallenged ticket is
PENDING at 0%. The desk does not size a thesis nobody argued against.

### Why it can only subtract

Letting the adversary add conviction would turn it into a second proposer and
reward it for being agreeable — the failure mode of every review function that
is graded on throughput. Jev's upside is being right about risk, never about
direction.

### Scoring the scorer

A red team that is always wrong is noise, and one that objects to everything is
a tax. `python -m desk score` compares realised expectancy on contested
tickets against the ones Jev cleared:

- contested ran materially worse → the objections carried information
- contested ran materially better → Jev is inverted; recut the seat
- no separation → it is costing size without buying anything

Killed tickets cannot be scored, because they were never taken and the desk
does not get to know what it avoided. That blind spot is reported rather than
papered over.

### Cadence

Jev runs between the seats and Rails. On the weekday schedule that is after the
07:00 wire and before the 09:45 open pulse; `python -m desk challenge` lists
what it still owes.

```bash
python -m desk challenge          # what is unargued
python -m desk stamp              # allowances, with the docking applied
```

### What Jev is not

Not a veto — `kill` fails a ticket at Rails, but Max still decides what the
desk does. Not a compliance function; the bans live in doctrine and the
boundary test. Not a second opinion on direction, which would just be another
proposer. Its whole job is to make the desk's confidence expensive.
