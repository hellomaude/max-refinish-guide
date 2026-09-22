# Installing the desk on the Mac

Everything runs on one always-on Mac. Nothing here is deployed anywhere else.

## 1. Land it

```bash
cd ~/desk && git clone https://github.com/hellomaude/max-refinish-guide.git .
cd markets-desk
python3 -m venv .venv && . .venv/bin/activate && pip install pyyaml
python -m unittest discover -s tests -t . -q     # must be green
python -m desk validate
```

## 2. Environment

```bash
cp install/env.example state/env       # then edit; state/ is gitignored
```

`state/env` holds keys only. It is read by the LaunchAgents below and by
your shell when you `source` it. It is never committed; `desk validate`
refuses a repo with a credential literal in it.

## 3. Pair a phone

```bash
python -m desk pair
```

Prints a one-time URL carrying the token. Open it once in Safari on the
iPhone (over the tailnet or LAN); the page stores the token and drops it
from the URL. From then on the confirm button works from that phone and
nowhere else. Re-run `pair` to rotate; the old token stops working.

## 4. Run it

By hand:

```bash
python -m desk serve                    # http://127.0.0.1:8791
python -m desk daemon                   # runs codex-feed/CADENCE.yaml
```

As LaunchAgents that start at login and restart if they exit:

```bash
bash install/install-macos.sh
```

Then keep the Mac awake — screen sleep is fine, system sleep stops both:

```bash
sudo pmset -a sleep 0 disksleep 0 autorestart 1
```

## 5. Reach it from the phone

`serve` binds `127.0.0.1` by default and refuses any other bind without a
token. To reach it from the phone:

- **Tailnet (recommended):** `python -m desk serve --bind 100.x.y.z` with the
  Mac's tailnet address. Only your devices can reach it.
- **LAN:** `--bind 0.0.0.0` on a network you control. Everyone on that
  network can see the book; only the paired phone can confirm.

Never expose it to the internet. There is no login page, only the token.

## 6. Push

Set `NTFY_TOPIC` (and optionally `NTFY_TOKEN`) in `state/env`, or
`PUSHOVER_TOKEN` + `PUSHOVER_USER`. The daemon pushes on: a ticket clearing
the ladder, a required seat dark past grace, a source unreachable, a
confirm voided by a re-stamp, a kill by Jev, a step failing. Once per
condition per cooldown (4h by default in `CADENCE.yaml`).

Test it without sending: `python -m desk daemon --once morning --dry-run-push`.

## 7. Local models

Serve Qwen3.6-27B and gpt-oss-120b on loopback with Ollama or vLLM. The desk
does not call them; the seats do, and a seat writes a file. `desk validate`
prints which seats the roster puts on the box. If a local model is down, the
seat files `no_read` — it does not fall back to a hosted vendor.

## What is not here

No broker. No exchange client. No wallet. `MODE.yaml` keeps every venue
`live: false`. When Max arms one, the install does not change; the sheet
Codex formats goes where `MODE.yaml` says, still one confirm at a time.
