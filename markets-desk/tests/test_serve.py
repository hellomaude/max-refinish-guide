"""`desk serve`: read everything, write one thing, and only with the token."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from desk.confirm import load_confirms
from desk.loader import DeskError
from desk.serve import make_server, new_token, snapshot, start_in_thread
from desk.ui import render

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 9, 22, 13, 30, tzinfo=timezone.utc)


def _copy_desk(tmp: str) -> Path:
    root = Path(tmp) / "desk"
    shutil.copytree(ROOT / "codex-feed", root / "codex-feed")
    shutil.copytree(ROOT / "tickets", root / "tickets")
    shutil.copytree(ROOT / "challenges", root / "challenges")
    (root / "reports").mkdir()
    return root


def _passing_desk(root: Path) -> None:
    """Make one ticket PASS so there is something to confirm: no required
    seats, no challenge requirement, equity enabled, one confident ticket."""
    mode = (root / "codex-feed" / "MODE.yaml").read_text(encoding="utf-8")
    mode = mode.replace("required_seats: [Rails]", "required_seats: []")
    mode = mode.replace("require_challenge: true", "require_challenge: false")
    (root / "codex-feed" / "MODE.yaml").write_text(mode, encoding="utf-8")
    for p in (root / "tickets").glob("*.ticket.yaml"):
        p.unlink()
    (root / "tickets" / "2026-09-22-T-PASS-btc.ticket.yaml").write_text(
        """schema_version: 2
id: T-PASS
created_at: 2026-09-22T06:00:00-07:00
source_seats: [Chain]
instrument: {kind: crypto_spot, symbol: BTC, venue: crypto_spot}
direction: long
theme: crypto_policy_beta
thesis: A thesis long enough to clear the minimum length the contract enforces today.
catalyst: Monday cash open tape
invalidation: Loses the reclaim level on a closing basis.
horizon: intraday
size_hint_pct: 1.0
confidence: 5
evidence:
  - {key: spot, kind: price, value: 81300, source: Kraken, as_of: 2026-09-22T06:00:00-07:00}
sources: [https://example.invalid/note]
rails_check: pass
max_gate: true
entry: 100.0
stop: 95.0
""",
        encoding="utf-8",
    )


class _Server:
    def __init__(self, root: Path, token: str | None):
        self.server = make_server(root, port=0, token=token, clock=lambda: NOW)
        start_in_thread(self.server)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def get(self, path: str, headers: dict | None = None):
        req = urllib.request.Request(self.base + path, headers=headers or {})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8"), r.headers

    def post(self, path: str, body: dict, headers: dict | None = None):
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data, method="POST",
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8") or "{}")

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class SnapshotTests(unittest.TestCase):
    def test_snapshot_renders_from_the_shipped_desk(self):
        data = snapshot(ROOT, now=NOW)
        self.assertEqual(data["mode"]["execution"], "research_packs_only")
        self.assertTrue(data["stamp"]["stamps"])
        for s in data["stamp"]["stamps"]:
            self.assertEqual(len(s["stamp_sha256"]), 64)
        html = render(data, now=NOW)
        self.assertIn("Markets Desk", html)
        self.assertIn("ago", html)
        self.assertNotIn("LIVE:", html, "no venue is live")

    def test_render_survives_an_empty_desk(self):
        html = render({"generated_at": NOW.isoformat()}, now=NOW)
        self.assertIn("none yet", html)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = _copy_desk(self.tmp)
        _passing_desk(self.root)
        self.token = new_token(self.root)
        self.srv = _Server(self.root, self.token)

    def tearDown(self):
        self.srv.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_page_and_the_api_read(self):
        status, body, headers = self.srv.get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn("hold to confirm", body)
        status, body, _ = self.srv.get("/api/stamp")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["stamps"][0]["verdict"], "pass")
        status, body, _ = self.srv.get("/api/health")
        self.assertTrue(json.loads(body)["paired"])

    def test_confirm_needs_the_token(self):
        status, payload = self.srv.post("/confirm", {"ticket_id": "T-PASS", "device": "iphone"})
        self.assertEqual(status, 401)
        status, payload = self.srv.post("/confirm", {"ticket_id": "T-PASS", "device": "iphone"},
                                        headers={"Authorization": "Bearer wrong"})
        self.assertEqual(status, 401)
        self.assertEqual(load_confirms(self.root / "confirmations"), {})

    def test_confirm_writes_a_file_with_the_device(self):
        digest = json.loads(self.srv.get("/api/stamp")[1])["stamps"][0]["stamp_sha256"]
        status, payload = self.srv.post(
            "/confirm", {"ticket_id": "T-PASS", "device": "iphone", "stamp_sha256": digest},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(status, 201, payload)
        found = load_confirms(self.root / "confirmations")
        self.assertEqual(found["T-PASS"].device, "iphone")
        self.assertEqual(found["T-PASS"].stamp_sha256, digest)
        # The page now shows it as confirmed rather than offering the button.
        self.assertIn("confirmed · iphone", self.srv.get("/")[1])

    def test_confirm_on_a_stale_digest_is_refused(self):
        """A confirm on a stamp you did not see is not a confirm."""
        status, payload = self.srv.post(
            "/confirm", {"ticket_id": "T-PASS", "device": "iphone", "stamp_sha256": "0" * 64},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(status, 409)
        self.assertIn("book moved", payload["error"])
        self.assertEqual(load_confirms(self.root / "confirmations"), {})

    def test_confirm_on_an_unknown_ticket_is_404(self):
        status, _ = self.srv.post("/confirm", {"ticket_id": "NOPE"},
                                  headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(status, 404)

    def test_every_other_post_is_404(self):
        for path in ("/api/stamp", "/mode", "/tickets", "/confirmations"):
            status, _ = self.srv.post(path, {}, headers={"Authorization": f"Bearer {self.token}"})
            self.assertEqual(status, 404, path)

    def test_no_cors_wildcard(self):
        _, _, headers = self.srv.get("/api/stamp")
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))


class BindTests(unittest.TestCase):
    def test_a_non_loopback_bind_needs_a_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_desk(tmp)
            with self.assertRaises(DeskError):
                make_server(root, bind="0.0.0.0", port=0, token=None)


if __name__ == "__main__":
    unittest.main()
