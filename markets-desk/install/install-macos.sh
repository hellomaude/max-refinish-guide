#!/usr/bin/env bash
# Install the desk's two LaunchAgents: serve (the UI + API) and daemon (the cadence).
# Idempotent. Run from markets-desk/. Nothing here touches MODE.yaml.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS" "$ROOT/state"
[ -f "$ROOT/state/env" ] || { echo "state/env missing — cp install/env.example state/env and fill it in"; exit 1; }
[ -x "$ROOT/.venv/bin/python" ] || { echo ".venv missing — see install/README.md §1"; exit 1; }
for name in serve daemon; do
  src="$ROOT/install/com.maxmotif.desk.$name.plist"
  dst="$AGENTS/com.maxmotif.desk.$name.plist"
  sed "s#__DESK_ROOT__#$ROOT#g" "$src" > "$dst"
  launchctl unload -w "$dst" 2>/dev/null || true
  launchctl load -w "$dst"
  echo "loaded com.maxmotif.desk.$name"
done
for i in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:8791/api/health" >/dev/null 2>&1; then echo "serve is up: http://127.0.0.1:8791"; exit 0; fi
  sleep 1
done
echo "serve did not answer /api/health in 20s — check state/serve.err.log"; exit 1
