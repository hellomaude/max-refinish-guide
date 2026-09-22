"""`desk serve`: the desk over HTTP, read-only but for one route.

This is what the iPhone talks to, and what the Mac's browser renders. Every
GET is a view over the same loaders the CLI uses — there is no second data
model. There is exactly one write, `POST /confirm`, and it does what the
CLI's `desk confirm` does: build a confirm against the current book, refuse
if it does not pass, write the file. Nothing else on this server mutates
anything, and `tests/test_boundary.py` counts the routes.

Bound to loopback by default. Reaching it from a phone means either a
tailnet address or the LAN, and either way the pairing token is required
for the confirm route. The token never travels in a URL after pairing; the
page stores it and sends it as a bearer header.

No CORS wildcard: the page is served from the same origin it calls.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from .assign import audit, load_assignments
from .challenge import load_challenges
from .confirm import load_confirms, make_confirm, usable, write_confirm
from .connectors import latest_health
from .daemon import Paths, _book_payload
from .ledger import calibration_report, challenge_report, load_outcomes, score
from .loader import DeskError, ValidationError
from .mode import load_mode
from .report import load_reports, seats_reporting
from .risk import stamp_book
from .roster import load_roster
from .ticket import load_tickets
from .ui import render

# The complete set of routes that change anything. One entry, by design.
MUTATING_ROUTES = ("/confirm",)

DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 8791
TOKEN_ENV = "DESK_TOKEN"


def token_path(root: Path) -> Path:
    return root / "state" / "pair.token"


def load_token(root: Path) -> str | None:
    """The pairing token: env first, then the state file."""
    env = os.environ.get(TOKEN_ENV)
    if env:
        return env.strip()
    path = token_path(root)
    if path.exists():
        return path.read_text(encoding="utf-8").strip() or None
    return None


def new_token(root: Path) -> str:
    """Mint a pairing token and store it. Called by `desk pair`."""
    token = secrets.token_urlsafe(32)
    path = token_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - platform dependent
        pass
    return token


def snapshot(root: Path, *, now: datetime) -> dict[str, Any]:
    """Everything the page and the API serve, from the loaders."""
    paths = Paths(root)
    mode = load_mode(paths.mode)
    tickets = load_tickets(paths.tickets) if paths.tickets.exists() else []
    reports = load_reports(paths.reports)
    challenges = load_challenges(paths.challenges)
    if paths.roster.exists():
        roster = load_roster(paths.roster)
        challenges, _ = roster.independent_challenges(tickets, challenges)
    else:
        roster = None
    book = stamp_book(tickets, mode, now=now, challenges=challenges,
                      available_seats=seats_reporting(reports) or None)
    payload = _book_payload(book)

    confirms = load_confirms(paths.confirmations)
    good, _ = usable(confirms, book, now=now)
    confirms_out = {
        tid: {
            "confirmed_at": c.confirmed_at.isoformat(),
            "device": c.device,
            "expires_at": c.expires_at.isoformat(),
            "allowed_pct": c.allowed_pct,
            "usable": tid in good,
        }
        for tid, c in confirms.items()
    }

    assignments_out: dict[str, Any] = {}
    for seat, a in load_assignments(paths.assignments).items():
        cov = audit(a, reports.get(seat), now=now)
        assignments_out[seat] = {
            "issued_at": a.issued_at.isoformat(),
            "at_stake_pct": a.at_stake_pct,
            "tasks": [t.task_id for t in a.tasks],
            "coverage": {
                "assigned": cov.assigned,
                "answered": list(cov.answered),
                "unanswered": list(cov.unanswered),
                "stale": list(cov.stale),
                "unsolicited": list(cov.unsolicited),
            },
        }

    ledger_out: dict[str, Any] = {}
    outcomes = load_outcomes(root / "ledger", tickets) if (root / "ledger").exists() else []
    if outcomes:
        seat_to_model = {s: a.model for s, a in roster.seats.items()} if roster else None
        dims = ("seat", "theme", "confidence") + (("model",) if seat_to_model else ())
        ledger_out["tables"] = {
            d: [e.row() for e in score(outcomes, dimension=d, seat_to_model=seat_to_model)]
            for d in dims
        }
        ledger_out["lines"] = calibration_report(outcomes) + challenge_report(outcomes, challenges)

    sources_out: dict[str, Any] = {}
    if paths.preflight.exists():
        found = sorted(paths.preflight.glob("*.json"))
        if found:
            try:
                sources_out = json.loads(found[-1].read_text(encoding="utf-8"))
            except (ValueError, OSError):
                sources_out = {}

    return {
        "generated_at": now.isoformat(),
        "mode": {
            "mode": mode.mode,
            "execution": mode.execution,
            "updated_at": mode.updated_at.isoformat(),
            "required_seats": list(mode.required_seats),
            "require_challenge": mode.require_challenge,
            "venues": {
                v.id: {"enabled": v.enabled, "live": v.live, "note": v.note}
                for v in mode.venues.values()
            },
        },
        "stamp": payload,
        "reports": {
            seat: {
                "read": r.read,
                "headline": r.headline,
                "produced_at": r.produced_at.isoformat(),
                "covers": list(r.covers),
                "crowding": dict(r.crowding),
                "unavailable": list(r.unavailable),
            }
            for seat, r in reports.items()
        },
        "assignments": assignments_out,
        "confirmations": confirms_out,
        "ledger": ledger_out,
        "sources": sources_out,
        "event_windows": [
            {
                "id": w.id,
                "starts_at": w.starts_at.isoformat(),
                "ends_at": w.ends_at.isoformat(),
                "applies_to_kinds": list(w.applies_to_kinds),
            }
            for w in mode.event_windows
        ],
        "health": {"dark_seats": _dark_seats(root)},
    }


def _dark_seats(root: Path) -> list[str]:
    from .connectors import load_manifest

    manifest_path = root / "codex-feed" / "connectors.json"
    if not manifest_path.exists():
        return []
    try:
        return load_manifest(manifest_path).dark_seats(latest_health(root / "preflight"))
    except (DeskError, ValueError, OSError):
        return []


def confirm_from_request(
    root: Path, body: Mapping[str, Any], *, now: datetime
) -> tuple[int, dict[str, Any]]:
    """The one write. Returns (status, json)."""
    ticket_id = str(body.get("ticket_id", "")).strip()
    device = str(body.get("device", "")).strip() or "iphone"
    presented = str(body.get("stamp_sha256", "")).strip().lower()
    if not ticket_id:
        return 400, {"error": "ticket_id required"}
    paths = Paths(root)
    mode = load_mode(paths.mode)
    tickets = load_tickets(paths.tickets)
    reports = load_reports(paths.reports)
    challenges = load_challenges(paths.challenges)
    if paths.roster.exists():
        challenges, _ = load_roster(paths.roster).independent_challenges(tickets, challenges)
    book = stamp_book(tickets, mode, now=now, challenges=challenges,
                      available_seats=seats_reporting(reports) or None)
    ticket = next((t for t in tickets if t.id == ticket_id), None)
    stamp = book.by_id(ticket_id)
    if ticket is None or stamp is None:
        return 404, {"error": f"{ticket_id}: not in the book"}
    try:
        confirm = make_confirm(ticket, stamp, book, now=now, device=device,
                               note=str(body.get("note", ""))[:200])
    except ValidationError as exc:
        return 409, {"error": str(exc)}
    # The page confirmed what it was looking at. If the book has moved since
    # the page loaded, the digests differ and the tap is refused — a confirm
    # on a stamp you did not see is not a confirm.
    if presented and not hmac.compare_digest(presented, confirm.stamp_sha256):
        return 409, {"error": f"{ticket_id}: the book moved since the page loaded — reload and re-read"}
    path = write_confirm(confirm, paths.confirmations)
    return 201, {
        "written": path.name,
        "ticket_id": ticket_id,
        "allowed_pct": confirm.allowed_pct,
        "expires_at": confirm.expires_at.isoformat(),
        "device": device,
    }


class _Handler(BaseHTTPRequestHandler):
    root: Path = Path(".")
    token: str | None = None
    clock: Callable[[], datetime] = staticmethod(lambda: datetime.now(timezone.utc))
    server_version = "desk/1"

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet
        return

    def _send(self, status: int, payload: Any, *, content_type: str = "application/json") -> None:
        body = payload.encode("utf-8") if isinstance(payload, str) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not self.token:
            return False
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        return hmac.compare_digest(header[7:].strip(), self.token)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        now = self.clock()
        try:
            if path in ("/", "/index.html"):
                data = snapshot(self.root, now=now)
                device = "iphone" if "iPhone" in self.headers.get("User-Agent", "") else "mac"
                self._send(200, render(data, now=now, device=device), content_type="text/html")
                return
            if path == "/api/health":
                self._send(200, {"ok": True, "now": now.isoformat(), "paired": bool(self.token)})
                return
            if path == "/api/snapshot":
                self._send(200, snapshot(self.root, now=now))
                return
            if path.startswith("/api/"):
                key = path[len("/api/"):]
                data = snapshot(self.root, now=now)
                if key in data:
                    self._send(200, data[key])
                    return
            self._send(404, {"error": "not found"})
        except (DeskError, OSError, ValueError) as exc:
            self._send(500, {"error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in MUTATING_ROUTES:
            self._send(404, {"error": "not found"})
            return
        if not self._authorized():
            self._send(401, {"error": "pairing token required"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > 4096:
            self._send(413, {"error": "too large"})
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            self._send(400, {"error": "body must be JSON"})
            return
        try:
            status, payload = confirm_from_request(self.root, body, now=self.clock())
        except (DeskError, OSError) as exc:
            status, payload = 500, {"error": str(exc)}
        self._send(status, payload)


def make_server(
    root: Path,
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    token: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ThreadingHTTPServer:
    if bind != DEFAULT_BIND and not token:
        raise DeskError(
            f"refusing to bind {bind}: a non-loopback bind needs a pairing token "
            "(run `desk pair` first)"
        )
    handler = type("DeskHandler", (_Handler,), {
        "root": root,
        "token": token,
        "clock": staticmethod(clock or (lambda: datetime.now(timezone.utc))),
    })
    return ThreadingHTTPServer((bind, port), handler)


def serve_forever(server: ThreadingHTTPServer) -> None:  # pragma: no cover - blocking
    try:
        server.serve_forever()
    finally:
        server.server_close()


def start_in_thread(server: ThreadingHTTPServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread
