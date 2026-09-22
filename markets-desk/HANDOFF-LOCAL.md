# Markets Desk — local handoff: finish it on the Mac

**For:** a Claude Code (or Codex) session running **on Max's Mac**, with Xcode,
network, and his keys. **Not** for a cloud session — everything below needs
the box. **Written:** 2026-09-22, from a cloud session that could reach none of it.

Read `AGENTS.md`, then `GOAL.md` §1–§3, then this. `GOAL.md` is the goal;
this is the part of it only a local agent can do, in the order that makes
each failure cheap.

---

## 0. What you have that the last agent did not

The previous session built and tested everything against fixtures from a
Linux container with no Swift toolchain, no market-data egress, no push
service, and no Mac. It could not compile a line of Swift, probe a single
source, or send one push. You can. Every "unverified" in the PR bodies for
#1–#5 is yours to verify, and most will need a small fix.

What is real: 345 Python tests, `desk validate`, the risk engine, the
contracts, `desk serve` with the page, the daemon, the install kit, and
Swift source for two apps. What is untested: the adapters against live
endpoints, the LaunchAgents, `notify.send` against a real service, and all
of the Swift.

---

## 1. Definition of done, local

Tick nothing in `GOAL.md`; Max ticks. Your job is to make these true and
report the evidence.

- [ ] `install/launch-mac.sh` runs end to end and prints "Mac app is up".
- [ ] `swift test` green in `apps/apple`; DeskMac builds and opens; DeskPhone builds to a device.
- [ ] `desk preflight --strict` passes with every keyed source `ok`; every failure recorded as `no_auth`/`geo_blocked`, never `unreachable`.
- [ ] All five `fetch` verbs return evidence with real `as_of` from live endpoints; every field drift fixed in the adapter with a real-response fixture and a test.
- [ ] `desk daemon --once morning` runs clean (not dry-run) and one push arrives on Max's phone.
- [ ] The phone is paired and a paper confirm from the iPhone produced a `confirmations/*.confirm.yaml` with `device: iphone`, and `desk sheet` wrote a paper sheet from it and refused without it.
- [ ] `state/env` holds the keys Max has; nothing else in the repo does.
- [ ] `MODE.yaml` untouched: every venue `live: false`, `execution: research_packs_only`.

---

## 2. Order of work

### L0 — Run the launcher, read what breaks

```bash
curl -fsSL https://raw.githubusercontent.com/hellomaude/max-refinish-guide/main/markets-desk/install/launch-mac.sh | bash
```

It gates on the Python suite, installs the LaunchAgents, opens the page,
then tries the Swift. **Expect the Swift step to fail the first time** —
the source has never met a compiler. Do not touch anything before this
step; the failures it prints are the work list.

### L1 — Make the Swift compile

`cd ~/desk/markets-desk/apps/apple && xcodegen generate && open Desk.xcodeproj`.
Build DeskMac. Fix errors in this order: DeskKit (models, client, pairing,
store) → DeskUI → app targets. Then `swift test`. Rules that must survive
the fixes, because `tests/test_apple.py` reads the source:

- exactly one `httpMethod = "POST"`, in `DeskAPI.swift`, to `/confirm`
- `URLSession`/`URLRequest` only in `DeskAPI.swift`
- `SecItem*` only in `Pairing.swift`, one item
- every date shown through `AgeLabel`
- no key, model, vendor or pack string anywhere

Likely trouble spots, from reading it cold: `@Observable` + `@Bindable`
usage on a store passed by reference; `LabeledContent` with a trailing
closure on macOS; `DragGesture` hold timing on macOS vs iOS; `Bundle.module`
for the fixture in the test target; `appending(path:)` availability. None of
these is a design problem.

Run the Python suite after every Swift edit. It is fast and it is the guard.

**Done when** `swift test` is green, DeskMac opens and shows the book with
ages, and the Python suite is still green.

### L2 — Prove the data layer live

```bash
cd ~/desk/markets-desk && set -a && . state/env && set +a
.venv/bin/python -m desk preflight --out preflight/$(date +%F).json
```

Then each fetch:

```bash
.venv/bin/python -m desk fetch Odds   --slug clarity-act-signed-2026 --outcome No
.venv/bin/python -m desk fetch Chain  --coin BTC --coin ETH
.venv/bin/python -m desk fetch Pulse  --symbol _SPX
.venv/bin/python -m desk fetch Shadow --cik 883902 --ticker SBLK
.venv/bin/python -m desk fetch Ledger --series 2s10s
```

