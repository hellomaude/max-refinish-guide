"""Rails engine tests.

The engine's whole value is that it decides the same way twice, so these
tests are mostly about invariants: no cap is ever breached, and each gate
binds for the stated reason rather than by accident.
"""

from __future__ import annotations

import random
import unittest
from datetime import timedelta

from desk.loader import ValidationError
from desk.risk import FAIL, PASS, PENDING, Book, OpenRisk, stamp_book
from tests.helpers import NOW, build_mode, build_ticket, hours_ago


def _sum_for_theme(book: Book, theme_id: str) -> float:
    return sum(s.allowed_pct for s in book.stamps if s.theme == theme_id)


class ConvictionLadderTests(unittest.TestCase):
    def test_ladder_scales_the_single_name_cap(self):
        mode = build_mode()
        for confidence, expected in ((1, 0.0), (2, 0.2), (3, 0.4), (4, 0.7), (5, 1.0)):
            ticket = build_ticket(id=f"T-{confidence}", confidence=confidence, size_hint_pct=1.0)
            book = stamp_book([ticket], mode, now=NOW)
            self.assertAlmostEqual(book.stamps[0].allowed_pct, expected, places=2,
                                   msg=f"confidence {confidence}")

    def test_confidence_one_is_research_not_a_position(self):
        book = stamp_book([build_ticket(confidence=1)], build_mode(), now=NOW)
        self.assertEqual(book.stamps[0].verdict, FAIL)
        self.assertEqual(book.stamps[0].allowed_pct, 0.0)

    def test_allowance_never_exceeds_the_ask(self):
        ticket = build_ticket(confidence=5, size_hint_pct=0.25)
        book = stamp_book([ticket], build_mode(), now=NOW)
        self.assertAlmostEqual(book.stamps[0].allowed_pct, 0.25, places=2)
        self.assertEqual(book.stamps[0].binding_constraint, "size_hint")


class ThemeCapTests(unittest.TestCase):
    def test_correlated_legs_share_one_cap(self):
        mode = build_mode()
        legs = [
            build_ticket(id="A", instrument={"symbol": "COIN"}, confidence=5),
            build_ticket(id="B", instrument={"symbol": "HOOD"}, confidence=5),
            build_ticket(id="C", instrument={"symbol": "MSTR"}, confidence=5),
        ]
        book = stamp_book(legs, mode, now=NOW)
        # Each leg would take 1.0% alone; together they may not exceed 1.5%.
        self.assertLessEqual(_sum_for_theme(book, "crypto_policy_beta"), 1.5 + 1e-9)
        self.assertGreater(_sum_for_theme(book, "crypto_policy_beta"), 1.4)

    def test_higher_conviction_gets_the_larger_share(self):
        mode = build_mode()
        legs = [
            build_ticket(id="A", instrument={"symbol": "COIN"}, confidence=5),
            build_ticket(id="B", instrument={"symbol": "HOOD"}, confidence=2),
        ]
        book = stamp_book(legs, mode, now=NOW)
        high = book.by_id("A").allowed_pct
        low = book.by_id("B").allowed_pct
        self.assertGreater(high, low)

    def test_slack_from_a_capped_leg_is_redistributed(self):
        """Water-filling, not flat scaling.

        B is ceiling-bound at 0.2% by its own conviction. A flat scale would
        shrink both legs; the freed room should go to A instead.
        """
        mode = build_mode()
        legs = [
            build_ticket(id="A", instrument={"symbol": "COIN"}, confidence=5, size_hint_pct=1.0),
            build_ticket(id="B", instrument={"symbol": "HOOD"}, confidence=2, size_hint_pct=1.0),
        ]
        book = stamp_book(legs, mode, now=NOW)
        self.assertAlmostEqual(book.by_id("B").allowed_pct, 0.2, places=2)
        self.assertAlmostEqual(book.by_id("A").allowed_pct, 1.0, places=2)

    def test_open_risk_consumes_the_theme_cap(self):
        mode = build_mode()
        ticket = build_ticket(instrument={"symbol": "COIN"}, confidence=5)
        book = stamp_book(
            [ticket], mode, now=NOW,
            open_risk=OpenRisk(by_theme={"crypto_policy_beta": 1.2}),
        )
        self.assertAlmostEqual(book.stamps[0].allowed_pct, 0.3, places=2)

    def test_one_member_theme_is_a_single_name_override(self):
        mode = build_mode()
        ticket = build_ticket(id="S", instrument={"symbol": "SBLK"}, confidence=5, size_hint_pct=1.0)
        book = stamp_book([ticket], mode, now=NOW)
        self.assertEqual(book.stamps[0].theme, "insider_shipping")
        self.assertAlmostEqual(book.stamps[0].allowed_pct, 0.75, places=2)


