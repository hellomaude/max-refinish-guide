# Markets Desk
Idea: A research desk of model-held seats whose output a risk engine stamps with ceilings, so Codex can format order sheets only inside them and only after Max confirms.
Track: build → land on box
Stage: built and tested against fixtures; unmerged; no adapter has touched a live endpoint
Started: 2026-09-20
Branch: claude/financial-system-codex-grokvot-3ho3jh (PR #1, draft, green, mergeable)
Decisions: MODE.yaml is the authority; the engine executes it, prose does not interpret it.
Decisions: mode live_confirm, execution research_packs_only; every venue live:false; equity/etf/perp/option enabled:false. Arming is Max's edit alone.
Decisions: Correlated ideas share one theme cap; water-filling allocates under it; a single-name override is a one-member theme.
Decisions: Freshness is keyed on as_of, never fetch time; stale FAILs; naive timestamps are refused.
Decisions: Hard evidence originates, soft corroborates; soft_evidence_only is a FAIL.
Decisions: Jev must file before size; adjustments only subtract; Jev never originates.
Decisions: The adversary must be a different model from the proposer; a self-review challenge does not count.
Decisions: Models are assigned by capability the desk lacks, never as a second vote; scored by model as well as by seat.
Decisions: Chain, Pulse, Shadow, CoS run on Qwen3.6-27B locally; gpt-oss-120b leads the adversary pool; the pack never leaves the box.
Decisions: Grok is steered by desk-issued assignments and graded by desk coach; it never picks its own subjects.
Decisions: No finance fine-tunes; general models plus contracts.
Decisions: One allowlisted POST in adapters/base.py; PUT/PATCH/DELETE banned everywhere.
Decisions: The ledger scores forward only; no backfilled outcomes.
Open: Max — merge PR #1; name an equity venue or not; keep require_challenge true (recommended).
Open: Box — preflight all 18 sources; wire EDGAR owner histories; re-verify WKND-002; Grok's first report; dashboard (Phase 4).
Artifacts: plan=HANDOFF.md doctrine=codex-feed/DOCTRINE.md seats=docs/SEATS.md models=docs/MODELS.md open-weight=docs/OPEN-WEIGHT.md evidence=docs/EVIDENCE.md risk=docs/RISK-MODEL.md pr=hellomaude/max-refinish-guide#1
