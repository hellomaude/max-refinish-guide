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

---

## Update 2026-09-23

Routine refresh. **Same caveat as the page header:** huggingface.co,
arxiv.org, openai.com, z.ai, deepseek.com, qwen.ai and artificialanalysis.ai
were egress-blocked from this session too. Every figure below is the search
engine's excerpt of the named primary page, and each line says whether the
figure is the vendor's own or an independent evaluation. Nothing is written
from memory; where the number could not be seen it is marked unverified.

### The finance benchmark this page cites, now traced to its source

The 88.4% figure in the header and in Ledger's `why` comes from
*Can Open-Weight Models Compete on Financial Text Comprehension?*, arXiv
2608.08634, Jan Spörer, University of St. Gallen, submitted 2026-08-09
([abs](https://arxiv.org/abs/2608.08634)). Independent, academic. The
abstract as excerpted: the 2026 update of Financial Touchstone has 2,967
question-context-answer triplets over 495 annual reports and twenty models
from ten providers; Claude Opus 4.6 has the highest accuracy at 88.4%,
Gemini 2.5 Pro the lowest hallucination rate at 0.08%, Kimi K2.6 is third,
the non-reasoning GLM 5 and Mistral 3 fourth and fifth, and retrieval
accounts for 48.9% of all failures.

Two things to carry when citing it:

- There are **two editions**. The original (ACM ICAIF 2025, eleven models,
  [doi](https://dl.acm.org/doi/10.1145/3768292.3770417)) has Gemini 2.5 Pro
  at 91.6% and does not include Opus 4.6. A "Financial Touchstone" number
  without an edition is ambiguous; the roster's number is the 2026 one.
- Every model got the same top-5 retrieved chunks, so the accuracy gap is
  the reader, not the retriever. That is the right comparison for Ledger,
  which is fed by adapters.

The BizFinBench.v2 figures (Qwen3-235B-A22B-Thinking-2507 at 53.3%, best
open model; Dianjin-R1 at 35.7%, trailing Qwen3-32B by 5.6 points; an 8.2
point gap to GPT-5; 21 models) are as the abstract of arXiv 2601.06401 is
excerpted ([abs](https://arxiv.org/abs/2601.06401)). Independent, though
the authors are a Chinese brokerage's research group. No new BizFinBench or
Financial Touchstone results were found since 2026-09-15.

### Open-weight releases since the page was written

- **Qwen3.8-27B** (Apache-2.0, 2026-08-14 per the QwenLM/Qwen3.8 news list)
  supersedes the Qwen3.6-27B this page rosters
  ([Qwen3.6-27B card](https://huggingface.co/Qwen/Qwen3.6-27B), released
  2026-04-22, 262,144 native context). The roster ids are families and the
  box pins the version, so nothing breaks, but the four adapter-fed seats
  are on a checkpoint one generation old. **Question for Max:** move the
  pin, or wait for a finance number on 3.8.
- **Ternary Bonsai 2 27B** (PrismML, 2026-09-17, Apache-2.0): a ternary
  compression of Qwen3.8-27B at about 5.9 GB with 262K context. The vendor
  claims 98.2% of the FP16 benchmark average
  ([card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)).
  **Vendor claim, no independent evaluation, no finance benchmark.** Not
  for the roster until someone else has measured it.
- **Ling-3.0-flash-Fin** (Ant Group, 2026-09-16, MIT, 124B total / 5.1B
  active MoE, 256K context;
  [card](https://huggingface.co/inclusionAI/Ling-3.0-flash-Fin)). A finance
  fine-tune, so the header's rule applies. The vendor card lists finance
  evals (FinFIRST, FinSearchComp, Finance Agent, τ³-Banking); the numbers
  could not be read and are **unverified**. The one independent figure
  found is Artificial Analysis's Finance & Accounting Index at 24 against a
  leader at 56 ([changelog](https://artificialanalysis.ai/changelog),
  index v1.1 dated 2026-09-16, search excerpt). Consistent with "finance
  fine-tunes trail general models"; not a reason to change anything.
- **MiMo-V2.6-Flash** (Xiaomi, 2026-09-22, MIT, 309B total / 15B active,
  1M context, [card](https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Flash-RL)).
  Vendor-announced. Hosted-only at that size; a second MIT 1M-context option
  beside DeepSeek-V4.1-Flash, and no finance number yet.
- **Kimi K3** is now on Amazon Bedrock (AWS what's-new, 2026-09-18,
  [note](https://aws.amazon.com/about-aws/whats-new/2026/09/moonshot-ai-kimi-k3-on-amazon-bedrock/)).
  The licence is the custom "Kimi K3 License" with a revenue-threshold
  clause ([repo](https://github.com/MoonshotAI/Kimi-K3)), which is what the
  header meant by "conditions". Vendor README finance figures exist
  (CorpFin v2, Finance Agent v2, τ³-Banking) and are **vendor-reported**;
  not written here as numbers.
- **Qwen3.8-Max** is an API name. The open weights ship as
  `Qwen/Qwen3.8-2.4T-A95B` (2026-08-12, custom "Qwen3.8-Max License",
  2.4T / 95B active, 262K context). No page named "Qwen3.8-Max" exists on
  Hugging Face; the header's line is right on the licence and should be
  read with the real weight name.

### The rostered open models: no change

- **gpt-oss-120b**: Apache-2.0, 117B total / 5.1B active, single 80 GB GPU
  per the GitHub README; released 2025-08-05, no 2026 update found. Context
  length unverified from the card.
- **DeepSeek-V4.1-Flash**: MIT, 552B, 8B active prefill / 16B decode, 1M
  context; released 2026-09-10 ([news](https://www.deepseek.com/en/news/deepseek-v4-1-flash/)).
- **GLM-5.3-Flash**: MIT, 320B / 18B active, 1,048,576 context; weights
  2026-08-25 ([blog](https://z.ai/blog/glm-5.3-flash)).

Jev's default is unchanged. The adversary pool has no new member worth
adding on evidence rather than on a vendor card.
