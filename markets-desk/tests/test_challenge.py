"""The adversary seat: contract, teeth, and whether it is earning its place."""

from __future__ import annotations

import unittest
from typing import Any

from desk.challenge import CONCEDE, CONTEST, KILL, load_challenges, parse_challenge, unchallenged
from desk.ledger import challenge_report
from desk.loader import ValidationError
from desk.risk import FAIL, PASS, PENDING, stamp_book
from tests.helpers import NOW, build_mode, build_ticket
from tests.test_ledger import outcome

COUNTER = (
    "The legislative read is right and the trade is still bad: you risk 92.5 to make 7.5, "
    "which needs better than 92.5% accuracy just to break even on a thin book."
)
MIND_CHANGE = "CLOB depth above $5k within two cents of the midpoint on the No side."


def build_challenge(**overrides: Any):
    doc: dict[str, Any] = {
        "schema_version": 2,
        "ticket_id": "T-001",
        "challenger": "Jev",
        "challenged_at": "2026-09-20T18:20:00-07:00",
        "verdict": CONTEST,
        "confidence_adjustment": -1,
        "strongest_counter": COUNTER,
        "what_would_change_my_mind": MIND_CHANGE,
    }
    doc.update(overrides)
    return parse_challenge(doc, where="test-challenge")


class ContractTests(unittest.TestCase):
    def _refuses(self, **overrides) -> str:
        with self.assertRaises(ValidationError) as caught:
            build_challenge(**overrides)
        return str(caught.exception)

    def test_registering_doubt_is_not_a_challenge(self):
        message = self._refuses(strongest_counter="I don't like it")
        self.assertIn("other side's best argument", message)

    def test_an_unsettleable_objection_is_refused(self):
        message = self._refuses(what_would_change_my_mind="nothing")
        self.assertIn("what_would_change_my_mind", message)

    def test_a_contest_must_cost_the_ticket_something(self):
        message = self._refuses(verdict=CONTEST, confidence_adjustment=0)
        self.assertIn("either move it or concede", message)

    def test_a_concede_cannot_also_dock_conviction(self):
        message = self._refuses(verdict=CONCEDE, confidence_adjustment=-1)
        self.assertIn("must be 0 on a concede", message)

    def test_the_adversary_cannot_add_conviction(self):
        """Letting it add would make it a second proposer."""
        message = self._refuses(confidence_adjustment=1)
        self.assertIn("confidence_adjustment", message)

    def test_a_concede_is_valid(self):
        held = build_challenge(verdict=CONCEDE, confidence_adjustment=0)
        self.assertFalse(held.contests)
        self.assertFalse(held.kills)

    def test_a_kill_contests(self):
        held = build_challenge(verdict=KILL, confidence_adjustment=-2)
        self.assertTrue(held.kills)
        self.assertTrue(held.contests)


class LoadingTests(unittest.TestCase):
    def test_the_shipped_challenge_loads(self):
        from pathlib import Path

        held = load_challenges(Path(__file__).resolve().parent.parent / "challenges")
        self.assertIn("WKND-002", held)
        self.assertEqual(held["WKND-002"].verdict, CONTEST)

    def test_missing_directory_is_empty_not_an_error(self):
        self.assertEqual(load_challenges("does-not-exist"), {})

    def test_unchallenged_lists_the_gap(self):
        held = {"A": build_challenge(ticket_id="A")}
        self.assertEqual(unchallenged(["A", "B", "C"], held), ["B", "C"])


