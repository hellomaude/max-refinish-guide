# Markets Desk — agent instructions

Read this first, whatever you are. Codex reads it natively; Claude reads
`CLAUDE.md`, which points here. `GOAL.md` is the goal and the loop;
`HANDOFF.md` and `HANDOFF-NATIVE.md` are the plans; `HANDOFF-LOCAL.md` is the
part only a session on Max's Mac can do; `.motif/STATE.md` is the state.

## Identity

This is Max Hahn's (Max Motif) research desk: a set of seats that produce
tickets, challenges and reports, a risk engine that stamps ceilings on them,
and an execution path (Codex) that formats order sheets **only inside those
ceilings and only after Max confirms**. Nothing in this package places an
order, moves money, signs anything, or connects a wallet. It never will.

The one-line doctrine: **information moves, money never** — until Max says,
and then only as far as Max says.

## Hard rules

- Never add order-placing machinery, signing material, wallet code, or a
  mutating HTTP verb. `tests/test_boundary.py` fails the build on any of it and
  the assertion is the review — do not delete one to make a test pass.
- Never set any venue `live: true` or move `execution` off
  `research_packs_only` in `codex-feed/MODE.yaml`. That edit is Max's alone.
- Never invent a fill, a price, a fact, or an `as_of`. A number without a
  source and a timestamp does not go in a file. Stale is a FAIL, not a discount.
- Never let a seat originate on soft evidence alone (`social`/`news`/
  `sentiment`). Jev never originates at all, and never adds conviction.
- No pumper X sources. No eToro. No paid Quiver. Auto-trade paths in any
  cloned repo stay disabled.
- No secrets, keys, or account identifiers in the repo. Keys live in env vars
  on the box; the FRED adapter already redacts its key from error text — keep
  that standard.
- Do not merge, publish, or mark a PR ready for review without Max's explicit
  approval. Pushing to your working branch is expected; nothing else is.
- Branch names: `codex/desk-<topic>`, `claude/<topic>`, `cursor/<topic>`.
  One topic per branch, PR to `main`, Max merges.

## Hot files

- `codex-feed/MODE.yaml` — the authority: caps, themes, event windows,
  freshness, venues. If it and prose disagree, it wins.
- `codex-feed/ROSTER.yaml` — which model holds which seat, and why.
- `desk/risk.py` — the engine. Gate order is documented in `_ceiling_for`.
- `desk/ticket.py`, `challenge.py`, `report.py`, `assign.py` — the four
  contracts. They refuse on load; read the refusal before working around it.
- `desk/confirm.py`, `desk/sheet.py` — the gate as code. A sheet needs a confirm.
- `desk/serve.py`, `desk/ui.py` — the page and the API; one write, `/confirm`.
- `desk/daemon.py`, `codex-feed/CADENCE.yaml` — the clock. Never fetches for a seat, never confirms.
- `tests/test_boundary.py` — the guard.
- `docs/SEATS.md` — every seat's contract and what gets its output refused.
- `prompts/` — paste-ready prompts for running a seat in a web chat.

## Acceptance

Every change must leave these true:

```bash
python -m unittest discover -s tests -t . -q   # all green; count only goes up
python -m desk validate                        # passes
python -m desk stamp                           # renders; allocated ≤ heat cap
```

A new rule gets a test that fails without it. A new adapter gets a fixture
from a real response and a boundary check. A doc claim gets a source.

## Reporting

When you finish, report: files changed; what changed for the desk (which
seat, which gate, which number); verification performed with the test count;
what is unverified and why; open questions for Max. Smallest coherent patch.
