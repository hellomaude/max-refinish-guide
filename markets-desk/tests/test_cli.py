"""CLI smoke tests: the verbs a seat types, exercised end to end."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from desk import cli
from desk.adapters import hyperliquid
from tests.test_adapters import HL_PAYLOAD


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def test_validate_accepts_the_shipped_book(self):
        code, out, _ = _run(["validate"])
        self.assertEqual(code, 0)
        self.assertIn("mode      ok", out)

    def test_stamp_renders_a_table(self):
        code, out, _ = _run(["stamp", "--now", "2026-09-21T06:30:00-07:00"])
        self.assertEqual(code, 0)
        self.assertIn("| ticket | verdict |", out)
        self.assertIn("WKND-002", out)

    def test_stamp_json_is_machine_readable(self):
        import json

        code, out, _ = _run(["stamp", "--now", "2026-09-21T06:30:00-07:00", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["execution"], "research_packs_only")
        self.assertTrue(payload["stamps"])

    def test_stamp_refuses_a_naive_now(self):
        with self.assertRaises(SystemExit):
            _run(["stamp", "--now", "2026-09-21T06:30:00"])

    def test_pack_includes_the_evidence_table(self):
        code, out, _ = _run(["pack", "--now", "2026-09-21T06:30:00-07:00"])
        self.assertEqual(code, 0)
        self.assertIn("## Tickets", out)
        self.assertIn("| evidence | value | source | as of |", out)

    def test_score_is_quiet_with_an_empty_ledger(self):
        code, out, _ = _run(["score", "--outcomes", "does-not-exist"])
        self.assertEqual(code, 0)
        self.assertIn("nothing to score yet", out)

    def test_fetch_prints_paste_ready_evidence(self):
        with mock.patch.object(hyperliquid, "fetch_json", return_value=HL_PAYLOAD):
            code, out, _ = _run(["fetch", "Chain", "--coin", "BTC"])
        self.assertEqual(code, 0)
        self.assertIn("evidence:", out)
        self.assertIn("key: BTC_funding_apr", out)
        self.assertIn("kind: funding_oi", out)
        self.assertIn("# BTC: funding calm", out)

    def test_fetch_reports_a_dark_source_on_stderr_and_exits_nonzero(self):
        from desk.adapters.base import FetchError

        with mock.patch.object(hyperliquid, "fetch_json", side_effect=FetchError("403")):
            code, out, err = _run(["fetch", "Chain", "--coin", "BTC"])
        self.assertEqual(code, 1)
        self.assertNotIn("evidence:", out)
        self.assertIn("403", err)

    def test_fetch_requires_the_arguments_a_seat_needs(self):
        with self.assertRaises(SystemExit):
            _run(["fetch", "Odds"])
        with self.assertRaises(SystemExit):
            _run(["fetch", "Wire"])


if __name__ == "__main__":
    unittest.main()
