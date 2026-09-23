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
| Wire | Gemini | Search grounding for calendar and event→instrument |
| Ledger | Gemini (fallback GLM-5.3-Flash) | 1M context for filings; the frontier still leads annual-report QA |
| Grok | Grok | Live X. Nothing else on the desk can see it |
| Odds, Rails | Claude | Rules-lawyering resolution text; wrote the engine and its tests |
| Chain, Pulse, Shadow, CoS | **Qwen3.6-27B, local** | Adapter-fed seats whose YAML the contract checks; the book never leaves the box |
| Codex | Codex | Execution path, by doctrine |
| **Jev** | **pool: gpt-oss-120b first, local** | **Whichever model did not write the ticket** — a different vendor from every frontier proposer by construction |

Four research seats and the default adversary run on the desk machine. What
open weights buy — privacy, vendor-independence, cost — and what they do not
buy is in `docs/OPEN-WEIGHT.md`. The ledger will say whether the split holds.

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

---

## Update 2026-09-23

What moved for a seat since the roster was written. Sources are search
excerpts of the named vendor pages (vendor hosts were egress-blocked); all
release dates and prices are the vendor's own announcement unless a line
says independent. Open-weight detail is in `docs/OPEN-WEIGHT.md`.

**Ledger.** The 1M-context field got wider in one week: Claude Opus 5.5
(2026-09-22, 1M context, 128K output, $4/$20 per MTok,
[overview](https://platform.claude.com/docs/en/models/opus-5-5/overview))
and GPT-6 Sol and Luna (2026-09-22, 1,050,000 context, Sol $2/$10, Luna
$0.10/$0.50 per MTok,
[announcement](https://openai.com/index/introducing-gpt-6-sol-and-luna/)).
Ledger's `why` is "1M context for filings; the frontier still leads
annual-report QA", and Gemini held that seat partly because it was the 1M
option. It no longer is the only one. No annual-report QA number exists yet
for any of the three, so there is no evidence to reassign on; the ledger
decides, per the page above. Two new academic benchmarks bear on the seat:

- **FinInteract** (arXiv 2609.24002, submitted 2026-09-21, independent,
  [abs](https://arxiv.org/abs/2609.24002)): 173 bilingual filings-QA items
  where the question is underspecified (consolidated versus segment
  "operating income"). Models score above 90% when the interpretation is
  given and at most 28.9% when they have to elicit it. For the desk this is
  a contract point, not a model point: **Ledger's brief must pin the
  definition** before the seat reads, or the answer is a coin flip on which
  line item the model picked.
- **FinFIRST** (arXiv 2609.25192, submitted 2026-09-21,
  [abs](https://arxiv.org/abs/2609.25192)): 123 expert-written financial
  search tasks graded on the answer and on the evidence trail. Authors are
  Ant-affiliated and released it with their own finance model, so treat it
  as vendor-adjacent. Excerpted result: Claude Opus 5 at 87.6% loose pass
  and 69.1% strict pass, the top score. The strict-versus-loose gap is the
  number the desk cares about: it is the cost of demanding the citation.

**Grok.** Grok 4.7 (2026-09-21, 500K context, $2/$6 under 200K and $4/$12
above, [news](https://x.ai/news/grok-4-7)). On the same day xAI moved X
Search to per-post billing at $5 per 1,000 posts fetched
([docs](https://docs.x.ai/)). The seat's capability is unchanged; its cost
model is not, and the Grok brief should cap posts fetched per run.

**Wire.** No dated change to Gemini grounding since the roster was written.
Perplexity is retiring Sonar chat completions on 2026-09-27 and moving
`sonar` to its Agent API on 2026-09-25 (announced 2026-08-13,
[notice](https://community.perplexity.ai/t/sonar-is-moving-to-the-agent-api/5802)).
The desk does not roster Perplexity; noted so nobody adds it this week.

**Chain, Pulse, Shadow, CoS.** The workhorse family moved to Qwen3.8-27B
(Apache-2.0, 2026-08-14). Same seat, same reason; the pin is a box decision
and a question for Max.

**Jev.** Nothing changed for gpt-oss-120b. No new open reasoning model in
window has an independent evaluation, so the pool stands.

**Odds, Rails.** Claude Opus 5.5 is the same vendor the seats already use;
no capability change, so no roster change.

The organising rule still holds after all of this: none of the above is a
reason to add a second model to a seat. Each is either a cost change, a
contract change, or a candidate with no independent number yet.
