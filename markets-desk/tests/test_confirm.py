"""The confirm: Max's yes, as a file Codex must read.

The failure this prevents is the quiet one: a sheet formatted against a
book that moved after Max said yes. So the tests are mostly about what a
confirm refuses.
"""

from __future__ import annotations

import unittest
from datetime import timedelta
from typing import Any

from desk.confirm import (
    CONFIRMER,
    DEFAULT_TTL,
    load_confirms,
    make_confirm,
    parse_confirm,
    render_confirm,
    stamp_digest,
    usable,
    write_confirm,
)
from desk.loader import ValidationError
from desk.risk import stamp_book
from desk.sheet import format_sheet, write_sheet
from tests.helpers import NOW, build_mode, build_ticket

# The Chain fixture in helpers.py passes at confidence 5 with a fresh price.
CHALLENGED = {}


def passing_book(**ticket_overrides: Any):
    mode = build_mode(required_seats=[], require_challenge=False)
    ticket = build_ticket(**ticket_overrides)
    book = stamp_book([ticket], mode, now=NOW)
    stamp = book.by_id(ticket.id)
    assert stamp is not None and stamp.verdict == "pass" and stamp.allowed_pct > 0, stamp
    return mode, ticket, book, stamp


class MakeTests(unittest.TestCase):
    def test_a_pass_with_a_ceiling_can_be_confirmed(self):
        mode, ticket, book, stamp = passing_book()
        confirm = make_confirm(ticket, stamp, book, now=NOW, device="iphone")
        self.assertEqual(confirm.confirmed_by, CONFIRMER)
        self.assertEqual(confirm.stamp_sha256, stamp_digest(stamp, book))
        self.assertEqual(confirm.expires_at, NOW + DEFAULT_TTL)
        self.assertTrue(confirm.matches(stamp, book))

    def test_a_pending_ticket_cannot_be_confirmed(self):
        """Confirming a PENDING is confirming nothing."""
        mode = build_mode(required_seats=[], require_challenge=True)
        ticket = build_ticket()
        book = stamp_book([ticket], mode, now=NOW)
        stamp = book.by_id(ticket.id)
        self.assertEqual(stamp.verdict, "pending")
        with self.assertRaises(ValidationError) as caught:
            make_confirm(ticket, stamp, book, now=NOW, device="mac")
        self.assertIn("nothing to confirm", str(caught.exception))

    def test_a_stamp_for_another_ticket_is_refused(self):
        mode, ticket, book, stamp = passing_book()
        other = build_ticket(id="T-OTHER")
        with self.assertRaises(ValidationError):
            make_confirm(other, stamp, book, now=NOW, device="mac")

    def test_an_unknown_device_is_refused(self):
        mode, ticket, book, stamp = passing_book()
        with self.assertRaises(ValidationError):
            make_confirm(ticket, stamp, book, now=NOW, device="watch")


class ContractTests(unittest.TestCase):
    def _doc(self, **overrides: Any) -> dict[str, Any]:
        mode, ticket, book, stamp = passing_book()
        doc = dict(make_confirm(ticket, stamp, book, now=NOW, device="cli").raw)
        doc.update(overrides)
        return doc

    def test_only_max_confirms(self):
        with self.assertRaises(ValidationError) as caught:
            parse_confirm(self._doc(confirmed_by="codex"))
        self.assertIn("only 'max' confirms", str(caught.exception))

    def test_a_confirm_on_a_fail_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            parse_confirm(self._doc(verdict="fail"))
        self.assertIn("only ever made against a PASS", str(caught.exception))

    def test_a_zero_ceiling_is_refused(self):
        with self.assertRaises(ValidationError):
            parse_confirm(self._doc(allowed_pct=0.0))

    def test_a_standing_order_is_refused(self):
        """More than a session is a standing order, and the desk has none."""
        with self.assertRaises(ValidationError) as caught:
            parse_confirm(self._doc(expires_at=NOW + timedelta(days=3)))
        self.assertIn("standing order", str(caught.exception))

    def test_a_naive_timestamp_is_refused(self):
        with self.assertRaises(ValidationError):
            parse_confirm(self._doc(confirmed_at="2026-09-21T06:30:00"))

    def test_a_bad_digest_is_refused(self):
        with self.assertRaises(ValidationError):
            parse_confirm(self._doc(stamp_sha256="abc"))

    def test_render_round_trips(self):
        mode, ticket, book, stamp = passing_book()
        confirm = make_confirm(ticket, stamp, book, now=NOW, device="iphone", note='say "hi"')
        import yaml

        back = parse_confirm(yaml.safe_load(render_confirm(confirm)))
        self.assertEqual(back.stamp_sha256, confirm.stamp_sha256)
        self.assertEqual(back.device, "iphone")
        self.assertEqual(back.expires_at, confirm.expires_at)


