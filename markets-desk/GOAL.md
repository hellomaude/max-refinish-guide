# GOAL — Markets Desk, to completion

**Paste this as the opening message of a new agent session. It is the whole
job. Work until every line in §2 is true, then stop.**

You are the build agent for Max Hahn's (Max Motif) Markets Desk in
`hellomaude/max-refinish-guide`, under `markets-desk/`. Read `AGENTS.md`
first, then `.motif/STATE.md`, then this file. The plans are `HANDOFF.md`
(the desk on the box) and `HANDOFF-NATIVE.md` (the Mac and iPhone agent).
This file is the goal they serve, and the loop you run until it is met.

---

## 1. The goal

> **A fully functioning research desk, running on Max's Mac, with every
> seat filing, every ticket challenged and stamped, Max confirming from his
> iPhone, and Codex formatting order sheets only from those confirms — proven
> on paper for two weeks — so that the day Max names a broker, nothing
> changes but one line in `MODE.yaml`.**

It is a trading agent in the only sense this desk permits: every seat's
work, stamped, in Max's hand, and one deliberate tap. It never trades on its
own. If a step seems to need it to, you have misread the step.

---

## 2. Definition of done

Work is complete when **all** of these hold, in order. Each is checkable.
Do not mark one done because it is nearly done.

**Desk on the box** (`HANDOFF.md` Phases 0–3)
- [ ] `python -m unittest discover -s tests -t . -q` green on the Mac; count ≥ the number in `.motif/STATE.md`.
- [ ] `python -m desk preflight --strict` passes with every source Max holds a key for reporting `ok`; the rest recorded as `no_auth` or `geo_blocked`, never `unreachable`.
- [ ] All five `fetch` verbs return evidence with real `as_of` stamps from live endpoints; every field-name drift fixed in the adapter with a fixture from the real response.
- [ ] `fetch Shadow` files `opportunistic_buyers` and `routine_buyers` from real owner histories.
- [ ] WKND-002's evidence re-fetched; the ticket's `as_of` is current and the CLOB depth is on file.
- [ ] `codex-feed/connectors.json` exists and `desk validate` refuses a book whose seat dependencies are absent or dark.
- [ ] Qwen3.6-27B and gpt-oss-120b served on loopback; `desk validate` prints four seats on the box.
- [ ] Gemini has filed a report that passed the contract; Grok has filed one that passed `assign --audit --strict`.
- [ ] Every ticket and challenge filed since this goal began carries `model:`, and `stamp` has counted at least one challenge from a model that differs from the proposer.

**The native agent** (`HANDOFF-NATIVE.md` Phases N0–N5)
- [ ] `desk/confirm.py` and `confirmations/` exist; a confirm on PENDING, on a stale hash, past expiry, or by anyone but `max` is refused, each under test.
- [ ] `tests/test_boundary.py` fails if any sheet-formatting path is reachable without a `Confirm`.
- [ ] `desk serve` runs, loopback by default, with exactly one mutating route (`/confirm`), token-gated; the boundary test asserts the count.
- [ ] `desk daemon` has run the full cadence for five consecutive weekdays with every session in `preflight/` and every push in a log; a deliberately broken source produced exactly one push.
- [ ] Max has confirmed a paper ticket from the Mac app, and Codex formatted a sheet from that confirm file and nothing else.
- [ ] Max has confirmed a paper ticket from the iPhone, away from the Mac, and the sheet carries `device: iphone`.
- [ ] Every screen on both apps shows the age of its data; nothing can look live when it is not.

**Proven on paper**
- [ ] Ten paper outcomes in `ledger/`, forward-only, skips included.
- [ ] `desk score` runs in the morning session and its by-model table has rows.
- [ ] Two weeks of `stamp` agree with Rails' manual stamp, or every disagreement is resolved into a `MODE.yaml` correction or an engine fix with a test.
- [ ] Time from `pass` to confirm, measured over the two weeks, is under five minutes at the median.
- [ ] `MODE.yaml` still has every venue `live: false` and `execution: research_packs_only`. **You did not change this. You will not.**

When the last box is ticked, write the final report (§7), update
`.motif/STATE.md` to `Stage: paper-complete; awaiting Max's gate`, and stop.

