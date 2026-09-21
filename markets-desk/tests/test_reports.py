"""Seat reports, and the rule that talk cannot be sized."""

from __future__ import annotations

import unittest
from typing import Any

from desk.loader import ValidationError
from desk.report import (
    HARD_KINDS,
    SOFT_KINDS,
    has_hard_evidence,
    parse_report,
    seats_reporting,
)
from desk.risk import FAIL, PASS, stamp_book
from desk.ticket import Evidence
from tests.helpers import NOW, build_mode, build_ticket, hours_ago

HEADLINE = "Funding calm across BTC and ETH; positioning is not the story today"


def build_report(**overrides: Any):
    doc: dict[str, Any] = {
        "schema_version": 2,
        "seat": "Chain",
        "produced_at": "2026-09-21T06:30:00-07:00",
        "read": "clear",
        "headline": HEADLINE,
        "covers": ["BTC", "ETH"],
        "evidence": [
            {
                "key": "BTC_funding_apr",
                "kind": "funding_oi",
                "value": 0.1095,
                "source": "Hyperliquid /info",
                "as_of": "2026-09-21T06:25:00-07:00",
            }
        ],
    }
    doc.update(overrides)
    return parse_report(doc, where="test-report")


class ContractTests(unittest.TestCase):
    def _refuses(self, **overrides) -> str:
        with self.assertRaises(ValidationError) as caught:
            build_report(**overrides)
        return str(caught.exception)

    def test_a_status_word_is_not_a_read(self):
        self.assertIn("headline", self._refuses(headline="checked"))

    def test_a_clear_read_needs_evidence(self):
        """Silence and confidence are different things."""
        message = self._refuses(read="clear", evidence=[])
        self.assertIn("requires at least one piece of evidence", message)

    def test_no_read_must_say_why(self):
        message = self._refuses(read="no_read", evidence=[], unavailable=[], notes="")
        self.assertIn("must say why", message)

    def test_no_read_with_a_dark_source_is_accepted(self):
        report = build_report(read="no_read", evidence=[], unavailable=["coinglass (no key)"])
        self.assertFalse(report.has_read)
        self.assertIn("dark: coinglass (no key)", report.line())

    def test_mixed_read_is_allowed_without_evidence(self):
        report = build_report(read="mixed", evidence=[])
        self.assertTrue(report.has_read)

    def test_evidence_needs_a_value_and_a_dated_source(self):
        self.assertIn("value", self._refuses(evidence=[
            {"key": "x", "kind": "price", "source": "s", "as_of": "2026-09-21T06:00:00-07:00"}]))
        self.assertIn("as_of", self._refuses(evidence=[
            {"key": "x", "kind": "price", "value": 1, "source": "s"}]))

    def test_covers_lookup_is_case_insensitive(self):
        report = build_report()
        self.assertTrue(report.for_symbol("btc"))
        self.assertFalse(report.for_symbol("SOL"))

    def test_only_reads_satisfy_the_required_seat_gate(self):
        reports = {
            "Chain": build_report(),
            "Pulse": build_report(seat="Pulse", read="no_read", evidence=[],
                                  unavailable=["cboe_delayed_chain"]),
        }
        self.assertEqual(seats_reporting(reports), {"Chain"})


class CrowdingTests(unittest.TestCase):
    """The social seat's most valuable field, and its guard rails."""

    def test_a_crowding_call_is_recorded(self):
        report = build_report(crowding={"BTC": "differentiated", "ETH": "consensus"})
        self.assertEqual(report.crowding_for("btc"), "differentiated")
        self.assertEqual(report.crowding_for("ETH"), "consensus")
        self.assertIsNone(report.crowding_for("SOL"))

    def test_an_unknown_level_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            build_report(crowding={"BTC": "very loud"})
        self.assertIn("not one of", str(caught.exception))

    def test_rating_a_name_you_did_not_look_at_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            build_report(covers=["BTC"], crowding={"SOL": "crowded"})
        self.assertIn("assess only what you looked at", str(caught.exception))

    def test_excluded_sources_are_carried(self):
        report = build_report(excluded_sources=["@somepumper (paid promotion pattern)"])
        self.assertIn("somepumper", report.excluded_sources[0])

    def test_crowding_is_optional(self):
        self.assertEqual(build_report().crowding, {})


class EvidenceClassTests(unittest.TestCase):
    def test_the_two_classes_do_not_overlap(self):
        self.assertFalse(set(HARD_KINDS) & set(SOFT_KINDS))

    def test_hard_evidence_is_detected(self):
        hard = [Evidence("p", "price", 1, source="s", as_of=NOW)]
        soft = [Evidence("t", "social", "loud", source="X", as_of=NOW)]
        self.assertTrue(has_hard_evidence(hard))
        self.assertFalse(has_hard_evidence(soft))
        self.assertTrue(has_hard_evidence(soft + hard))

    def test_empty_evidence_is_not_hard(self):
        self.assertFalse(has_hard_evidence([]))


class SoftEvidenceRuleTests(unittest.TestCase):
    SOCIAL = [{"key": "mentions", "kind": "social", "value": "up a lot",
               "source": "X", "as_of": None}]

    def _social_ticket(self, **overrides):
        evidence = [{"key": "mentions", "kind": "social", "value": "up a lot",
                     "source": "X", "as_of": hours_ago(2)}]
        return build_ticket(evidence=evidence, **overrides)

    def test_talk_alone_cannot_be_sized(self):
        book = stamp_book([self._social_ticket(size_hint_pct=1.0, confidence=5)],
                          build_mode(), now=NOW)
        stamp = book.stamps[0]
        self.assertEqual(stamp.verdict, FAIL)
        self.assertEqual(stamp.allowed_pct, 0.0)
        self.assertEqual(stamp.binding_constraint, "soft_evidence_only")

    def test_a_ticket_asking_for_nothing_is_exempt(self):
        """A stub is not claiming anything yet."""
        book = stamp_book([self._social_ticket(size_hint_pct=0.0, confidence=1)],
                          build_mode(), now=NOW)
        self.assertNotEqual(book.stamps[0].binding_constraint, "soft_evidence_only")

    def test_one_hard_fact_unlocks_it(self):
        evidence = [
            {"key": "mentions", "kind": "social", "value": "up a lot",
             "source": "X", "as_of": hours_ago(2)},
            {"key": "spot", "kind": "price", "value": 81300,
             "source": "Kraken", "as_of": hours_ago(1)},
        ]
        book = stamp_book([build_ticket(evidence=evidence, size_hint_pct=1.0, confidence=5)],
                          build_mode(), now=NOW)
        self.assertEqual(book.stamps[0].verdict, PASS)
        self.assertAlmostEqual(book.stamps[0].allowed_pct, 1.0, places=2)

    def test_the_rule_fires_before_the_challenge_gate(self):
        """Soft-only is a refusal on its own merits, not something Jev must catch."""
        mode = build_mode(require_challenge=True)
        book = stamp_book([self._social_ticket(size_hint_pct=1.0, confidence=5)],
                          mode, now=NOW)
        self.assertEqual(book.stamps[0].binding_constraint, "soft_evidence_only")


class ShippedTemplateTests(unittest.TestCase):
    def test_the_report_template_satisfies_its_own_contract(self):
        from pathlib import Path

        from desk.loader import load_document

        path = Path(__file__).resolve().parent.parent / "codex-feed" / "REPORT_TEMPLATE.yaml"
        parse_report(load_document(path), where=str(path))


if __name__ == "__main__":
    unittest.main()
