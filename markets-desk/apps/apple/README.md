# Markets Desk — Mac and iPhone

Native clients of `desk serve`. Two apps, one package, one data model that
mirrors the server's JSON exactly. They are the window, the gate and the
alarm from `../../HANDOFF-NATIVE.md`; the daemon's push reaches the phone
through ntfy/Pushover regardless of whether the app is open.

## What the phone holds

The pairing — a base URL and a token — in the Keychain, and nothing else. No
model, no API key, no broker credential, no pack. `../../tests/test_apple.py`
reads this source tree and fails the desk's build if any of that appears.

## What the phone can do

Read the snapshot. Write one confirm. The confirm flow is four steps on
purpose: open the ticket, read the stamp and Jev's case on one screen, hold
for 1.5 s, pass Face ID. Then the digest of what was on screen goes to
`POST /confirm`; the server refuses if the book has moved since.

## Build

```bash
brew install xcodegen
cd markets-desk/apps/apple
xcodegen generate            # → Desk.xcodeproj
open Desk.xcodeproj          # pick DeskMac or DeskPhone, ⌘R
swift test                   # DeskKit tests, no simulator needed
```

Signing: your own team, your own devices. Nothing is distributed.

## Pair

On the Mac: `python -m desk pair --host <tailnet address>` prints a one-time
URL. Open it on the phone (paste into Mode → Pairing, or tap it from
Messages — the app registers for the URL). The Mac app pairs itself to
loopback if it can read `state/pair.token` under `$DESK_ROOT` or
`~/desk/markets-desk`.

## Rules the source keeps

- Every timestamp shows its age. `AgeLabel` is the only way a date is shown.
- One `httpMethod = "POST"` in the package, in `DeskAPI.confirm`.
- The confirm control is enabled only on `verdict == pass && allowed_pct > 0`.
- The LIVE banner is red and cannot be styled ordinary.
- No view edits policy. There is no request that could.
