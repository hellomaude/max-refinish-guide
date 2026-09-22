# Open-weight models on the desk

What open weights are for here, which ones, on which seats, and the evidence.

**Gathered from search-engine summaries** — arXiv and the benchmark hosts were
egress-blocked from this session, so figures are as the abstracts report them.
The landscape moves monthly; the model ids in `ROSTER.yaml` are families, and
the box pins versions.

---

## What open weights buy, and what they do not

They do not buy intelligence. On the two finance benchmarks with a clear
leaderboard the frontier still leads: Claude Opus 4.6 tops Financial
Touchstone's annual-report QA at **88.4%**, with the best open-weight model
(Kimi K2.6) third; on BizFinBench.v2 the best open model is Qwen3-235B-Thinking
at 53.3%.
([Financial Touchstone](https://arxiv.org/abs/2608.08634),
[BizFinBench.v2](https://arxiv.org/pdf/2601.06401))

They buy three things the desk actually needs:

1. **The book stays on the box.** A ticket read by a local model is read by
   nobody else. The pack — CoS's output — is the single most sensitive
   document the desk produces, and it should never transit a vendor.
2. **A different vendor from every proposer, by construction.** The
   adversary rule (`docs/MODELS.md`) needs Jev to be a model the ticket's
   author is not. A local open-weight challenger satisfies that against every
   frontier seat without a second API bill.
3. **Cost that lets the contract do the work.** Four research seats are
   adapter-fed: the number comes from code and the seat writes YAML the
   contract will refuse if it is wrong. A 27B on one GPU is enough for that,
   and paying frontier rates to format a funding read is waste.

And one finding that closes a door: **finance fine-tunes underperform general
models.** Dianjin-R1, a dedicated finance model, trails plain Qwen3-32B by
5.6 points on BizFinBench.v2. Do not chase "FinLLM" checkpoints. Take the
best general model and let the contracts enforce the domain.

---

## The models

| Model | Licence | Hosting | Why it is on the roster |
|---|---|---|---|
| **gpt-oss-120b** | Apache-2.0 | local (~80 GB) | Reasoning model with configurable effort. Best reasoning-per-gigabyte with a clean licence. **The default adversary** at `effort=high` ([model card](https://openai.com/index/gpt-oss-model-card/)) |
| **Qwen3.6-27B** | Apache-2.0 | local (one GPU) | Dense 27B, 256K context, strong structured output. **The adapter-fed workhorse** ([Morph ranking](https://www.morphllm.com/best-open-source-llm)) |
| DeepSeek-V4.1-Flash | MIT | api | 552B MoE / 8–16B active, 1M context, frontier-class tool use, cheap. Declared for when a hosted open model is wanted; **not yet assigned** ([Wavect comparison](https://wavect.io/blog/open-weight-llm-comparison-2026/)) |
| GLM-5.3-Flash | MIT | api | 320B / 18B active; GLM 5 placed fourth on annual-report QA. **Ledger's fallback** |

**Considered and not rostered:**

- **Kimi K3** — best open model overall (Terminal-Bench 88.3, 1M context) but
  2.8T parameters and a licence with conditions for commercial products.
  Not local, and the licence needs a read before a product studio leans on it.
- **Qwen3.8-Max** — top of the open leaderboard, but under a conditional
  licence. The 27B Apache checkpoint is the one to use.
- **Llama 4** — Maverick at Q4 fits a 128 GB Mac Studio, but the policy
  withholds multimodal rights from EU developers; nothing here needs it over
  Qwen.
- **Any "finance" fine-tune** — see above.

---

## The assignments

| Seat | Model | Leaves the box? | Why |
|---|---|---|---|
| Chain | Qwen3.6-27B | no | funding/OI come from the adapter; the seat writes YAML |
| Pulse | Qwen3.6-27B | no | GEX is computed; the seat refuses an untimestamped chain |
| Shadow | Qwen3.6-27B | no | ownership XML is parsed by code; **filings under review stay local** |
| CoS | Qwen3.6-27B | no | the pack is the most sensitive artefact; compression is well within a 27B |
| **Jev** | pool: gpt-oss-120b first | no (for the default) | a different vendor from every frontier proposer; argued on the box |
| Ledger | Gemini, fallback GLM-5.3-Flash | yes | annual-report QA is where the frontier still wins |
| Odds | Claude | yes | rules-lawyering resolution text decided WKND-002 |
| Wire | Gemini | yes | open models have no native search |
| Rails | Claude | yes | wrote the engine and its tests |
| Grok | Grok | yes | live X; no substitute exists |
| Codex | Codex | yes | doctrine |

`desk validate` now prints which seats are on the box. Today: **Chain, Pulse,
Shadow, CoS**, plus the default adversary.

Two rules in `ROSTER.yaml` make this hold rather than drift:

- `adversary_pool_needs_local: true` — Jev's pool must contain a local model,
  so every frontier-authored ticket can be challenged without leaving.
- The pool also carries non-Qwen members, so a ticket from a Qwen seat still
  gets a non-Qwen adversary. `validate` refuses a pool naming an undeclared
  model.

---

## Running it

The four Qwen seats and the default adversary fit one workstation:

- **Qwen3.6-27B** at Q4_K_M ≈ 16 GB. One consumer GPU or any Apple Silicon
  with 32 GB.
- **gpt-oss-120b** ≈ 80 GB at its native MXFP4. A 128 GB Mac Studio holds
  both with room; a 24 GB GPU holds Qwen alone, and the adversary can go to
  the next pool member until the box grows.
  ([local hardware guide](https://huggingface.co/blog/daya-shankar/open-source-llm-models-to-run-locally))

Serve with vLLM on Linux/NVIDIA or MLX via Ollama on Apple Silicon. Both
expose an OpenAI-compatible endpoint, which is all a seat needs: it is
prompted with the brief and the template, and it writes a file. The desk
does not know or care what produced the file — that is the whole design.

Pin the version on the box, in the serving config, not in `ROSTER.yaml`.

---

## What decides whether this was right

The ledger. `desk score` by model, after thirty resolved outcomes. If the
Qwen seats' tickets carry a negative expectancy the frontier seats do not,
move them back and keep the ledger rows as the record. If gpt-oss's
challenges are not separating winners from losers (`challenge_report`), the
adversary needs a stronger model in the pool's first slot. The roster is a
hypothesis; the ledger is the test.
