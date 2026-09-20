# Doctrine

Unchanged in substance from the desk this replaces. What changed is that most
of it is now enforced by code rather than remembered.

## Roles

| Role | Does | Never |
|---|---|---|
| Research seats — Wire, Ledger, Chain, Odds, Pulse, Shadow, Rails, CoS | Information, briefs, tickets | Place trades, move money, connect wallets, post unsupervised |
| Jev — the adversary | Challenges: the case against every ticket | Originate a ticket, or add conviction to one |
| Codex | Owns the trade-ticket and execution path | Fire live capital without Max's confirmation |
| Max | Approves every capital action | — |

Gabriel / Rails doctrine, unchanged: **information moves, money never.**

## Hard bans

Unsupervised live orders · wallet spend by research · no pumper sources ·
live auto-trade paths in cloned repos stay disabled · Polymarket `SecureClient`
and any POST to `/order` · Kraken live orders until Max arms them.

`tests/test_boundary.py` fails the build if order-placing machinery, signing
material, or a mutating HTTP verb appears in the package, and if the shipped
policy arms a venue or moves off `research_packs_only`. Lifting a ban means
deleting an assertion, which a reviewer sees.

## What a ticket must carry

The schema is in `desk/ticket.py` and is enforced, not advisory. A ticket is
refused if it has:

- a thesis too short to contain reasoning,
- no invalidation — an idea you cannot be wrong about is not a trade,
- a stop on the wrong side of entry, or equal to it,
- undefined risk, a size request, and no entry/stop to convert it,
- evidence without a source or an `as_of`,
- any timestamp without a timezone,
- `max_gate` anything other than true.

## The adversary

No ticket carries size until Jev has argued against it. An unchallenged ticket
is PENDING, a killed one FAILs, and a contested one is docked conviction before
any cap applies.

Jev may not originate tickets — a seat that proposes cannot credibly attack,
and the boundary test fails the build if it appears in a ticket's
`source_seats`. Its adjustment can only subtract, because an adversary that can
add conviction is just another proposer. Full contract in `docs/SEATS.md`.

## How sizing is decided

Rails stamps the **whole book at once**, because a ticket's allowance depends
on what else competes for its theme cap. The gates, in order, each able only to
reduce:

1. halt mode, disabled venue, stale evidence, missing seat report, no
   challenge on record, or a challenge that kills — hard stops
2. conviction ladder, after Jev's docking → a fraction of the single-name cap
3. single-name cap, less what is already on
4. event windows — the around-event cap, and the overnight cap for anything
   held past the close
5. theme cap, shared across correlated legs
6. portfolio heat, across all themes

Everything Rails returns is a **ceiling**, never an instruction. Max gates the
order.

## Freshness

Every piece of evidence declares when the underlying fact was true, not when it
was fetched. `MODE.yaml` sets a tolerance per evidence kind, and a ticket
leaning on anything past tolerance fails outright rather than being discounted.

Options greeks get 20 hours specifically so a feed frozen at Friday's expiry
cannot underwrite a Monday position.

## Scoring

Every ticket gets an outcome record, including the ones not taken — a desk that
only scores the trades it took cannot see its own selection bias. `python -m
desk score` reports expectancy by seat, theme and confidence, and flags a
conviction ladder that is not earning its slope.

The ladder in `MODE.yaml` is a prior. It should be re-cut from realised
expectancy once roughly thirty tickets have resolved.

## Changing policy

`MODE.yaml` is the authority. `MODE.md` may stay as narrative for humans; where
they disagree, the YAML wins, because the YAML is what runs.

Editing it changes what the desk may propose. Treat the edit like a trade:
Max gates it.
