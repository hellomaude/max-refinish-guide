# Markets Desk
Idea: A research desk of model-held seats whose output a risk engine stamps with ceilings, so Codex can format order sheets only inside them and only after Max confirms.
Track: build → land on box
Stage: system built — confirm contract, sheet path, serve + page, daemon + push, pair, install kit, connector manifest; native Mac + iPhone source written under apps/apple (uncompiled here); no adapter has touched a live endpoint
Started: 2026-09-20
Branch: main (PR #1 merged at 5e5ab79); follow-ups on codex/desk-* or claude/*
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
Open: Max — name an equity venue or not (after paper); keep require_challenge true (recommended).
Open: Box — preflight all 18 sources; wire EDGAR owner histories; re-verify WKND-002; Grok's first report.
Open: Local (HANDOFF-LOCAL.md L0–L6) — run the launcher, compile apps/apple on the Mac (xcodegen generate; swift test; ⌘R), fix what the compiler catches; two weeks paper (N5). See HANDOFF-NATIVE.md §3b.
Decisions: The native app is the window, the gate and the alarm — never a router. A confirm is a file Codex must read before any sheet; it requires verdict pass, a matching stamp hash, and Max.
Decisions: The iPhone holds no model, no key, no pack; desk serve has exactly one mutating route, /confirm.
Decisions: The served page (desk serve) is the UI on both Mac and iPhone until the native apps exist; it has one write, /confirm, and every timestamp shows its age.
Decisions: A confirm's digest binds the stamp and the mode; the book moving voids it and the daemon pushes.
Decisions: Push may reach only ntfy or Pushover; the daemon never fetches for a seat and never confirms.
Artifacts: goal=GOAL.md local=HANDOFF-LOCAL.md plan=HANDOFF.md native=HANDOFF-NATIVE.md doctrine=codex-feed/DOCTRINE.md seats=docs/SEATS.md models=docs/MODELS.md open-weight=docs/OPEN-WEIGHT.md evidence=docs/EVIDENCE.md risk=docs/RISK-MODEL.md pr=hellomaude/max-refinish-guide#1
