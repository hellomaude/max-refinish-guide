"""What the ticket and mode contracts refuse.

Each of these was a way a bad ticket could reach Codex looking well-formed.
"""

from __future__ import annotations

import unittest

from desk.loader import ValidationError
from desk.mode import parse_mode
from desk.ticket import parse_ticket
from tests.helpers import build_mode, build_ticket


class TicketContractTests(unittest.TestCase):
    def _refuses(self, **overrides) -> str:
        with self.assertRaises(ValidationError) as caught:
            build_ticket(**overrides)
        return str(caught.exception)

    def test_thesis_must_say_something(self):
        self.assertIn("thesis", self._refuses(thesis="it goes up"))

    def test_an_idea_you_cannot_be_wrong_about_is_not_a_trade(self):
        self.assertIn("invalidation", self._refuses(invalidation="dunno"))

    def test_max_gate_cannot_be_waived(self):
        self.assertIn("max_gate", self._refuses(max_gate=False))

    def test_stop_on_the_wrong_side_of_entry_is_refused(self):
        self.assertIn("stop", self._refuses(direction="long", entry=100.0, stop=105.0))
        self.assertIn("stop", self._refuses(direction="short", entry=100.0, stop=95.0))

    def test_stop_equal_to_entry_implies_infinite_size(self):
        self.assertIn("infinite size", self._refuses(entry=100.0, stop=100.0))

    def test_undefined_risk_asking_for_size_needs_entry_and_stop(self):
        message = self._refuses(entry=None, stop=None, size_hint_pct=1.0)
        self.assertIn("entry/stop", message)

    def test_defined_risk_needs_no_stop(self):
        ticket = build_ticket(
            instrument={"kind": "prediction_market", "symbol": "clarity-act-signed-2026",
                        "venue": "polymarket", "outcome": "No"},
            defined_risk=True, entry=0.925, stop=None,
        )
        self.assertTrue(ticket.defined_risk)

    def test_prediction_market_must_name_its_outcome(self):
        message = self._refuses(
            instrument={"kind": "prediction_market", "symbol": "clarity-act-signed-2026",
                        "venue": "polymarket", "outcome": ""},
            defined_risk=True, entry=0.5, stop=None,
        )
        self.assertIn("outcome", message)

    def test_naive_timestamps_are_refused(self):
        message = self._refuses(created_at="2026-09-21T06:00:00")
        self.assertIn("timezone", message)

    def test_evidence_needs_a_value_and_a_date(self):
        self.assertIn("value", self._refuses(
            evidence=[{"key": "x", "kind": "price", "source": "s", "as_of": "2026-09-21T06:00:00-07:00"}]
        ))
        self.assertIn("as_of", self._refuses(
            evidence=[{"key": "x", "kind": "price", "value": 1, "source": "s"}]
        ))

    def test_confidence_is_bounded(self):
        self.assertIn("confidence", self._refuses(confidence=6))
        self.assertIn("confidence", self._refuses(confidence=0))

    def test_sources_cannot_be_empty(self):
        self.assertIn("sources", self._refuses(sources=[]))


class TicketArithmeticTests(unittest.TestCase):
    def test_notional_scales_with_the_stop_distance(self):
        ticket = build_ticket(entry=100.0, stop=95.0)  # 5 points of risk per unit
        # Risking $500 buys 100 units, i.e. $10,000 of notional.
        self.assertAlmostEqual(ticket.notional_for_risk(500.0), 10_000.0, places=2)

    def test_a_tighter_stop_buys_more_notional_for_the_same_risk(self):
        wide = build_ticket(entry=100.0, stop=90.0).notional_for_risk(500.0)
        tight = build_ticket(entry=100.0, stop=99.0).notional_for_risk(500.0)
        self.assertGreater(tight, wide)

    def test_defined_risk_notional_is_the_premium(self):
        ticket = build_ticket(
            instrument={"kind": "prediction_market", "symbol": "clarity-act-signed-2026",
                        "venue": "polymarket", "outcome": "No"},
            defined_risk=True, entry=0.925, stop=None,
        )
        # At 92.5c a $925 risk buys 1000 contracts, which is $925 of notional.
        self.assertAlmostEqual(ticket.notional_for_risk(925.0), 925.0, places=2)

    def test_missing_structure_returns_none_rather_than_guessing(self):
        ticket = build_ticket(entry=None, stop=None, size_hint_pct=0.0)
        self.assertIsNone(ticket.notional_for_risk(500.0))