class BookMovedTests(unittest.TestCase):
    def test_a_confirm_is_void_when_the_book_moves(self):
        """The rule with teeth: re-stamp, re-confirm."""
        mode, ticket, book, stamp = passing_book()
        confirm = make_confirm(ticket, stamp, book, now=NOW, device="iphone")
        # Same ticket, lower conviction: a different ceiling, a different digest.
        moved_ticket = build_ticket(confidence=3)
        moved = stamp_book([moved_ticket], mode, now=NOW)
        moved_stamp = moved.by_id(ticket.id)
        self.assertNotEqual(moved_stamp.allowed_pct, stamp.allowed_pct)
        problems = confirm.problems(moved_stamp, moved, now=NOW)
        self.assertTrue(any("book moved" in p for p in problems))

    def test_an_expired_confirm_is_named(self):
        mode, ticket, book, stamp = passing_book()
        confirm = make_confirm(ticket, stamp, book, now=NOW, device="mac")
        problems = confirm.problems(stamp, book, now=NOW + DEFAULT_TTL + timedelta(minutes=1))
        self.assertTrue(any("expired" in p for p in problems))

    def test_usable_splits_good_from_bad(self):
        mode, ticket, book, stamp = passing_book()
        confirm = make_confirm(ticket, stamp, book, now=NOW, device="mac")
        good, bad = usable({ticket.id: confirm}, book, now=NOW)
        self.assertIn(ticket.id, good)
        self.assertEqual(bad, [])
        good, bad = usable({ticket.id: confirm}, book, now=NOW + timedelta(days=1))
        self.assertEqual(good, {})
        self.assertTrue(bad)

    def test_the_digest_ignores_reason_wording(self):
        mode, ticket, book, stamp = passing_book()
        from dataclasses import replace

        reworded = replace(stamp, reasons=["different prose, same decision"])
        self.assertEqual(stamp_digest(stamp, book), stamp_digest(reworded, book))

    def test_the_digest_binds_the_mode(self):
        mode, ticket, book, stamp = passing_book()
        from dataclasses import replace

        other_mode = replace(book, execution="broker_sheets")
        self.assertNotEqual(stamp_digest(stamp, book), stamp_digest(stamp, other_mode))


class FilesTests(unittest.TestCase):
    def test_write_then_load_newest_per_ticket(self):
        import tempfile
        from pathlib import Path

        mode, ticket, book, stamp = passing_book()
        early = make_confirm(ticket, stamp, book, now=NOW - timedelta(hours=1), device="mac")
        late = make_confirm(ticket, stamp, book, now=NOW, device="iphone")
        with tempfile.TemporaryDirectory() as tmp:
            write_confirm(early, tmp)
            write_confirm(late, tmp)
            found = load_confirms(tmp)
        self.assertEqual(found[ticket.id].device, "iphone")


class SheetTests(unittest.TestCase):
    def test_a_sheet_needs_a_matching_confirm(self):
        mode, ticket, book, stamp = passing_book()
        confirm = make_confirm(ticket, stamp, book, now=NOW, device="iphone")
        sheet = format_sheet(ticket, stamp, book, mode, confirm, now=NOW, risk_budget_usd=100_000)
        self.assertTrue(sheet.paper, "every venue is live:false, so the sheet is paper")
        self.assertAlmostEqual(sheet.risk_usd, stamp.allowed_pct / 100 * 100_000)
        self.assertIsNotNone(sheet.notional_usd)
        self.assertIn("PAPER SHEET", sheet.render())

    def test_a_sheet_is_refused_on_a_void_confirm(self):
        mode, ticket, book, stamp = passing_book()
        confirm = make_confirm(ticket, stamp, book, now=NOW, device="iphone")
        with self.assertRaises(ValidationError) as caught:
            format_sheet(ticket, stamp, book, mode, confirm, now=NOW + timedelta(days=1))
        self.assertIn("expired", str(caught.exception))

    def test_a_sheet_is_refused_for_the_wrong_ticket(self):
        mode, ticket, book, stamp = passing_book()
        confirm = make_confirm(ticket, stamp, book, now=NOW, device="iphone")
        other = build_ticket(id="T-OTHER")
        with self.assertRaises(ValidationError):
            format_sheet(other, stamp, book, mode, confirm, now=NOW)

    def test_a_ticket_without_price_structure_is_kicked_back_not_guessed(self):
        # A defined-risk ticket with no entry passes Rails but cannot be sized.
        mode, ticket, book, stamp = passing_book(entry=None, stop=None, defined_risk=True)
        confirm = make_confirm(ticket, stamp, book, now=NOW, device="mac")
        sheet = format_sheet(ticket, stamp, book, mode, confirm, now=NOW, risk_budget_usd=50_000)
        self.assertIsNone(sheet.notional_usd)
        self.assertIn("kicked back", sheet.render())

    def test_write_sheet_names_paper(self):
        import tempfile

        mode, ticket, book, stamp = passing_book()
        confirm = make_confirm(ticket, stamp, book, now=NOW, device="mac")
        sheet = format_sheet(ticket, stamp, book, mode, confirm, now=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_sheet(sheet, tmp)
            self.assertIn(".paper.sheet.md", path.name)


if __name__ == "__main__":
    unittest.main()
