"""The native apps, guarded from the Python side.

There is no Swift toolchain in CI here, so the rules the phone must keep are
asserted by reading the source: what it may hold, what it may send, and
that its model of the server's JSON is the server's JSON. The fixture the
Swift tests decode is regenerated from the shipped desk by this test, so a
field added to `desk serve` without a matching Swift field fails here
before it fails on a phone.
"""

from __future__ import annotations

import json
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPLE = ROOT / "apps" / "apple"
SOURCES = APPLE / "Sources"
FIXTURE = APPLE / "Tests" / "DeskKitTests" / "Fixtures" / "snapshot.json"
NOW = datetime(2026, 9, 22, 13, 30, tzinfo=timezone.utc)

# Nothing the phone should ever mention, let alone hold.
FORBIDDEN = (
    "api_key", "apiKey", "API_KEY", "OPENAI", "ANTHROPIC", "xai.com", "ollama",
    "private_key", "mnemonic", "seed_phrase", "withdraw", "place_order", "create_order",
    "/pack", "packs/",
)
MUTATING_METHODS = ('"PUT"', '"PATCH"', '"DELETE"')


def _swift_files() -> list[Path]:
    return sorted(SOURCES.rglob("*.swift"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class WhatThePhoneHoldsTests(unittest.TestCase):
    def test_sources_exist(self):
        self.assertGreaterEqual(len(_swift_files()), 12)

    def test_nothing_forbidden_appears_in_the_source(self):
        offenders = []
        for path in _swift_files():
            text = _read(path)
            for needle in FORBIDDEN:
                for i, line in enumerate(text.splitlines(), start=1):
                    if needle in line and not line.strip().startswith("//"):
                        offenders.append(f"{path.relative_to(APPLE)}:{i}: {needle}")
        self.assertEqual(offenders, [])

    def test_the_keychain_holds_only_the_pairing(self):
        """Security-framework calls live in one file and store one item."""
        for path in _swift_files():
            text = _read(path)
            if path.name != "Pairing.swift":
                self.assertNotIn("SecItem", text, f"{path.name} touches the Keychain")
        pairing = _read(SOURCES / "DeskKit" / "Pairing.swift")
        self.assertEqual(pairing.count("kSecAttrAccount as String: account"), 3)
        self.assertIn('static let account = "pairing"', pairing)


class WhatThePhoneSendsTests(unittest.TestCase):
    def test_exactly_one_post_in_the_package(self):
        posts = []
        for path in _swift_files():
            for i, line in enumerate(_read(path).splitlines(), start=1):
                if 'httpMethod = "POST"' in line:
                    posts.append(f"{path.relative_to(APPLE)}:{i}")
        self.assertEqual(posts, ["Sources/DeskKit/DeskAPI.swift:%d" % _line_of(SOURCES / "DeskKit" / "DeskAPI.swift", 'httpMethod = "POST"')])

    def test_no_other_mutating_verb(self):
        for path in _swift_files():
            text = _read(path)
            for verb in MUTATING_METHODS:
                self.assertNotIn(f"httpMethod = {verb}", text, f"{path.name} uses {verb}")

    def test_the_post_targets_the_confirm_route(self):
        api = _read(SOURCES / "DeskKit" / "DeskAPI.swift")
        self.assertIn('appending(path: "/confirm")', api)
        self.assertEqual(api.count("httpBody ="), 1)

    def test_network_calls_live_in_the_client_only(self):
        for path in _swift_files():
            if path.name == "DeskAPI.swift":
                continue
            self.assertNotIn("URLSession", _read(path), f"{path.name} makes its own requests")
            self.assertNotIn("URLRequest", _read(path), f"{path.name} builds its own requests")

    def test_the_confirm_control_gates_on_pass_with_a_ceiling(self):
        models = _read(SOURCES / "DeskKit" / "Models.swift")
        self.assertIn('verdict == "pass" && allowedPct > 0', models)
        book = _read(SOURCES / "DeskUI" / "BookView.swift")
        self.assertIn(".disabled(!stamp.confirmable)", book)

    def test_the_confirm_flow_requires_biometrics_and_a_hold(self):
        sheet = _read(SOURCES / "DeskUI" / "ConfirmSheet.swift")
        self.assertIn("evaluatePolicy(.deviceOwnerAuthentication", sheet)
        self.assertIn("duration: Double = 1.5", sheet)
        self.assertIn("guard await biometric() else", sheet)

    def test_the_confirm_sends_the_digest_on_screen(self):
        store = _read(SOURCES / "DeskKit" / "Store.swift")
        self.assertIn("stampSha256: stamp.stampSha256", store)


class WhatThePhoneShowsTests(unittest.TestCase):
    def test_every_date_goes_through_agelabel(self):
        """A date rendered any other way can look live when it is not.

        Two exemptions, both deliberate: AgeLabel's own tooltip shows the
        absolute instant behind the age, and event windows show start/end
        because they are future instants, not freshness claims."""
        offenders = []
        for path in (SOURCES / "DeskUI").rglob("*.swift"):
            for i, line in enumerate(_read(path).splitlines(), start=1):
                if ".formatted(" not in line:
                    continue
                if ".help(" in line or "startsAt" in line or "endsAt" in line:
                    continue
                offenders.append(f"{path.name}:{i}")
        self.assertEqual(offenders, [])

    def test_the_live_banner_is_red(self):
        shared = _read(SOURCES / "DeskUI" / "Shared.swift")
        self.assertIn(".background(DeskColor.fail", shared)

    def test_no_view_can_edit_policy(self):
        for path in (SOURCES / "DeskUI").rglob("*.swift"):
            text = _read(path)
            self.assertNotIn("MODE.yaml\"", text)
            self.assertNotIn("live = true", text)


class FixtureTests(unittest.TestCase):
    def test_the_fixture_is_the_shipped_snapshot(self):
        """Regenerate from the desk; the committed fixture must match so the
        Swift model cannot drift from the server without failing here."""
        from desk.serve import snapshot

        fresh = snapshot(ROOT, now=NOW)
        stored = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(sorted(stored), sorted(fresh))
        self.assertEqual(stored["stamp"]["stamps"], fresh["stamp"]["stamps"])
        self.assertEqual(stored["mode"], fresh["mode"])

    def test_every_snapshot_key_has_a_swift_coding_key(self):
        models = _read(SOURCES / "DeskKit" / "Models.swift")
        stored = json.loads(FIXTURE.read_text(encoding="utf-8"))

        def declared(key: str) -> bool:
            # Either a quoted raw value ("generated_at") or a bare case (mode).
            return f'"{key}"' in models or re.search(rf"\bcase\b[^\n]*\b{re.escape(key)}\b", models) is not None

        for key in stored:
            self.assertTrue(declared(key), f"snapshot key {key!r} has no Swift coding key")
        for key in stored["stamp"]["stamps"][0]:
            self.assertTrue(declared(key), f"stamp key {key!r} missing in Swift")


def _line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(_read(path).splitlines(), start=1):
        if needle in line:
            return i
    raise AssertionError(f"{needle!r} not in {path}")


if __name__ == "__main__":
    unittest.main()
