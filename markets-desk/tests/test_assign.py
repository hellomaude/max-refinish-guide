"""Assignments: the desk pointing a research seat at something.

The load-bearing claims here are about priority and about double-counting,
because both were wrong in the first draft and running it against the real
book is what exposed them.
"""

from __future__ import annotations

import unittest
from datetime import timedelta
from typing import Any

from desk.assign import (
    Assignment,
    audit,
    build_assignment,
    load_assignment,
    parse_assignment,
    render_assignment,
)
from desk.loader import ValidationError
from desk.report import parse_report
from tests.helpers import NOW, build_mode, build_ticket, hours_ago

HEADLINE = "Crypto-policy chatter thinning since the cloture vote; COIN is the loud leg"


def build_grok(**overrides: Any):
    doc: dict[str, Any] = {
        "schema_version": 2,
        "seat": "Grok",
        "produced_at": hours_ago(1),
        "read": "mixed",
        "headline": HEADLINE,
        "covers": ["COIN", "BTC"],
        "crowding": {"COIN": "consensus", "BTC": "differentiated"},
        "evidence": [
            {
                "key": "coin_mentions_7d",
                "kind": "social",
                "value": "up ~180% vs the prior week",
                "source": "X, aggregate mention count",
                "as_of": hours_ago(1),
            }
        ],
    }
    doc.update(overrides)
    return parse_report(doc, where="test-grok")


class PriorityTests(unittest.TestCase):
    def test_a_ticket_that_declares_no_size_is_not_priced_at_zero(self):
        """The bug the real book exposed.

        Four of five live tickets carry `size_hint_pct: 0.0` — they ask Rails
        to size them. Ranking by the declared hint sorted exactly the tickets
        most in need of a crowding read to the bottom of the work order.
        """
        asks_nothing = build_ticket(id="T-NOSIZE", size_hint_pct=0.0, confidence=1)
        assignment = build_assignment("Grok", [asks_nothing], build_mode(), now=NOW)
        task = assignment.task_for("COIN", "crowding")
        self.assertIsNotNone(task)
        self.assertAlmostEqual(task.at_stake_pct, 1.5)

    def test_confidence_does_not_discount_the_priority(self):
        """Discounting by the number the research produces is circular.

        A confidence-1 ticket earns a 0.00 ladder fraction, so pricing the
        work by the ladder priced every unresearched name at zero.
        """
        low = build_ticket(id="T-LOW", size_hint_pct=0.0, confidence=1)
        high = build_ticket(id="T-HIGH", size_hint_pct=0.0, confidence=5)
        mode = build_mode()
        lo = build_assignment("Grok", [low], mode, now=NOW).task_for("COIN", "crowding")
        hi = build_assignment("Grok", [high], mode, now=NOW).task_for("COIN", "crowding")
        self.assertEqual(lo.at_stake_pct, hi.at_stake_pct)

    def test_a_declared_hint_still_caps_the_figure(self):
        small = build_ticket(id="T-SMALL", size_hint_pct=0.25)
        task = build_assignment(
            "Grok", [small], build_mode(), now=NOW
        ).task_for("COIN", "crowding")
        self.assertAlmostEqual(task.at_stake_pct, 0.25)

    def test_the_work_order_is_sorted_by_what_is_at_stake(self):
        tickets = [
            build_ticket(id="T-SBLK", instrument={"symbol": "SBLK"},
                         theme="insider_shipping", size_hint_pct=0.0),
            build_ticket(id="T-COIN", size_hint_pct=0.0),
        ]
        assignment = build_assignment("Grok", tickets, build_mode(), now=NOW)
        self.assertEqual(assignment.subjects("crowding")[0], "COIN")


