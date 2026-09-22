# Markets Desk — native handoff: the trading agent for Mac and iPhone

**Owner:** Max Hahn (Max Motif) · **Written:** Tue 2026-09-22 · **Builds on:** `HANDOFF.md` (the desk itself; Phases 0–7)
**Goal:** the best possible trading agent for Mac and iPhone — the whole desk in Max's pocket, with the one button that matters.

Read `AGENTS.md`, then `HANDOFF.md` §2, then this. Do not start here.

---

## 1. What "trading agent" means on this desk — read this twice

It does not mean an app that trades. Nothing in this system ever fires an
order on its own, and this handoff does not change that. The doctrine is
enforced by CI: research never places, Codex never fires without confirm,
Max approves every capital action.

The best possible trading agent under that doctrine is therefore:

> **Every seat's work, stamped, in Max's hand — and one deliberate tap that
> turns a ceiling into a confirmed order sheet. Nothing else.**

Concretely, the native app is three things:

1. **The window.** The book, the stamp, seat reads, Jev's case, the
   assignments, the ledger — live, on Mac and iPhone, never looking fresher
   than it is.
2. **The gate.** The one place Max confirms. A confirm is a **file** the desk
   writes and Codex must read before it formats a sheet. No confirm file, no
   sheet. That is how "Max approves every capital action" becomes code.
3. **The alarm.** Push when something changes that needs him: a ticket
   clears the ladder, a seat goes dark, a stop is near, a window opens.

What it is **not**: an order router, a broker client, a wallet, an auto-trader
in any mode. If a task here seems to need any of those, you have misread the
task. Stop and ask Max.

**Why this is the best possible version and not a compromise.** Every
auto-trader ever built on a research stack fails the same way: a stale read
becomes a position before anyone notices. This desk refuses stale reads at
the engine, refuses unchallenged theses, refuses soft evidence, refuses a
proposer's own model as adversary — and then puts the last decision with the
only party who bears the loss. The native app makes that decision fast, not
automatic. Fast is the win. Automatic is the failure mode.

---

## 2. Architecture

```
┌───────────── Mac (hub, always on) ──────────────┐
│  markets-desk/  (the package, unchanged)         │
│  local models: Qwen3.6-27B, gpt-oss-120b         │   loopback only
│  desk daemon:   runs the cadence, writes files   │
│  desk serve:    read-only JSON over LAN/tailnet  │──┐
│  Mac app:       SwiftUI, reads the same files    │  │
└──────────────────────────────────────────────────┘  │ paired, authenticated
                                                      │ read + confirm only
┌───────────── iPhone ─────────────────────────────┐  │
│  SwiftUI client of `desk serve`                   │◄─┘
│  the window · the gate · the alarm                │
│  Keychain-held pairing token; no keys, no models  │
└───────────────────────────────────────────────────┘
```

**The Mac is the desk.** It runs the package, the local models, the
cadence, and holds every file. The Mac app is a native view over the same
directory the CLI reads — no second data model, no sync.

**The iPhone is a client.** It never runs a model, never holds an API key,
never sees the raw pack (CoS output is local by roster). It talks to one
service, `desk serve`, over a paired connection, and it can do exactly two
things: read, and write a confirm.

**`desk serve`** is a new verb: a read-only JSON surface over the same
loaders the CLI uses (`stamp --json`, reports, assignments, ledger, mode,
preflight), plus **one** write endpoint: `POST /confirm`, which writes a
confirm file after verifying the pairing token and the stamp hash. Bound to
loopback by default; reachable from the phone only over the tailnet or LAN
with pairing. No other mutating route exists, and the boundary test asserts it.

**Push** goes through ntfy or Pushover from the daemon, deduplicated per
condition with a cooldown, so a stuck state notifies once, not every poll.
APNs is not needed and adds an Apple developer dependency for nothing.

---

## 3. The confirm contract

This is the load-bearing piece. Build it first, in the package, before any UI.