class PortfolioHeatTests(unittest.TestCase):
    def test_heat_cap_binds_across_themes(self):
        mode = build_mode(caps={"portfolio_heat_pct": 1.0, "single_name_pct": 1.0,
                                "default_theme_pct": 1.5})
        legs = [
            build_ticket(id="A", instrument={"symbol": "COIN"}, confidence=5),
            build_ticket(id="B", instrument={"symbol": "SBLK"}, confidence=5),
        ]
        book = stamp_book(legs, mode, now=NOW)
        self.assertLessEqual(sum(s.allowed_pct for s in book.stamps), 1.0 + 1e-9)

    def test_open_risk_consumes_heat(self):
        mode = build_mode()
        ticket = build_ticket(confidence=5)
        book = stamp_book([ticket], mode, now=NOW,
                          open_risk=OpenRisk(by_theme={"other": 2.9}))
        self.assertLessEqual(book.stamps[0].allowed_pct, 0.1 + 1e-9)


class StalenessTests(unittest.TestCase):
    def test_frozen_greeks_fail_the_ticket(self):
        """The Friday-OpEx failure, as a test.

        The number is plausible and the source is real; only `as_of` gives it
        away, which is exactly why a human checklist kept missing it.
        """
        mode = build_mode()
        ticket = build_ticket(
            evidence=[{"key": "gex", "kind": "options_greeks", "value": -1.2e9,
                       "source": "GEX Metrix", "as_of": hours_ago(72)}],
        )
        book = stamp_book([ticket], mode, now=NOW)
        stamp = book.stamps[0]
        self.assertEqual(stamp.verdict, FAIL)
        self.assertEqual(stamp.allowed_pct, 0.0)
        self.assertEqual(stamp.binding_constraint, "staleness")
        self.assertIn("gex", stamp.stale_evidence[0])

    def test_fresh_greeks_pass(self):
        mode = build_mode()
        ticket = build_ticket(
            evidence=[{"key": "gex", "kind": "options_greeks", "value": -1.2e9,
                       "source": "CBOE delayed chain", "as_of": hours_ago(2)}],
        )
        book = stamp_book([ticket], mode, now=NOW)
        self.assertEqual(book.stamps[0].verdict, PASS)

    def test_unknown_evidence_kind_falls_back_to_default(self):
        mode = build_mode()
        ticket = build_ticket(
            evidence=[{"key": "vibes", "kind": "not_a_known_kind", "value": 1,
                       "source": "X", "as_of": hours_ago(100)}],
        )
        book = stamp_book([ticket], mode, now=NOW)
        self.assertEqual(book.stamps[0].verdict, FAIL, "default tolerance is 72h")


class EventWindowTests(unittest.TestCase):
    WINDOW = {
        "id": "pmi",
        "starts_at": "2026-09-22T12:55:00-07:00",
        "ends_at": "2026-09-23T07:30:00-07:00",
        "overnight_risk_pct": 0.0,
        "max_pct_around_event": 0.5,
        "applies_to_kinds": ["equity", "etf", "crypto_spot"],
    }

    def test_overnight_rule_zeroes_a_swing_equity(self):
        mode = build_mode(event_windows=[self.WINDOW])
        ticket = build_ticket(horizon="swing", confidence=5)
        book = stamp_book([ticket], mode, now=NOW)
        self.assertEqual(book.stamps[0].allowed_pct, 0.0)
        self.assertIn("overnight", book.stamps[0].binding_constraint)

    def test_intraday_keeps_the_around_event_cap(self):
        mode = build_mode(event_windows=[self.WINDOW])
        # An intraday ticket on Tuesday overlaps the window but holds nothing over.
        # Its evidence has to be fresh as of Tuesday too, or the staleness gate
        # fires first and the event cap is never reached.
        tuesday = NOW + timedelta(days=1, hours=7)
        ticket = build_ticket(
            horizon="intraday",
            confidence=5,
            evidence=[{"key": "spot", "kind": "price", "value": 81300, "source": "Kraken",
                       "as_of": hours_ago(1, base=tuesday)}],
        )
        book = stamp_book([ticket], mode, now=tuesday)
        self.assertAlmostEqual(book.stamps[0].allowed_pct, 0.5, places=2)

    def test_window_does_not_bind_an_unlisted_instrument_kind(self):
        """A December binary cannot be flattened into a Wednesday print."""
        mode = build_mode(event_windows=[self.WINDOW])
        ticket = build_ticket(
            instrument={"kind": "prediction_market", "symbol": "clarity-act-signed-2026",
                        "venue": "polymarket", "outcome": "No"},
            horizon="position",
            defined_risk=True,
            entry=0.925,
            stop=None,
            confidence=3,
            size_hint_pct=0.5,
        )
        book = stamp_book([ticket], mode, now=NOW)
        self.assertEqual(book.stamps[0].allowed_pct, 0.4)

    def test_window_outside_the_horizon_does_not_bind(self):
        mode = build_mode(event_windows=[self.WINDOW])
        ticket = build_ticket(horizon="intraday", confidence=5)
        book = stamp_book([ticket], mode, now=NOW)  # Monday; window opens Tuesday
        self.assertAlmostEqual(book.stamps[0].allowed_pct, 1.0, places=2)