class DoubleCountTests(unittest.TestCase):
    def test_correlated_legs_are_counted_once(self):
        """Three legs sharing a 1.5% ceiling put 1.5% at stake, not 4.5%.

        Reintroducing the double-count in the module that tells a seat where
        to look would be a strange place to lose the desk's whole thesis about
        correlation.
        """
        legs = [
            build_ticket(id="T-COIN", instrument={"symbol": "COIN"}, size_hint_pct=0.0),
            build_ticket(id="T-HOOD", instrument={"symbol": "HOOD"}, size_hint_pct=0.0),
            build_ticket(id="T-BTC", instrument={"symbol": "BTC", "kind": "crypto_spot"},
                         size_hint_pct=0.0),
        ]
        assignment = build_assignment("Grok", legs, build_mode(), now=NOW)
        self.assertEqual(len(assignment.subjects("crowding")), 3)
        self.assertAlmostEqual(assignment.at_stake_pct, 1.5)

    def test_separate_themes_add_up(self):
        tickets = [
            build_ticket(id="T-COIN", size_hint_pct=0.0),
            build_ticket(id="T-SBLK", instrument={"symbol": "SBLK"},
                         theme="insider_shipping", size_hint_pct=0.0),
        ]
        assignment = build_assignment("Grok", tickets, build_mode(), now=NOW)
        self.assertAlmostEqual(assignment.at_stake_pct, 2.25)


class TaskGenerationTests(unittest.TestCase):
    def test_a_fresh_call_is_not_reassigned(self):
        ticket = build_ticket(id="T-COIN")
        assignment = build_assignment(
            "Grok", [ticket], build_mode(), now=NOW, prior=build_grok()
        )
        self.assertNotIn("COIN", assignment.subjects("crowding"))

    def test_a_call_past_the_freshness_budget_is_reassigned(self):
        """Social evidence goes stale in 48 hours by policy."""
        old = build_grok(produced_at=hours_ago(100), evidence=[
            {"key": "coin_mentions_7d", "kind": "social", "value": "flat",
             "source": "X", "as_of": hours_ago(100)},
        ])
        assignment = build_assignment(
            "Grok", [build_ticket(id="T-COIN")], build_mode(), now=NOW, prior=old
        )
        self.assertIn("COIN", assignment.subjects("crowding"))

    def test_the_freshness_budget_comes_from_policy(self):
        mode = build_mode(staleness_hours={"default": 72, "social": 6})
        task = build_assignment(
            "Grok", [build_ticket(id="T-COIN")], mode, now=NOW
        ).task_for("COIN", "crowding")
        self.assertEqual(task.max_age_hours, 6)

    def test_a_dated_catalyst_becomes_its_own_task(self):
        ticket = build_ticket(
            id="T-CAT",
            catalyst="Senate re-runs cloture on H.R.3633 once sixty votes exist",
            catalyst_at=(NOW + timedelta(days=30)).isoformat(),
        )
        assignment = build_assignment("Grok", [ticket], build_mode(), now=NOW)
        self.assertEqual(len(assignment.subjects("catalyst")), 1)

    def test_a_past_catalyst_is_not_assigned(self):
        ticket = build_ticket(
            id="T-OLD",
            catalyst="A print that already happened",
            catalyst_at=(NOW - timedelta(days=2)).isoformat(),
        )
        assignment = build_assignment("Grok", [ticket], build_mode(), now=NOW)
        self.assertEqual(assignment.subjects("catalyst"), ())

    def test_a_paragraph_catalyst_is_gisted_to_a_usable_subject(self):
        """A ticket's catalyst is prose and can run to a paragraph.

        Used unedited it produced a 300-character YAML subject that no seat
        could answer against and no terminal could print.
        """
        ticket = build_ticket(
            id="T-LONG",
            catalyst=(
                "Absence of a catalyst is the thesis: each week without floor action "
                "decays Yes toward zero. The live procedural hook is Senator Tillis's "
                "motion to reconsider, which leaves the bill on the calendar and lets "
                "the majority re-run the vote the day sixty votes exist."
            ),
            catalyst_at=(NOW + timedelta(days=60)).isoformat(),
        )
        subject = build_assignment("Grok", [ticket], build_mode(), now=NOW).subjects("catalyst")[0]
        self.assertLessEqual(len(subject), 91)
        self.assertNotIn("\n", subject)