```yaml
# confirmations/2026-09-2X-WKND-00N.confirm.yaml
schema_version: 1
ticket_id: WKND-00N
confirmed_at: 2026-09-2XT06:47:12-07:00
confirmed_by: max                 # the only value the contract accepts
device: iphone                    # iphone | mac
stamp_sha256: <hash of the stamp --json entry for this ticket at confirm time>
allowed_pct: 0.40                 # copied from the stamp; must match the hash
verdict: pass                     # must be pass; a confirm on FAIL/PENDING is refused
instrument: {kind: prediction_market, symbol: clarity-act-signed-2026, outcome: "No"}
direction: long
entry: 0.925
stop: null
expires_at: 2026-09-2XT13:30:00-07:00   # a confirm is good for one session
note: ""
```

`desk/confirm.py` refuses: a `verdict` other than `pass`; an `allowed_pct`
that does not match the hashed stamp; a hash that does not match the current
stamp (the book moved — re-stamp, re-confirm); an expired confirm; a
`confirmed_by` other than `max`; a naive timestamp.

**Codex's obligation changes by one line:** it formats a sheet only for a
ticket with a valid, unexpired confirm whose hash matches the stamp it is
reading. `HANDOFF-CODEX.md` §4 gets that line. `tests/test_boundary.py`
gains: no sheet-formatting path may run without a `Confirm` object.

A confirm is not an order. It is Max saying "this ceiling, this instrument,
this session — yes". The sheet still goes to Max as a sheet. `live: true`
is a separate, later, Max-only edit, and even then the sheet is confirmed
per order.

---

## 3b. What is built, as of 2026-09-22

The package side of this handoff exists and is under test:

| Piece | State |
|---|---|
| `desk/confirm.py`, `confirmations/`, `desk confirm` | **Built.** Refuses PENDING/FAIL, non-Max, stale digest, expiry, >24h |
| `desk/sheet.py`, `desk sheet` | **Built.** `format_sheet` requires a `Confirm`; boundary test pins the signature |
| `desk serve` | **Built.** Page + JSON API; exactly one mutating route; token-gated; loopback default |
| The page (`desk/ui.py`) | **Built.** Served HTML, works in Safari on Mac and iPhone; hold-to-confirm; every timestamp shows age |
| `desk daemon`, `CADENCE.yaml` | **Built.** Runs slots, writes preflight/assign/stamp/pack, pushes on the conditions in N2 |
| `desk/notify.py` | **Built.** ntfy or Pushover, deduplicated per condition per cooldown |
| `desk pair`, `install/` | **Built.** Token minting, LaunchAgents for serve and daemon, env template |
| `codex-feed/connectors.json` | **Built.** `validate` asserts seat dependencies |
| Native Mac app (N3) | **Not built.** The served page is the Mac UI until then |
| Native iPhone app (N4) | **Not built.** The served page in Safari is the iPhone UI until then; pairing works as specified |

The served page *is* the window, the gate and the alarm today. The native
apps are an upgrade over the same `serve` API, not a prerequisite for
anything below. N0–N2 are done in the package; N3/N4 become "build native
over `/api/*` and `/confirm`" rather than "design it".

## 4. The plan, in order

Prerequisites: `HANDOFF.md` Phases 0–3 done (landed, data layer proven live,
roster up). Phase 4 there (the HTML dashboard) is **superseded by this
handoff's Mac app** — do not build both. Keep `desk dash` only if you want
a no-Apple fallback; it is not required.

### Phase N0 — The confirm contract, in the package

`desk/confirm.py`, `confirmations/`, `desk confirm` verb (CLI path for the
Mac), boundary test extension, Codex handoff line, tests.

**Done when** a confirm on a PENDING ticket is refused, a confirm with a
stale hash is refused, and `test_boundary` fails if a sheet-formatting
function is reachable without a `Confirm`.

### Phase N1 — `desk serve`

Read-only JSON over the CLI loaders; `POST /confirm` as the single write;
pairing token in the Mac Keychain, presented by the phone; loopback default;
tailnet/LAN opt-in with the token required. No CORS wildcard. No other verb.

**Done when** the boundary test asserts `serve` exposes exactly one mutating
route and it is `/confirm`, and a request without the token gets 401.

### Phase N2 — The daemon and push

`desk daemon`: the cadence from `docs/MIGRATION.md` (06:30, 09:45, 12:30,
13:15 PT weekdays; Monday 08:00; weekend crypto) as a LaunchAgent running
`preflight → fetch → assign → challenge → stamp → pack`, writing files, never
skipping silently — a failed step writes a `no_read` and pushes. Push
conditions, each deduplicated with a cooldown:

| Condition | Push |
|---|---|
| a ticket's verdict becomes `pass` with `allowed_pct > 0` | "WKND-00N cleared — 0.40% ceiling. Confirm?" |
| a required seat has not filed by cadence + 15 min | "Rails dark since 06:30" |
| a source goes `unreachable`/`no_auth` | "CBOE unreachable — Pulse blind" |
| an event window opens or closes | "PMI window open: equity/etf/future flat" |
| a confirmed ticket's stamp hash changes | "WKND-00N re-stamped — confirm void" |
| Jev files `kill` | "WKND-00N killed: <gist>" |

**Done when** a week of daemon runs shows every session in `preflight/` and
every push in a log, and a deliberately broken source produced exactly one
push.

### Phase N3 — Mac app

SwiftUI, reading the desk directory directly (not through `serve` — it is
on the box). Sidebar: Book · Seats · Adversary · Assignments · Ledger ·
Sources · Mode. Each view is the CLI's output, native. The Book view carries
the confirm button, enabled only on `pass` with `allowed_pct > 0`, which
runs `desk confirm` and shows the written file.

Rules: system fonts; every timestamp shows age (green < 1 h, amber < 6 h,
red beyond or absent) so the app can never look live when it is not; no
view that edits `MODE.yaml`; the venue table shows `live` in red if it is
ever true.

**Done when** Max has confirmed a paper ticket from the Mac and Codex
formatted a sheet from that confirm and nothing else.

### Phase N4 — iPhone app

SwiftUI client of `desk serve`. Tabs: Book · Seats · Alerts · Settings.
Pairing: scan a QR from the Mac app carrying the tailnet address and a
one-time code; the token lands in Keychain. The confirm flow is deliberate:
tap the ticket → read the stamp and Jev's counter on one screen → hold to
confirm → Face ID → `POST /confirm`. Four steps on purpose; a market order
should not be a swipe.

Offline: shows the last fetch with its age in red. No cached confirm — a
confirm needs the live stamp hash.

**Done when** Max has confirmed a paper ticket from the iPhone, standing
away from the Mac, and the confirm file's `device: iphone` reached Codex.

### Phase N5 — Two weeks paper, then the gate

Run the full loop with every venue `live: false`: seats file, Jev argues,
Rails stamps, Max confirms from the phone, Codex writes sheets to a folder,
outcomes go to the ledger as if taken. `desk score` after ten. Compare the
sheets to what Max would have done by hand.

Then, and only then, `HANDOFF.md` Phase 7 — Max names a broker. The app
changes by nothing. The sheet goes where `MODE.yaml` says; Max still
confirms each one.

**Done when** the ledger has ten paper outcomes, the confirm→sheet path has
zero manual steps, and Max says the phone is faster than the pack.

---

## 5. Hard rules, enforced

Everything in `AGENTS.md` and `HANDOFF.md` §6, plus:

- The iPhone never holds a model, a key, a broker credential, or the pack.
- `desk serve` has one mutating route. Adding a second fails the build.
- A confirm requires `verdict: pass`, a matching stamp hash, and Max. The
  contract refuses everything else; do not add an override.
- No confirm is cached, batched, scheduled, or auto-renewed. One tap, one
  session, one ticket.
- The app cannot edit `MODE.yaml`. Arming a venue is a text edit on the Mac
  by Max, and the boundary test notices.
- Every timestamp on every screen shows its age. Looking live is the one
  UI bug that loses money.

---

## 6. What decides whether this was right

The ledger, and one number: **time from `pass` to confirm.** If the phone
cuts it from "next time Max opens the pack" to under five minutes, and the
ledger's expectancy on confirmed tickets is not worse than the paper
baseline, the agent is working. If confirms cluster at the open with no
read of Jev's counter, the four-step flow is being swiped through and
needs a fifth.

---

## 7. Your first hour

1. `AGENTS.md`, `HANDOFF.md` §2, this file §1. In that order.
2. Confirm `HANDOFF.md` Phases 0–3 are done. If not, you are on the wrong
   handoff.
3. Build Phase N0 in the package with tests before opening Xcode. The
   contract is the product; the app is a view of it.
4. Update `.motif/STATE.md` when N0 lands.

Every allowance is a ceiling. Every confirm is Max's. Info moves; money
never — until Max says, one tap at a time.