class ModeContractTests(unittest.TestCase):
    def _refuses(self, **overrides) -> str:
        with self.assertRaises(ValidationError) as caught:
            build_mode(**overrides)
        return str(caught.exception)

    def test_conviction_ladder_must_be_complete(self):
        self.assertIn("missing level", self._refuses(conviction_ladder={1: 0.0, 2: 0.5}))

    def test_conviction_ladder_values_are_fractions(self):
        self.assertIn("fraction", self._refuses(
            conviction_ladder={1: 0.0, 2: 0.2, 3: 0.4, 4: 0.7, 5: 1.5}))

    def test_duplicate_theme_ids_are_refused(self):
        message = self._refuses(themes=[
            {"id": "dup", "cap_pct": 1.0, "members": ["A"]},
            {"id": "dup", "cap_pct": 2.0, "members": ["B"]},
        ])
        self.assertIn("duplicate theme", message)

    def test_backwards_event_window_is_refused(self):
        message = self._refuses(event_windows=[{
            "id": "bad",
            "starts_at": "2026-09-23T07:00:00-07:00",
            "ends_at": "2026-09-22T07:00:00-07:00",
            "overnight_risk_pct": 0.0,
            "max_pct_around_event": 1.0,
        }])
        self.assertIn("after starts_at", message)

    def test_broker_sheets_with_no_armed_venue_is_incoherent(self):
        message = self._refuses(
            execution="broker_sheets",
            venues={"equity": {"enabled": False, "live": False}},
        )
        self.assertIn("no venue is enabled", message)

    def test_theme_membership_supports_prefix_wildcards(self):
        mode = build_mode()
        self.assertEqual(mode.theme_for("clarity-act-signed-2026").id, "crypto_policy_beta")
        self.assertIsNone(mode.theme_for("clarity"))

    def test_theme_lookup_is_case_insensitive(self):
        self.assertEqual(build_mode().theme_for("coin").id, "crypto_policy_beta")

    def test_unknown_symbol_gets_the_default_theme_cap(self):
        mode = build_mode()
        self.assertIsNone(mode.theme_for("AAPL"))
        self.assertEqual(mode.cap_for_theme("something_new"), 1.5)


class ShippedConfigTests(unittest.TestCase):
    """The committed MODE.yaml has to satisfy its own contract."""

    def test_shipped_mode_parses_and_stays_conservative(self):
        from pathlib import Path
        from desk.mode import load_mode

        mode = load_mode(Path(__file__).resolve().parent.parent / "codex-feed" / "MODE.yaml")
        self.assertEqual(mode.execution, "research_packs_only")
        # No venue may be live while the desk is on research packs.
        self.assertTrue(all(not v.live for v in mode.venues.values()))
        # Every theme cap must fit inside the heat cap on its own.
        for theme in mode.themes:
            self.assertLessEqual(theme.cap_pct, mode.portfolio_heat_pct)

    def test_shipped_sources_resolve_their_fallbacks(self):
        from pathlib import Path
        from desk.sources import load_sources

        sources = load_sources(Path(__file__).resolve().parent.parent / "codex-feed" / "sources.yaml")
        self.assertTrue(sources)
        known = {s.id for s in sources}
        for source in sources:
            for fallback in source.fallbacks:
                self.assertIn(fallback, known)


if __name__ == "__main__":
    unittest.main()
