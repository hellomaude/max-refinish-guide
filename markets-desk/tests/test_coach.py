"""Grading the one seat nothing was grading.

A seat that never originates a ticket never lands in the outcome ledger, so
Grok could be wrong indefinitely at no cost. A crowding call is falsifiable,
which is what makes it scoreable: `consensus` claims the edge is gone, and a
name called consensus that then worked is a call that argued a winner down.
"""

from __future__ import annotations

import unittest
from datetime import timedelta
from typing import Any

from desk.assign import build_assignment
from desk.coach import (
    BEARISH,
    coach,
    coverage_history,
    grade_crowding,
    grade_report,
    level_counts,
)
from desk.ledger import Outcome
from desk.report import parse_report
from tests.helpers import NOW, build_mode, build_ticket


def report(crowding: dict[str, str], *, at=NOW, seat="Grok"):
    doc: dict[str, Any] = {
        "schema_version": 2,
        "seat": seat,
        "produced_at": (at - timedelta(hours=1)).isoformat(),
        "read": "mixed",
        "headline": "Attention read across the crypto-policy cluster and shipping",
        "covers": sorted(crowding),
        "crowding": dict(crowding),
        "evidence": [
            {
                "key": "mentions_7d",
                "kind": "social",
                "value": "baselined against the prior week",
                "source": "X, aggregate mention count",
                "as_of": (at - timedelta(hours=1)).isoformat(),
            }
        ],
    }
    return parse_report(doc, where="test-grok")


def ticket(tid: str, symbol: str):
    return build_ticket(id=tid, instrument={"symbol": symbol})


def outcome(tid: str, r: float | None, *, taken=True, at=None):
    return Outcome(
        ticket_id=tid,
        decided_at=at or NOW,
        taken=taken,
        result_r=r,
        reason="" if taken else "talked out of it",
    )


class TimingTests(unittest.TestCase):
    def test_a_call_filed_after_the_decision_does_not_count(self):
        """Hindsight is not a prediction."""
        late = report({"COIN": "consensus"}, at=NOW + timedelta(days=3))
        grade = grade_crowding(
            [outcome("T1", 1.0)], [late], [ticket("T1", "COIN")]
        )
        self.assertEqual(grade.bearish, [])
        self.assertEqual(grade.hindsight_dropped, 1)
        self.assertEqual(grade.unrated, [1.0])

    def test_the_newest_call_before_the_decision_is_the_one_scored(self):
        early = report({"COIN": "differentiated"}, at=NOW - timedelta(days=5))
        later = report({"COIN": "consensus"}, at=NOW - timedelta(hours=2))
        grade = grade_crowding(
            [outcome("T1", -1.0)], [early, later], [ticket("T1", "COIN")]
        )
        self.assertEqual(grade.bearish, [-1.0])
        self.assertEqual(grade.differentiated, [])

    def test_a_name_never_looked_at_is_unrated_not_dropped(self):
        grade = grade_crowding(
            [outcome("T1", 0.5)], [report({"BTC": "consensus"})], [ticket("T1", "COIN")]
        )
        self.assertEqual(grade.unrated, [0.5])
        self.assertEqual(grade.hindsight_dropped, 0)


class ScoreableTests(unittest.TestCase):
    def test_a_skipped_ticket_after_a_bearish_call_is_a_blind_spot(self):
        """Grok talking the desk out of a trade is the seat working.

        It is also unscoreable, and the desk does not get to know what it
        avoided. Reported rather than smoothed over.
        """
        grade = grade_crowding(
            [outcome("T1", None, taken=False)],
            [report({"COIN": "crowded"})],
            [ticket("T1", "COIN")],
        )
        self.assertEqual(grade.skipped_after_bearish, 1)
        self.assertEqual(grade.scored, 0)
        self.assertIn("cannot see what it avoided", " ".join(grade_report(grade)))

    def test_an_open_position_is_not_scored_yet(self):
        grade = grade_crowding(
            [outcome("T1", None)], [report({"COIN": "consensus"})], [ticket("T1", "COIN")]
        )
        self.assertEqual(grade.scored, 0)

    def test_both_bearish_levels_score_together(self):
        self.assertEqual(set(BEARISH), {"consensus", "crowded"})


