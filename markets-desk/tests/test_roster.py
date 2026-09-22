"""The roster: many models, one desk, and the rule that stops it being a vote.

Two models agreeing is not evidence. The desk buys diversity of information,
not diversity of models on the same information, and the one place that
matters most is the adversary: a challenge from the proposer's own model is
self-review.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from desk.challenge import parse_challenge
from desk.ledger import Outcome, score
from desk.loader import ValidationError
from desk.roster import check_filings, load_roster, parse_roster
from tests.helpers import NOW, build_ticket

ROOT = Path(__file__).resolve().parent.parent


def build_roster(**overrides: Any):
    doc: dict[str, Any] = {
        "schema_version": 1,
        "updated_at": "2026-09-22T07:30:00-07:00",
        "models": {
            "claude": {"vendor": "Anthropic", "strengths": "plumbing"},
            "grok": {"vendor": "xAI", "strengths": "live X"},
            "gemini": {"vendor": "Google", "strengths": "search grounding"},
        },
        "seats": {
            "Chain": {"model": "claude", "why": "adapter-fed"},
            "Wire": {"model": "gemini", "why": "search grounding"},
            "Grok": {"model": "grok", "why": "live X"},
            "Jev": {"model": "any", "why": "whichever model did not write the ticket"},
        },
        "rules": {"adversary_must_differ": True, "max_research_seats_per_model": 6},
    }
    doc.update(overrides)
    return parse_roster(doc, where="test-roster")


COUNTER = (
    "The funding read is one venue on one interval and says nothing about spot "
    "positioning, which is where the size actually sits."
)


def build_challenge(**overrides: Any):
    doc: dict[str, Any] = {
        "schema_version": 2,
        "ticket_id": "T-001",
        "challenger": "Jev",
        "challenged_at": "2026-09-21T07:15:00-07:00",
        "verdict": "contest",
        "strongest_counter": COUNTER,
        "what_would_change_my_mind": "A second venue showing the same funding skew.",
        "confidence_adjustment": -1,
    }
    doc.update(overrides)
    return parse_challenge(doc, where="test-challenge")


class RosterContractTests(unittest.TestCase):
    def test_an_assignment_needs_a_why(self):
        with self.assertRaises(ValidationError) as caught:
            build_roster(seats={"Chain": {"model": "claude"}})
        self.assertIn("why", str(caught.exception))

    def test_an_undeclared_model_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            build_roster(seats={"Chain": {"model": "gpt", "why": "x"}})
        self.assertIn("not declared", str(caught.exception))

    def test_jev_may_not_be_pinned_to_one_model(self):
        with self.assertRaises(ValidationError) as caught:
            build_roster(seats={"Jev": {"model": "claude", "why": "x"}})
        self.assertIn("pinned", str(caught.exception))

    def test_one_model_cannot_hold_the_whole_desk(self):
        seats = {f"S{i}": {"model": "claude", "why": "x"} for i in range(7)}
        with self.assertRaises(ValidationError) as caught:
            build_roster(seats=seats)
        self.assertIn("over the cap", str(caught.exception))

    def test_the_shipped_roster_loads_and_covers_every_seat(self):
        roster = load_roster(ROOT / "codex-feed" / "ROSTER.yaml")
        for seat in ("Wire", "Ledger", "Chain", "Odds", "Pulse", "Shadow",
                     "Grok", "Rails", "CoS", "Codex", "Jev"):
            self.assertIsNotNone(roster.model_for(seat), f"{seat} unassigned")
        self.assertEqual(roster.model_for("Jev"), "any")
        self.assertEqual(roster.model_for("Grok"), "grok")


class IndependenceTests(unittest.TestCase):
    def test_a_challenge_from_the_proposers_model_is_self_review(self):
        """The rule with teeth."""
        roster = build_roster()
        ticket = build_ticket(id="T-001", source_seats=["Chain"])   # claude
        challenge = build_challenge(model="claude")
        self.assertFalse(roster.is_independent(ticket, challenge))
        kept, dropped = roster.independent_challenges([ticket], {"T-001": challenge})
        self.assertEqual(kept, {})
        self.assertIn("self-review", dropped[0])

    def test_a_challenge_from_a_different_model_counts(self):
        roster = build_roster()
        ticket = build_ticket(id="T-001", source_seats=["Chain"])
        challenge = build_challenge(model="gemini")
        self.assertTrue(roster.is_independent(ticket, challenge))

    def test_a_declared_ticket_model_overrides_the_seat_assignment(self):
        roster = build_roster()
        ticket = build_ticket(id="T-001", source_seats=["Chain"], model="gemini")
        self.assertFalse(roster.is_independent(ticket, build_challenge(model="gemini")))
        self.assertTrue(roster.is_independent(ticket, build_challenge(model="claude")))

    def test_an_undeclared_challenger_model_is_not_assumed_guilty(self):
        """The rule bites on what is declared, not on what is missing."""
        roster = build_roster()
        ticket = build_ticket(id="T-001", source_seats=["Chain"])
        self.assertTrue(roster.is_independent(ticket, build_challenge()))

    def test_the_rule_can_be_switched_off_in_the_roster(self):
        roster = build_roster(rules={"adversary_must_differ": False})
        ticket = build_ticket(id="T-001", source_seats=["Chain"])
        self.assertTrue(roster.is_independent(ticket, build_challenge(model="claude")))

    def test_a_multi_seat_ticket_is_owned_by_every_seats_model(self):
        roster = build_roster()
        ticket = build_ticket(id="T-001", source_seats=["Chain", "Wire"])  # claude + gemini
        self.assertFalse(roster.is_independent(ticket, build_challenge(model="gemini")))
        self.assertFalse(roster.is_independent(ticket, build_challenge(model="claude")))
        self.assertTrue(roster.is_independent(ticket, build_challenge(model="grok")))


class FilingTests(unittest.TestCase):
    def test_a_filing_naming_an_unknown_model_is_flagged(self):
        roster = build_roster()
        ticket = build_ticket(id="T-001", model="gpt")
        problems = check_filings(roster, [ticket], {})
        self.assertTrue(any("not in the roster" in p for p in problems))

    def test_a_seat_with_no_assignment_is_flagged(self):
        roster = build_roster()
        ticket = build_ticket(id="T-001", source_seats=["Odds"])
        problems = check_filings(roster, [ticket], {})
        self.assertTrue(any("no roster assignment" in p for p in problems))


class ScoreByModelTests(unittest.TestCase):
    def test_seats_sharing_a_model_collapse_into_one_row(self):
        outcomes = [
            Outcome("T1", NOW, True, result_r=1.0, seats=("Chain",)),
            Outcome("T2", NOW, True, result_r=-2.0, seats=("Odds",)),
            Outcome("T3", NOW, True, result_r=0.5, seats=("Grok",)),
        ]
        rows = score(outcomes, dimension="model",
                     seat_to_model={"Chain": "claude", "Odds": "claude", "Grok": "grok"})
        by_key = {r.key: r for r in rows}
        self.assertEqual(by_key["claude"].resolved, 2)
        self.assertAlmostEqual(by_key["claude"].total_r, -1.0)
        self.assertEqual(by_key["grok"].resolved, 1)

    def test_model_dimension_needs_the_roster(self):
        with self.assertRaises(ValueError):
            score([], dimension="model")


if __name__ == "__main__":
    unittest.main()