class HardStopTests(unittest.TestCase):
    def test_halt_mode_zeroes_everything(self):
        mode = build_mode(mode="halt")
        book = stamp_book([build_ticket(), build_ticket(id="T-002")], mode, now=NOW)
        self.assertTrue(all(s.allowed_pct == 0.0 and s.verdict == FAIL for s in book.stamps))
        self.assertEqual(book.stamps[0].binding_constraint, "mode.halt")

    def test_disabled_venue_refuses_the_ticket(self):
        mode = build_mode()
        ticket = build_ticket(instrument={"kind": "option", "symbol": "COIN", "venue": "option"})
        book = stamp_book([ticket], mode, now=NOW)
        self.assertEqual(book.stamps[0].verdict, FAIL)
        self.assertIn("venue.option", book.stamps[0].binding_constraint)

    def test_missing_required_seat_is_pending_not_pass(self):
        mode = build_mode(required_seats=["Rails", "Odds"])
        book = stamp_book([build_ticket()], mode, now=NOW, available_seats=["Rails"])
        stamp = book.stamps[0]
        self.assertEqual(stamp.verdict, PENDING)
        self.assertEqual(stamp.allowed_pct, 0.0)
        self.assertEqual(stamp.missing_seats, ["Odds"])

    def test_explicit_rails_fail_is_honoured(self):
        book = stamp_book([build_ticket(rails_check="fail")], build_mode(), now=NOW)
        self.assertEqual(book.stamps[0].verdict, FAIL)

    def test_pending_ticket_still_gets_a_provisional_number(self):
        book = stamp_book([build_ticket(rails_check="pending", confidence=3)],
                          build_mode(), now=NOW)
        self.assertEqual(book.stamps[0].verdict, PENDING)
        self.assertAlmostEqual(book.stamps[0].allowed_pct, 0.4, places=2)


class InvariantTests(unittest.TestCase):
    def test_caps_hold_across_random_books(self):
        """No generated book may breach a theme cap or the heat cap."""
        rng = random.Random(20260921)
        mode = build_mode()
        symbols = ["COIN", "HOOD", "MSTR", "BTC", "SBLK"]
        for trial in range(200):
            tickets = [
                build_ticket(
                    id=f"T-{i}",
                    instrument={"symbol": rng.choice(symbols)},
                    confidence=rng.randint(1, 5),
                    size_hint_pct=round(rng.uniform(0.0, 3.0), 2),
                )
                for i in range(rng.randint(1, 6))
            ]
            book = stamp_book(tickets, mode, now=NOW)
            with self.subTest(trial=trial):
                total = sum(s.allowed_pct for s in book.stamps)
                self.assertLessEqual(total, mode.portfolio_heat_pct + 1e-9)
                for theme_id in {s.theme for s in book.stamps}:
                    self.assertLessEqual(
                        _sum_for_theme(book, theme_id),
                        mode.cap_for_theme(theme_id) + 1e-9,
                    )
                for stamp in book.stamps:
                    self.assertLessEqual(stamp.allowed_pct, stamp.requested_pct + 1e-9)
                    self.assertGreaterEqual(stamp.allowed_pct, 0.0)

    def test_stamping_is_deterministic(self):
        mode = build_mode()
        tickets = [
            build_ticket(id="A", instrument={"symbol": "COIN"}, confidence=4),
            build_ticket(id="B", instrument={"symbol": "HOOD"}, confidence=3),
        ]
        first = stamp_book(tickets, mode, now=NOW)
        second = stamp_book(tickets, mode, now=NOW)
        self.assertEqual(
            [(s.ticket_id, s.allowed_pct, s.verdict) for s in first.stamps],
            [(s.ticket_id, s.allowed_pct, s.verdict) for s in second.stamps],
        )

    def test_rounding_floors_rather_than_breaching_a_cap(self):
        mode = build_mode(caps={"portfolio_heat_pct": 0.999, "single_name_pct": 1.0,
                                "default_theme_pct": 1.5})
        book = stamp_book([build_ticket(confidence=5)], mode, now=NOW)
        self.assertLessEqual(book.stamps[0].allowed_pct, 0.999)
        self.assertAlmostEqual(book.stamps[0].allowed_pct, 0.99, places=2)


if __name__ == "__main__":
    unittest.main()
