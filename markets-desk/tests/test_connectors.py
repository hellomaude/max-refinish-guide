"""The connector manifest: a seat's dependencies, asserted not advised."""

from __future__ import annotations

import unittest
from pathlib import Path

from desk.connectors import load_manifest, parse_manifest
from desk.loader import ValidationError
from desk.sources import load_sources

ROOT = Path(__file__).resolve().parent.parent


class ManifestTests(unittest.TestCase):
    def test_the_shipped_manifest_matches_the_registry(self):
        manifest = load_manifest(ROOT / "codex-feed" / "connectors.json")
        ids = [s.id for s in load_sources(ROOT / "codex-feed" / "sources.yaml")]
        self.assertEqual(manifest.check_registry(ids), [])

    def test_every_roster_seat_is_declared(self):
        from desk.roster import load_roster

        manifest = load_manifest(ROOT / "codex-feed" / "connectors.json")
        roster = load_roster(ROOT / "codex-feed" / "ROSTER.yaml")
        self.assertEqual(set(manifest.seats), set(roster.seats))

    def test_an_unknown_source_is_named(self):
        manifest = parse_manifest({"schema_version": 1, "seats": {"Odds": {"sources": ["nope"]}}})
        problems = manifest.check_registry(["polymarket_gamma"])
        self.assertEqual(len(problems), 1)
        self.assertIn("'nope'", problems[0])

    def test_a_dark_dependency_names_the_seat(self):
        manifest = parse_manifest({"schema_version": 1, "seats": {
            "Pulse": {"sources": ["cboe_delayed_chain"]},
            "Odds": {"sources": ["polymarket_gamma"]},
        }})
        dark = manifest.dark_seats({"cboe_delayed_chain": "unreachable", "polymarket_gamma": "ok"})
        self.assertEqual(len(dark), 1)
        self.assertTrue(dark[0].startswith("Pulse"))

    def test_degraded_still_counts_as_up(self):
        manifest = parse_manifest({"schema_version": 1, "seats": {"Odds": {"sources": ["x"]}}})
        self.assertEqual(manifest.dark_seats({"x": "degraded"}), [])

    def test_bad_shape_is_refused(self):
        with self.assertRaises(ValidationError):
            parse_manifest({"schema_version": 1, "seats": {"Odds": {"sources": "polymarket_gamma"}}})


if __name__ == "__main__":
    unittest.main()
