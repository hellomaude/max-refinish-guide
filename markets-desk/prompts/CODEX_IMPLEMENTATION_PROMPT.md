# Codex implementation prompt — Markets Desk

You are editing `markets-desk/` in `hellomaude/max-refinish-guide`. Read
`AGENTS.md`, then `HANDOFF.md`, then `codex-feed/DOCTRINE.md` before touching
anything. Work on a branch named `codex/desk-<topic>`.

Task:
<PASTE MAX REQUEST HERE>

Constraints:
- Stdlib Python plus PyYAML. `unittest`. No new dependencies without saying why.
- Policy changes go in `codex-feed/MODE.yaml`, never as special cases in
  `desk/risk.py`.
- A new rule ships with a test that fails without it. A new adapter ships
  with a fixture from a real response and stays inside the boundary guard.
- Never touch `venues.*.live`, `execution`, or delete an assertion in
  `tests/test_boundary.py`. Those are Max's.
- Docstrings say why, and name the failure that motivated the rule.

Acceptance:
- `python -m unittest discover -s tests -t . -q` — all green, count not lower
  than before.
- `python -m desk validate` passes.
- `python -m desk stamp` renders and allocates no more than the heat cap.

Report: files changed; what changed for the desk (seat, gate, number);
verification with the test count; what is unverified and why; questions for
Max. Smallest coherent patch. Do not merge or mark the PR ready.
