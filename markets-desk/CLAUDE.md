# Claude context — Markets Desk

Read `AGENTS.md` first; it is the contract for every agent here. Then
`HANDOFF.md` for the plan and current state, then `codex-feed/DOCTRINE.md`.

## Primary artifacts

- `codex-feed/MODE.yaml` is the authority and `desk/risk.py` executes it.
  Change policy in YAML, never by special-casing the engine.
- Contracts refuse on load. When one refuses your file, the refusal is the
  finding — fix the file or, if the contract is wrong, fix the contract with
  a test that shows why.

## Taste

Stdlib Python plus PyYAML. Hand-rolled validation, `unittest`, no framework.
Docstrings say why, and cite the failure that motivated the rule when there
was one. Prose is terse and directive; a recommendation, not a menu. The
public name is always **Max Motif**, never "Motif".

## What the desk is not

Not a trading bot, not an ensemble, not a consensus mechanism. Seats are
assigned by capability the desk lacks, never as a second vote. Two models
agreeing is not evidence.

## Reporting

Smallest coherent patch. Files changed, what changed for the desk,
verification with the test count, what is unverified, questions for Max.
Do not merge, publish, or mark a PR ready without Max's explicit approval.