class SeparationTests(unittest.TestCase):
    def _grade(self, pairs: list[tuple[str, float]]):
        reports, outcomes, tickets = [], [], []
        for i, (level, r) in enumerate(pairs):
            symbol = f"SYM{i}"
            tid = f"T{i}"
            reports.append(report({symbol: level}, at=NOW - timedelta(hours=2)))
            outcomes.append(outcome(tid, r))
            tickets.append(ticket(tid, symbol))
        return grade_crowding(outcomes, reports, tickets)

    def test_a_seat_whose_consensus_calls_mark_losers_is_earning_its_place(self):
        grade = self._grade(
            [("consensus", -1.0), ("crowded", -0.8), ("consensus", -1.2),
             ("differentiated", 1.0), ("differentiated", 0.8), ("differentiated", 1.2)]
        )
        self.assertGreater(grade.separation_r, 0.25)
        self.assertIn("earning its seat", " ".join(grade_report(grade)))

    def test_a_seat_reading_loudness_as_positioning_is_called_inverted(self):
        """The real failure mode: volume rises *with* a move.

        Mention count flags momentum, not saturation, so a seat scoring volume
        will call the winners consensus.
        """
        grade = self._grade(
            [("consensus", 1.0), ("crowded", 1.2), ("consensus", 0.9),
             ("differentiated", -1.0), ("differentiated", -0.9), ("differentiated", -1.1)]
        )
        self.assertLess(grade.separation_r, -0.25)
        joined = " ".join(grade_report(grade))
        self.assertIn("inverted", joined)
        self.assertIn("Stop scoring volume", " ".join(coach(grade)))

    def test_calls_that_separate_nothing_are_said_to_mean_nothing(self):
        grade = self._grade(
            [("consensus", 0.5), ("crowded", 0.4), ("consensus", 0.6),
             ("differentiated", 0.5), ("differentiated", 0.4), ("differentiated", 0.6)]
        )
        self.assertIn("not separating", " ".join(grade_report(grade)))
        self.assertIn("not distinguishing anything", " ".join(coach(grade)))

    def test_a_thin_record_refuses_to_judge(self):
        grade = self._grade([("consensus", -1.0), ("differentiated", 1.0)])
        self.assertIn("too thin to judge", " ".join(grade_report(grade)))
        self.assertIsNone(grade.separation_r if grade.scored < 2 else None)


class ComplianceTests(unittest.TestCase):
    def _coverage(self, answered: dict[str, str], asked: list[str]):
        tickets = [
            build_ticket(id=f"T-{s}", instrument={"symbol": s}, size_hint_pct=0.0)
            for s in asked
        ]
        assignment = build_assignment("Grok", tickets, build_mode(), now=NOW)
        assignments = {"Grok": assignment}
        history = [report(answered, at=NOW + timedelta(hours=1))] if answered else []
        return coverage_history(assignments, history, now=NOW + timedelta(hours=1))

    def test_a_low_answer_rate_is_coached(self):
        coverage = self._coverage({"COIN": "consensus"}, ["COIN", "SBLK", "HOOD", "BTC"])
        lines = " ".join(coach(grade_crowding([], [], []), coverage))
        self.assertIn("Answer the work order", lines)

    def test_volunteering_instead_of_answering_is_called_drift(self):
        coverage = self._coverage(
            {"DOGE": "crowded", "WIF": "crowded", "PEPE": "crowded", "COIN": "consensus"},
            ["COIN", "SBLK", "HOOD"],
        )
        lines = " ".join(coach(grade_crowding([], [], []), coverage))
        self.assertIn("drift", lines)

    def test_a_clean_seat_is_told_there_is_nothing_to_correct(self):
        coverage = self._coverage({"COIN": "consensus"}, ["COIN"])
        lines = coach(grade_crowding([], [], []), coverage)
        self.assertEqual(len(lines), 1)
        self.assertIn("Nothing to correct", lines[0])

    def test_a_report_answering_before_the_assignment_is_not_an_answer(self):
        tickets = [build_ticket(id="T-COIN", size_hint_pct=0.0)]
        assignment = build_assignment("Grok", tickets, build_mode(), now=NOW)
        earlier = [report({"COIN": "consensus"}, at=NOW - timedelta(days=4))]
        coverage = coverage_history({"Grok": assignment}, earlier, now=NOW)
        self.assertEqual(coverage[0].answered, ())


class UsageTests(unittest.TestCase):
    def test_a_level_that_never_fires_is_reported_as_unused(self):
        counts = level_counts([report({"COIN": "consensus", "BTC": "differentiated"})])
        self.assertEqual(counts["crowded"], 0)
        self.assertEqual(counts["consensus"], 1)

    def test_only_the_named_seat_is_counted(self):
        counts = level_counts(
            [report({"COIN": "crowded"}, seat="Chain")], seat="Grok"
        )
        self.assertEqual(sum(counts.values()), 0)


if __name__ == "__main__":
    unittest.main()