---

## 3. Never

These are enforced by `tests/test_boundary.py` and by Max. Not one is
negotiable, and finding a clever way around one is the failure, not the win.

- Never write order-placing machinery, signing material, wallet code, or a
  mutating HTTP verb outside the allowlist.
- Never set any venue `live: true`. Never move `execution` off
  `research_packs_only`. Never name a broker in `MODE.yaml`. Those three
  edits are Max's, by hand, after §2 is complete.
- Never delete or weaken an assertion in `tests/test_boundary.py`.
- Never invent a fill, a price, a fact, an `as_of`, or a base rate. Stale
  is a FAIL. Unknown is `no_read`.
- Never let a seat originate on soft evidence. Never let Jev originate, add
  conviction, or be the proposer's own model.
- Never cache, batch, schedule, or auto-renew a confirm. One tap, one
  session, one ticket.
- Never put a model, an API key, a broker credential, or the pack on the
  iPhone.
- Never commit a secret. Never paste the pack into a web chat.
- Never merge, publish, or mark a PR ready for review. Max merges.
- Never reference any other repository, project, or system of Max's. This
  desk stands alone.

---

## 4. The loop

Run this every session until §2 is met.

1. **Orient.** Read `.motif/STATE.md`. Find the first unticked line in §2
   whose prerequisites are ticked. That is the task. If none qualifies, the
   task is whatever blocks the next one.
2. **Branch.** `codex/desk-<topic>` or `claude/<topic>`. One topic.
3. **Build.** Smallest coherent change. A new rule ships with a test that
   fails without it. A new adapter ships with a real-response fixture.
4. **Verify.** The suite, `desk validate`, `desk stamp`. Then the specific
   done-condition, by running it, not by reasoning that it would pass.
5. **Record.** Update `.motif/STATE.md`: tick nothing in this file — the
   ticks are Max's — but record the decision and the evidence. Commit with
   a message that says why.
6. **Push and open a draft PR** to `main` with the report format in §7.
   Do not mark it ready.
7. **Continue** to the next task. Do not wait for the merge unless the next
   task depends on it; then say so in the PR and pick a task that does not.

If a session ends mid-task, `.motif/STATE.md` carries enough for the next
one to resume. That file is the memory; keep it current.

---

## 5. Stop and ask Max — only for these

Everything else, decide and proceed. Stop for:

- A step needs a **key, credential, purchase, or account** you do not have.
  Name it, say which done-condition it blocks, and move to one it does not.
- A **contract refuses something that seems right.** Do not loosen the
  contract. Show Max the refusal and the file; let him say which is wrong.
- Two done-conditions **conflict** in practice. Say how, propose which
  yields, proceed on your proposal if he is silent for a session.
- Anything that would require touching `venues.*.live`, `execution`, a
  broker name, or `test_boundary.py`'s assertions. **Do not proceed on
  silence here. Ever.**

One question per PR, at the top, with the recommended answer first.

---

## 6. What good looks like

- The desk refuses more than it accepts. A morning where every ticket is
  PENDING or FAIL and the report says why is a working desk, not a broken one.
- Numbers come from adapters; prose comes from seats; ceilings come from
  Rails; the tap comes from Max. No layer does another's job.
- Every timestamp has an offset. Every screen shows its age. Every claim in
  a doc has a source, and says when the source was not read in full.
- The commit log reads as a record of decisions, not a changelog.

---

## 7. Report format

Every PR body, and the final report:

```
## What changed for the desk
<seat / gate / number — not files>

## Done-conditions advanced
<which lines in GOAL.md §2, and the evidence: a command and its output>

## Verification
<test count before → after; validate; stamp; the specific check>

## Unverified
<what could not be checked from here and why>

## For Max
<at most one question, recommended answer first — or "nothing">
```

---

## 8. Where you are right now

`main` carries the desk at 268 tests, merged 2026-09-22. No adapter has
touched a live endpoint. No local model is served. No confirm contract
exists. No app exists. `.motif/STATE.md` has the decisions to date.

The first task is `HANDOFF.md` Phase 0. Go.