class CoverageTests(unittest.TestCase):
    def _assignment(self, *symbols: str) -> Assignment:
        tickets = [
            build_ticket(id=f"T-{s}", instrument={"symbol": s}, size_hint_pct=0.0)
            for s in symbols
        ]
        return build_assignment("Grok", tickets, build_mode(), now=NOW)

    def test_an_unanswered_ask_is_named(self):
        coverage = audit(self._assignment("COIN", "SBLK"), build_grok(), now=NOW)
        self.assertEqual(coverage.unanswered, ("SBLK",))
        self.assertEqual(coverage.answered, ("COIN",))

    def test_a_silent_seat_answers_nothing(self):
        coverage = audit(self._assignment("COIN"), None, now=NOW)
        self.assertEqual(coverage.answer_rate, 0.0)
        self.assertFalse(coverage.complete)

    def test_a_no_read_report_answers_nothing(self):
        dark = build_grok(
            read="no_read", crowding={}, covers=[], evidence=[],
            unavailable=["X search API returning 429"],
        )
        coverage = audit(self._assignment("COIN"), dark, now=NOW)
        self.assertEqual(coverage.unanswered, ("COIN",))

    def test_a_volunteered_name_is_tracked_as_unsolicited(self):
        """Not a failure. It is the drift signal when it replaces the asks."""
        coverage = audit(self._assignment("COIN"), build_grok(), now=NOW)
        self.assertEqual(coverage.unsolicited, ("BTC",))

    def test_an_answer_past_its_budget_is_stale_not_answered(self):
        late = build_grok(evidence=[
            {"key": "coin_mentions_7d", "kind": "social", "value": "up 180%",
             "source": "X", "as_of": hours_ago(100)},
        ])
        coverage = audit(self._assignment("COIN"), late, now=NOW)
        self.assertEqual(coverage.stale, ("COIN",))
        self.assertEqual(coverage.answered, ())

    def test_a_complete_answer_is_complete(self):
        coverage = audit(self._assignment("COIN", "BTC"), build_grok(), now=NOW)
        self.assertTrue(coverage.complete)
        self.assertEqual(coverage.answer_rate, 1.0)


class ContractTests(unittest.TestCase):
    def _doc(self) -> dict[str, Any]:
        assignment = build_assignment(
            "Grok", [build_ticket(id="T-COIN")], build_mode(), now=NOW
        )
        import yaml

        return yaml.safe_load(render_assignment(assignment))

    def test_render_parses_back_to_the_same_assignment(self):
        original = build_assignment(
            "Grok",
            [
                build_ticket(id="T-COIN", size_hint_pct=0.0),
                build_ticket(id="T-SBLK", instrument={"symbol": "SBLK"},
                             theme="insider_shipping", size_hint_pct=0.0),
            ],
            build_mode(),
            now=NOW,
        )
        text = render_assignment(original)
        import yaml

        back = parse_assignment(yaml.safe_load(text))
        self.assertEqual(back.subjects(), original.subjects())
        self.assertAlmostEqual(back.at_stake_pct, original.at_stake_pct)
        self.assertEqual(render_assignment(back), text)

    def test_an_unknown_task_kind_is_refused(self):
        doc = self._doc()
        doc["tasks"][0]["kind"] = "vibes"
        with self.assertRaises(ValidationError) as caught:
            parse_assignment(doc)
        self.assertIn("kind", str(caught.exception))

    def test_a_duplicate_task_id_is_refused(self):
        doc = self._doc()
        doc["tasks"].append(dict(doc["tasks"][0]))
        with self.assertRaises(ValidationError) as caught:
            parse_assignment(doc)
        self.assertIn("duplicate task_id", str(caught.exception))

    def test_a_naive_answer_by_is_refused(self):
        doc = self._doc()
        doc["tasks"][0]["answer_by"] = "2026-09-22T12:00:00"
        with self.assertRaises(ValidationError):
            parse_assignment(doc)


class ShippedAssignmentTests(unittest.TestCase):
    def test_the_committed_assignment_is_valid(self):
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / "assignments"
        found = sorted(path.glob("*.assignment.yaml")) if path.exists() else []
        for item in found:
            assignment = load_assignment(item)
            self.assertTrue(assignment.tasks, f"{item} assigns nothing")
            for task in assignment.tasks:
                self.assertLessEqual(
                    len(task.subject), 120, f"{item}: unusable subject line"
                )


if __name__ == "__main__":
    unittest.main()
