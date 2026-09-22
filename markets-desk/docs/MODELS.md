# Models

How several frontier models share one desk without it becoming a vote.

## The premise

A seat is anything that satisfies a contract — a ticket, a challenge, a
report. That made the desk model-agnostic from the start: Grok joined by
writing files, and Codex reads `stamp --json` without caring what produced
it. So "a collab of the best models" is not an architecture change. It is a
roster, and three rules.

## The rule that matters

**Two models agreeing is not evidence.** Their errors correlate through shared
training data and shared sources. Two models disagreeing is not signal either;
it is a tie with no tiebreak. So the desk never asks models to vote. It assigns
each model to a seat for a **capability the desk would otherwise lack**, and
scores the seat.

The roster is `codex-feed/ROSTER.yaml`. Every assignment carries a `why`, and
`desk validate` refuses one without it — an assignment with no capability
behind it is a second vote.

| Seat | Model | The capability |
|---|---|---|
| Wire, Ledger | Gemini | Search grounding for calendar and event→instrument; long context for filings and transcripts |
| Grok | Grok | Live X. Nothing else on the desk can see it |
| Chain, Odds, Pulse, Shadow, Rails, CoS | Claude | Wrote the contracts and the tests; the seat that edits caps should be the one that can break the build |
| Codex | Codex | Execution path, by doctrine |
| **Jev** | **any** | **Whichever model did not write the ticket** |

Claude holds six research seats, which is the cap. That is not a vote of
confidence; it is that four of those seats are adapter-fed and need a careful
reader more than a special capability, and splitting them across vendors for
its own sake buys nothing. The ledger will say whether that holds.

## The three rules, enforced

**1. The adversary must be a different model from the proposer.**
`rules.adversary_must_differ`. A challenge whose `model` matches the ticket's
model — declared, or inferred from the proposing seat's roster entry — is
self-review. It does not count. The ticket stays PENDING until a different
model argues against it. Every verb that gates on Jev (`validate`,
`challenge`, `stamp`, `pack`) goes through the same filter, so the rule cannot
be bypassed by picking a different command. Dropped challenges are printed as
`SELF-REVIEW` with the reason.

This is why Jev is `any` and not a model. Pin Jev to Claude and every Claude
ticket is unchallengeable; `validate` refuses a roster that does that.

**2. Score by model, not just by seat.** `rules.score_by_model`. Seats that
share a model share a failure mode. `desk score` adds a `by model` table that
collapses seats into vendors, so a systematic bias in one shows up as one row
rather than being spread thin across five. After thirty outcomes, this table is
the roster review.

**3. No model holds more than six research seats.**
`rules.max_research_seats_per_model`. One vendor's outage, or one vendor's
blind spot, cannot dark the whole desk.

## How a model joins

Write a file. A ticket in `tickets/`, a challenge in `challenges/`, a report
in `reports/`. Add the model under `models:` in the roster and assign it a seat
with a `why`. Optionally declare `model:` on each filing — the adversary rule
bites exactly on declarations and only by inference without them, so a desk
that wants the rule strict declares it everywhere.

No API. No adapter. The contract is the interface, and it is the same contract
for a frontier model, a fleet, or a person with a text editor.

## How a model leaves

The ledger says so. `desk score` by model with thirty resolved outcomes and a
negative expectancy is the case; a seat whose reports keep being refused by the
contract is the other case. Reassign the seat in the roster, leave the ledger
rows — they are the record of why.

## What this is not

- Not an ensemble. Nobody averages the models' opinions.
- Not a consensus mechanism. Agreement is cheap.
- Not a way to skip Jev. Two proposers is still zero adversaries.
- Not a change to who confirms. Every model on the desk produces ceilings and
  arguments; Max confirms every order, whichever model wrote the ticket.