class TeethTests(unittest.TestCase):
    def test_a_kill_fails_the_ticket_outright(self):
        mode = build_mode()
        held = {"T-001": build_challenge(verdict=KILL, confidence_adjustment=-2)}
        book = stamp_book([build_ticket(confidence=5)], mode, now=NOW, challenges=held)
        stamp = book.stamps[0]
        self.assertEqual(stamp.verdict, FAIL)
        self.assertEqual(stamp.allowed_pct, 0.0)
        self.assertEqual(stamp.binding_constraint, "challenge.kill")

    def test_a_contest_docks_conviction_and_therefore_size(self):
        mode = build_mode()
        ticket = build_ticket(confidence=5, size_hint_pct=1.0)
        alone = stamp_book([ticket], mode, now=NOW)
        contested = stamp_book([ticket], mode, now=NOW,
                               challenges={"T-001": build_challenge(confidence_adjustment=-1)})
        self.assertAlmostEqual(alone.stamps[0].allowed_pct, 1.0, places=2)
        self.assertAlmostEqual(contested.stamps[0].allowed_pct, 0.7, places=2)
        self.assertEqual(contested.stamps[0].challenge_verdict, CONTEST)

    def test_docking_cannot_fall_below_conviction_one(self):
        mode = build_mode()
        held = {"T-001": build_challenge(verdict=CONTEST, confidence_adjustment=-4)}
        book = stamp_book([build_ticket(confidence=2)], mode, now=NOW, challenges=held)
        self.assertEqual(book.stamps[0].effective_confidence, 1)
        self.assertEqual(book.stamps[0].allowed_pct, 0.0)

    def test_a_concede_leaves_size_untouched(self):
        mode = build_mode()
        ticket = build_ticket(confidence=4, size_hint_pct=1.0)
        alone = stamp_book([ticket], mode, now=NOW)
        conceded = stamp_book([ticket], mode, now=NOW, challenges={
            "T-001": build_challenge(verdict=CONCEDE, confidence_adjustment=0)})
        self.assertAlmostEqual(alone.stamps[0].allowed_pct, conceded.stamps[0].allowed_pct)

    def test_unchallenged_is_pending_when_the_desk_requires_a_challenge(self):
        mode = build_mode(require_challenge=True)
        book = stamp_book([build_ticket(confidence=5)], mode, now=NOW)
        stamp = book.stamps[0]
        self.assertEqual(stamp.verdict, PENDING)
        self.assertEqual(stamp.allowed_pct, 0.0)
        self.assertEqual(stamp.binding_constraint, "unchallenged")

    def test_unchallenged_passes_when_the_desk_does_not_require_one(self):
        mode = build_mode(require_challenge=False)
        book = stamp_book([build_ticket(confidence=5)], mode, now=NOW)
        self.assertEqual(book.stamps[0].verdict, PASS)

    def test_a_contested_ticket_also_loses_its_claim_on_a_shared_cap(self):
        """Docked conviction is the water-filling weight too, so it loses twice."""
        mode = build_mode()
        legs = [
            build_ticket(id="A", instrument={"symbol": "COIN"}, confidence=5, size_hint_pct=1.0),
            build_ticket(id="B", instrument={"symbol": "HOOD"}, confidence=5, size_hint_pct=1.0),
        ]
        held = {"B": build_challenge(ticket_id="B", confidence_adjustment=-1)}
        book = stamp_book(legs, mode, now=NOW, challenges=held)
        self.assertGreater(book.by_id("A").allowed_pct, book.by_id("B").allowed_pct)
        self.assertLessEqual(
            book.by_id("A").allowed_pct + book.by_id("B").allowed_pct, 1.5 + 1e-9
        )

    def test_the_shipped_book_is_docked_by_the_shipped_challenge(self):
        from pathlib import Path

        from desk.mode import load_mode
        from desk.ticket import load_tickets

        root = Path(__file__).resolve().parent.parent
        book = stamp_book(
            load_tickets(root / "tickets"),
            load_mode(root / "codex-feed" / "MODE.yaml"),
            now=NOW,
            challenges=load_challenges(root / "challenges"),
        )
        stamp = book.by_id("WKND-002")
        self.assertEqual(stamp.challenge_verdict, CONTEST)
        self.assertAlmostEqual(stamp.allowed_pct, 0.20, places=2)


class ScoringTests(unittest.TestCase):
    def test_thin_evidence_says_so(self):
        held = {"A": build_challenge(ticket_id="A")}
        report = " ".join(challenge_report([outcome("A", r=-1.0)], held))
        self.assertIn("too thin to judge", report)

    def test_earning_its_seat_when_objections_predict_losses(self):
        held = {f"C{i}": build_challenge(ticket_id=f"C{i}") for i in range(4)}
        outcomes = [outcome(f"C{i}", r=-1.0) for i in range(4)]
        outcomes += [outcome(f"K{i}", r=1.5) for i in range(4)]
        report = " ".join(challenge_report(outcomes, held))
        self.assertIn("earning its seat", report)

    def test_inverted_when_it_taxes_the_winners(self):
        held = {f"C{i}": build_challenge(ticket_id=f"C{i}") for i in range(4)}
        outcomes = [outcome(f"C{i}", r=2.0) for i in range(4)]
        outcomes += [outcome(f"K{i}", r=-0.5) for i in range(4)]
        report = " ".join(challenge_report(outcomes, held))
        self.assertIn("inverted", report)

    def test_no_separation_is_reported_as_a_cost(self):
        held = {f"C{i}": build_challenge(ticket_id=f"C{i}") for i in range(4)}
        outcomes = [outcome(f"C{i}", r=0.5) for i in range(4)]
        outcomes += [outcome(f"K{i}", r=0.5) for i in range(4)]
        report = " ".join(challenge_report(outcomes, held))
        self.assertIn("without buying information", report)

    def test_killed_tickets_are_flagged_as_unscoreable(self):
        held = {"A": build_challenge(ticket_id="A", verdict=KILL, confidence_adjustment=-2)}
        report = " ".join(challenge_report([outcome("A", taken=False)], held))
        self.assertIn("unscoreable", report)


if __name__ == "__main__":
    unittest.main()
