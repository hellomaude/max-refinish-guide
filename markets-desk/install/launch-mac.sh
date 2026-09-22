#!/usr/bin/env bash
# One command from a fresh Mac to a running desk with the Mac app open.
#
#   curl -fsSL https://raw.githubusercontent.com/hellomaude/max-refinish-guide/main/markets-desk/install/launch-mac.sh | bash
#
# or, from a clone:  bash markets-desk/install/launch-mac.sh
#
# Idempotent. Re-run it after a `git pull`. It never edits MODE.yaml; every
# venue stays live:false and nothing here can place an order.
set -euo pipefail

DESK_HOME="${DESK_HOME:-$HOME/desk}"
REPO="https://github.com/hellomaude/max-refinish-guide.git"
say() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }
die() { printf '\n\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(uname)" = "Darwin" ] || die "this launcher is for macOS"
command -v git >/dev/null || die "git missing — install Xcode Command Line Tools: xcode-select --install"
command -v python3 >/dev/null || die "python3 missing"

# ---- 1. code ---------------------------------------------------------------
say "code → $DESK_HOME"
if [ -d "$DESK_HOME/.git" ]; then
  git -C "$DESK_HOME" pull --ff-only
else
  mkdir -p "$(dirname "$DESK_HOME")"
  git clone "$REPO" "$DESK_HOME"
fi
ROOT="$DESK_HOME/markets-desk"
cd "$ROOT"

# ---- 2. python -------------------------------------------------------------
say "python venv + PyYAML"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip -q install --upgrade pip pyyaml >/dev/null
say "tests (this is the gate; if it is red, stop here)"
.venv/bin/python -m unittest discover -s tests -t . -q 2>&1 | tail -3
.venv/bin/python -m desk validate >/dev/null && echo "validate: ok"

# ---- 3. env ----------------------------------------------------------------
mkdir -p state
if [ ! -f state/env ]; then
  cp install/env.example state/env
  say "wrote state/env from the template — fill in keys later; nothing below needs them"
fi

# ---- 4. pairing token ------------------------------------------------------
say "pairing token"
if [ ! -s state/pair.token ]; then
  .venv/bin/python -m desk pair --host 127.0.0.1 >/dev/null
fi
echo "token at state/pair.token (the Mac app reads it; the phone gets it from \`desk pair --host <tailnet-ip> --qr\`)"

# ---- 5. serve + daemon as LaunchAgents --------------------------------------
say "LaunchAgents: serve + daemon"
bash install/install-macos.sh

# ---- 6. the page -----------------------------------------------------------
say "opening the served page"
open "http://127.0.0.1:8791/" || true

# ---- 7. the native Mac app ---------------------------------------------------
say "native Mac app"
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Xcode not found; the served page is the UI until it is. Done."
  exit 0
fi
if ! command -v xcodegen >/dev/null; then
  if command -v brew >/dev/null; then brew install xcodegen; else
    echo "xcodegen missing and no Homebrew — install from https://brew.sh then re-run. The served page is up meanwhile."; exit 0; fi
fi
cd apps/apple
xcodegen generate >/dev/null
say "swift test (DeskKit)"
if ! swift test 2>&1 | tail -5; then
  echo "DeskKit tests failed — open Desk.xcodeproj and read the first error. The served page is still up."; exit 1
fi
say "building DeskMac"
BUILD_DIR="$ROOT/state/build"
if xcodebuild -project Desk.xcodeproj -scheme DeskMac -configuration Debug \
     -derivedDataPath "$BUILD_DIR" CODE_SIGN_IDENTITY="-" CODE_SIGNING_ALLOWED=NO build 2>&1 | tail -3; then
  APP="$(find "$BUILD_DIR/Build/Products/Debug" -maxdepth 1 -name 'DeskMac.app' | head -1)"
  [ -n "$APP" ] || die "built, but DeskMac.app not found under $BUILD_DIR"
  say "launching $APP"
  DESK_ROOT="$ROOT" open "$APP"
  echo
  echo "Mac app is up. It pairs itself to loopback from state/pair.token."
  echo "For the phone: .venv/bin/python -m desk pair --host <tailnet-ip> --qr, then open Desk.xcodeproj → DeskPhone → run on device."
else
  echo "xcodebuild failed — open Desk.xcodeproj in Xcode and read the first error; a first compile"
  echo "usually needs a type fix or two. The served page at http://127.0.0.1:8791 is up regardless."
  exit 1
fi
