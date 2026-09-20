"""Prober tests.

No network. The point of the prober is its classification — telling a missing
key apart from a geo-block apart from an outage — so that is what gets tested.
"""

from __future__ import annotations

import unittest
import urllib.error
from unittest import mock

from desk.loader import ValidationError
from desk.sources import (
    DEGRADED,
    GEO_BLOCKED,
    NO_AUTH,
    OK,
    UNREACHABLE,
    Health,
    parse_sources,
    probe,
    resolve_chain,
)

DOC = {
    "sources": [
        {"id": "primary", "seat": "Chain", "kind": "funding_oi",
         "url": "https://example.invalid/a", "fallbacks": ["secondary"]},
        {"id": "secondary", "seat": "Chain", "kind": "funding_oi",
         "url": "https://example.invalid/b", "auth_env": "TEST_DESK_KEY",
         "fallbacks": ["tertiary"]},
        {"id": "tertiary", "seat": "Chain", "kind": "funding_oi",
         "url": "https://example.invalid/c"},
        {"id": "walled", "seat": "Chain", "kind": "funding_oi",
         "url": "https://example.invalid/d", "geo_risk": True},
    ]
}


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.invalid/x", code, "nope", {}, None)


class RegistryTests(unittest.TestCase):
    def test_parses(self):
        sources = parse_sources(DOC)
        self.assertEqual(len(sources), 4)
        self.assertEqual(sources[0].fallbacks, ("secondary",))

    def test_dangling_fallback_is_refused(self):
        bad = {"sources": [{"id": "a", "seat": "X", "kind": "price",
                            "url": "https://example.invalid", "fallbacks": ["nope"]}]}
        with self.assertRaises(ValidationError) as caught:
            parse_sources(bad)
        self.assertIn("unknown source", str(caught.exception))


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.sources = {s.id: s for s in parse_sources(DOC)}

    def test_unset_key_is_reported_before_any_request(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("TEST_DESK_KEY", None)
            with mock.patch("desk.sources.urllib.request.urlopen") as opener:
                health = probe(self.sources["secondary"])
        self.assertEqual(health.state, NO_AUTH)
        self.assertIn("TEST_DESK_KEY", health.detail)
        opener.assert_not_called()

    def test_rejected_credential_is_no_auth_not_an_outage(self):
        with mock.patch.dict("os.environ", {"TEST_DESK_KEY": "x"}):
            with mock.patch("desk.sources.urllib.request.urlopen", side_effect=_http_error(401)):
                health = probe(self.sources["secondary"])
        self.assertEqual(health.state, NO_AUTH)

    def test_451_is_a_geo_block_even_without_the_flag(self):
        with mock.patch("desk.sources.urllib.request.urlopen", side_effect=_http_error(451)):
            health = probe(self.sources["primary"])
        self.assertEqual(health.state, GEO_BLOCKED)

    def test_403_is_a_geo_block_only_for_a_flagged_venue(self):
        with mock.patch("desk.sources.urllib.request.urlopen", side_effect=_http_error(403)):
            self.assertEqual(probe(self.sources["walled"]).state, GEO_BLOCKED)
            self.assertEqual(probe(self.sources["primary"]).state, UNREACHABLE)

    def test_rate_limit_is_degraded_not_dead(self):
        with mock.patch("desk.sources.urllib.request.urlopen", side_effect=_http_error(429)):
            self.assertEqual(probe(self.sources["primary"]).state, DEGRADED)

    def test_expected_non_200_counts_as_ok(self):
        source = parse_sources({"sources": [
            {"id": "post_only", "seat": "Chain", "kind": "funding_oi",
             "url": "https://example.invalid/info", "expect_status": [200, 405]},
        ]})[0]
        with mock.patch("desk.sources.urllib.request.urlopen", side_effect=_http_error(405)):
            self.assertEqual(probe(source).state, OK)


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.sources = parse_sources(DOC)

    def test_walks_to_the_first_usable_source(self):
        health = [
            Health("primary", UNREACHABLE),
            Health("secondary", NO_AUTH),
            Health("tertiary", OK),
        ]
        self.assertEqual(resolve_chain("primary", self.sources, health), "tertiary")

    def test_returns_none_when_the_whole_chain_is_dark(self):
        health = [
            Health("primary", UNREACHABLE),
            Health("secondary", NO_AUTH),
            Health("tertiary", GEO_BLOCKED),
        ]
        self.assertIsNone(resolve_chain("primary", self.sources, health))

    def test_a_cycle_cannot_spin(self):
        sources = parse_sources({"sources": [
            {"id": "a", "seat": "X", "kind": "price", "url": "https://example.invalid/a",
             "fallbacks": ["b"]},
            {"id": "b", "seat": "X", "kind": "price", "url": "https://example.invalid/b",
             "fallbacks": ["a"]},
        ]})
        health = [Health("a", UNREACHABLE), Health("b", UNREACHABLE)]
        self.assertIsNone(resolve_chain("a", sources, health))

    def test_degraded_still_counts_as_usable(self):
        health = [Health("primary", DEGRADED)]
        self.assertEqual(resolve_chain("primary", self.sources, health), "primary")


if __name__ == "__main__":
    unittest.main()