For every failure: fix the adapter, save the real response (redacted of
nothing sensitive — these are public endpoints) as a fixture under
`tests/fixtures/`, and add the test that would have caught it. Keep the
boundary: no new POST outside `adapters/base.py`, no new host that is not
a data source.

Two specific jobs here:

- **EDGAR owner histories.** Wire the per-owner `submissions` call that
  feeds `is_routine()` (reporting-owner CIK → their Form 4 dates), respecting
  10 req/s. `fetch Shadow` must file `opportunistic_buyers` and
  `routine_buyers`.
- **WKND-002.** Re-fetch, update the ticket's evidence `as_of`, read the
  CLOB depth at 92.5 and put it in the ticket. That is Jev's open condition.

**Done when** `preflight --strict` passes for every keyed source and all
five fetches return live `as_of` stamps.

### L3 — Pair the phone, confirm once on paper

```bash
.venv/bin/python -m desk pair --host <tailnet-ip> --qr
```

Build DeskPhone to the iPhone from Xcode; pair it. To have something
confirmable without touching policy: on a **temporary copy** of the desk
(`cp -r ~/desk/markets-desk /tmp/desk-paper`), set `required_seats: []`
and `require_challenge: false` in the copy's `MODE.yaml`, drop in the
passing ticket from `tests/test_serve.py::_passing_desk`, and run
`desk serve --root /tmp/desk-paper --bind <tailnet-ip>`. Confirm it from
the phone. Then:

```bash
.venv/bin/python -m desk confirm --list --root /tmp/desk-paper   # if --root is absent, pass paths explicitly
.venv/bin/python -m desk sheet T-PASS --risk-budget 100000 --out /tmp/desk-paper/sheets
```

The sheet must say `PAPER SHEET`, carry `device: iphone`, and `sheet` must
refuse on the real desk where no confirm exists. Delete the copy after.

**Never** edit the real `MODE.yaml` to make a ticket pass. That is the gate.

**Done when** a confirm file with `device: iphone` exists in the copy, a
paper sheet was written from it, and the real desk still refuses a sheet.

### L4 — Push, for real

Put `NTFY_TOPIC` (or Pushover) in `state/env`, subscribe the phone, then:

```bash
.venv/bin/python -m desk daemon --once morning
```

One push should arrive (the book has PENDING tickets and Rails is dark, so
`seat-dark:Rails` fires). Run it again inside four hours: nothing should
arrive — that is the dedup. Check `state/daemon.log` and `state/push.json`.

**Done when** one push arrived, the second run was suppressed, and both are
in the log.

### L5 — Local models and the seats

Serve Qwen3.6-27B and gpt-oss-120b on loopback (Ollama or vLLM). `desk
validate` should print four seats on the box. Then get the first real
report filed: paste `prompts/RESEARCH_SEAT_PROMPT.md` into Gemini's web
chat for Ledger with the assignment slot filled from the current
`assignments/`, put the YAML in `reports/`, and `desk validate`. Then the
same for Grok with `codex-feed/BRIEF-GROK.md` and `desk assign Grok
--audit --strict`. Expect refusals; fix the file, not the contract.

**Done when** two real reports pass the contracts and one assignment audit
passes `--strict`.

### L6 — Hand back

Update `.motif/STATE.md`, open one PR per phase on `codex/desk-<topic>` or
`claude/<topic>`, and write the report format from `GOAL.md` §7 in each.
Then `GOAL.md` §4 takes over — the loop runs until the two-week paper
period is done.

---

## 3. Stop and ask Max — only for these

Same four as `GOAL.md` §5: a missing key or purchase; a contract that
refuses something that looks right (show him the refusal, do not loosen
it); two conditions that conflict; and anything touching `venues.*.live`,
`execution`, a broker name, or a `test_boundary.py` assertion — **never on
silence for that last one.**

One local addition: **do not `sudo` anything except the `pmset` line in
`install/README.md`**, and say so before you do.

---

## 4. Report format

Per phase, in the PR body and to Max:

```
## What changed for the desk
## Done-conditions advanced   (from §1 here and GOAL.md §2, with the command and its output)
## Verification              (Python test count before → after; swift test; the specific check)
## Unverified
## For Max                   (one question, recommended answer first — or "nothing")
```

---

## 5. Where you are

`main` at the #4 merge carries everything; PR #5 adds the launcher. Nothing
has run on a Mac. Start at L0. The first thing you will learn is what the
Swift compiler thinks of code written blind, and that is the most useful
thing anyone on this project has not yet learned.
