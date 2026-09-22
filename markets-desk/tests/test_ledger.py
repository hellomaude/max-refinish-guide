"""Ledger tests: the desk's memory of whether it was right."""

from __future__ import annotations

import unittest

from desk.ledger import Outcome, calibration_report, parse_outcome, score
from desk.loader import ValidationError
from tests.helpers import NOW


def outcome(ticket_id: str, *, taken=True, r=None, seats=("Chain",), conf=3, theme="crypto") -> Outcome:
    return Outcome(
        ticket_id=ticket_id,
        decided_at=NOW,
        taken=taken,
        result_r=r,
        seats=seats,
        confidence=conf,
        theme=theme,
        reason="" if taken else "stood down",
    )


class ParsingTests(unittest.TestCase):
    def test_a_skip_must_say_why(self):
        with self.assertRaises(ValidationError) as caught:
            parse_outcome({"ticket_id": "T", "decided_at": "2026-09-21T06:00:00-07:00",
                           "taken": False})
        self.assertIn("reason", str(caught.exception))

    def test_a_skip_with_a_reason_is_recorded(self):
        parsed = parse_outcome({"ticket_id": "T", "decided_at": "2026-09-21T06:00:00-07:00",
                                "taken": False, "reason": "gate never opened"})
        self.assertFalse(parsed.taken)
        self.assertFalse(parsed.resolved)

    def test_an_open_position_is_not_yet_scoreable(self):
        parsed = parse_outcome({"ticket_id": "T", "decided_at": "2026-09-21T06:00:00-07:00",
                                "taken": True, "sized_pct": 0.4})
        self.assertTrue(parsed.taken)
        self.assertFalse(parsed.resolved)


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.outcomes = [
            outcome("A", r=2.0, seats=("Chain",), conf=5),
            outcome("B", r=-1.0, seats=("Chain",), conf=3),
            outcome("C", r=1.0, seats=("Odds",), conf=4),
            outcome("D", taken=False, seats=("Odds",), conf=2),
        ]

    def test_expectancy_and_hit_rate_by_seat(self):
        by_seat = {s.key: s for s in score(self.outcomes, dimension="seat")}
        chain = by_seat["Chain"]
        self.assertEqual(chain.resolved, 2)
        self.assertAlmostEqual(chain.expectancy_r, 0.5)
        self.assertAlmostEqual(chain.hit_rate, 0.5)
        self.assertAlmostEqual(chain.total_r, 1.0)
        self.assertAlmostEqual(chain.worst_r, -1.0)

    def test_skips_count_as_proposed_but_not_resolved(self):
        by_seat = {s.key: s for s in score(self.outcomes, dimension="seat")}
        odds = by_seat["Odds"]
        self.assertEqual(odds.proposed, 2)
        self.assertEqual(odds.taken, 1)
        self.assertEqual(odds.resolved, 1)

    def test_a_ticket_credits_every_seat_that_sourced_it(self):
        shared = [outcome("A", r=1.0, seats=("Chain", "Odds"))]
        keys = {s.key for s in score(shared, dimension="seat")}
        self.assertEqual(keys, {"Chain", "Odds"})

    def test_unknown_dimension_is_refused(self):
        with self.assertRaises(ValueError):
            score(self.outcomes, dimension="phase_of_moon")


class CalibrationTests(unittest.TestCase):
    def test_says_nothing_on_a_thin_book(self):
        lines = calibration_report([outcome("A", r=1.0, conf=4)])
        self.assertIn("not enough resolved", lines[0])

    def test_flags_an_inverted_ladder(self):
        """High conviction losing to low conviction is the signal worth having."""
        outcomes = [outcome(f"L{i}", r=1.5, conf=2) for i in range(6)]
        outcomes += [outcome(f"H{i}", r=-0.5, conf=5) for i in range(6)]
        report = " ".join(calibration_report(outcomes))
        self.assertIn("underperforms", report)
        self.assertIn("not earning its slope", report)

    def test_accepts_a_ladder_that_works(self):
        outcomes = [outcome(f"L{i}", r=0.1, conf=2) for i in range(6)]
        outcomes += [outcome(f"H{i}", r=1.5, conf=5) for i in range(6)]
        report = " ".join(calibration_report(outcomes))
        self.assertIn("as intended", report)

    def test_warns_about_thin_samples(self):
        outcomes = [outcome("A", r=0.1, conf=2), outcome("B", r=1.0, conf=5)]
        report = " ".join(calibration_report(outcomes))
        self.assertIn("thin samples", report)


if __name__ == "__main__":
    unittest.main()
