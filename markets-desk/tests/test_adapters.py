"""Adapter tests. No network — every upstream is a fixture.

The fixtures are shaped from the documented responses. They are not proof the
live endpoints match; `python -m desk preflight` on the desk box is what
settles that. What these tests do pin is the parsing, the arithmetic, and the
refusals.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from unittest import mock

from desk.adapters import cboe, edgar, fred, hyperliquid, polymarket
from desk.adapters.base import FetchError

# --------------------------------------------------------------------------
# Polymarket
# --------------------------------------------------------------------------

GAMMA_MARKET = [{
    "slug": "clarity-act-signed-2026",
    "question": "Will the CLARITY Act be signed into law in 2026?",
    "description": "This market resolves YES if H.R.3633 is signed into law by 2026-12-31.",
    # Gamma hands these back as JSON-encoded strings.
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["0.0755", "0.9245"]',
    "clobTokenIds": '["111", "222"]',
    "volume": "48211.5",
    "endDate": "2026-12-31T23:59:59Z",
}]


class PolymarketTests(unittest.TestCase):
    def test_decodes_json_encoded_arrays(self):
        with mock.patch.object(polymarket, "fetch_json", return_value=GAMMA_MARKET):
            result = polymarket.fetch_market("clarity-act-signed-2026")
        self.assertTrue(result.ok)
        self.assertAlmostEqual(float(result.by_key("price_yes").value), 0.0755)
        self.assertAlmostEqual(float(result.by_key("price_no").value), 0.9245)

    def test_resolution_text_is_evidence_in_its_own_right(self):
        """Odds cannot rules-lawyer terms it never fetched."""
        with mock.patch.object(polymarket, "fetch_json", return_value=GAMMA_MARKET):
            result = polymarket.fetch_market("clarity-act-signed-2026")
        text = result.by_key("resolution_text")
        self.assertIsNotNone(text)
        self.assertIn("signed into law", text.value)
        self.assertEqual(text.kind, "legislative")

    def test_can_filter_to_one_outcome(self):
        with mock.patch.object(polymarket, "fetch_json", return_value=GAMMA_MARKET):
            result = polymarket.fetch_market("clarity-act-signed-2026", outcome="No")
        self.assertIsNone(result.by_key("price_yes"))
        self.assertIsNotNone(result.by_key("price_no"))

    def test_unknown_slug_is_a_clean_failure(self):
        with mock.patch.object(polymarket, "fetch_json", return_value=[]):
            result = polymarket.fetch_market("nope")
        self.assertFalse(result.ok)
        self.assertIn("no market matched", result.error)

    def test_transport_failure_does_not_raise(self):
        with mock.patch.object(polymarket, "fetch_json", side_effect=FetchError("boom")):
            result = polymarket.fetch_market("clarity-act-signed-2026")
        self.assertFalse(result.ok)
        self.assertEqual(result.evidence, [])

    def test_token_ids_decode(self):
        self.assertEqual(polymarket.token_ids(GAMMA_MARKET[0]), ["111", "222"])

    def test_book_reports_the_spread(self):
        book = {"bids": [{"price": "0.920", "size": "500"}, {"price": "0.915", "size": "100"}],
                "asks": [{"price": "0.930", "size": "400"}, {"price": "0.940", "size": "900"}]}
        with mock.patch.object(polymarket, "fetch_json", return_value=book):
            result = polymarket.fetch_book("222")
        self.assertAlmostEqual(float(result.by_key("best_bid").value), 0.920)
        self.assertAlmostEqual(float(result.by_key("best_ask").value), 0.930)
        self.assertAlmostEqual(float(result.by_key("spread").value), 0.010, places=4)

    def test_midpoint(self):
        with mock.patch.object(polymarket, "fetch_json", return_value={"mid": "0.925"}):
            result = polymarket.fetch_midpoint("222")
        self.assertAlmostEqual(float(result.by_key("clob_midpoint").value), 0.925)


# --------------------------------------------------------------------------
# Hyperliquid
# --------------------------------------------------------------------------

HL_PAYLOAD = [
    {"universe": [{"name": "BTC"}, {"name": "ETH"}, {"name": "SOL"}]},
    [
        {"markPx": "81300.0", "funding": "0.0000125", "openInterest": "12500.5"},
        {"markPx": "2650.0", "funding": "-0.0000200", "openInterest": "88000.0"},
        {"markPx": "140.0", "funding": "0.0001000", "openInterest": "500.0"},
    ],
]


class HyperliquidTests(unittest.TestCase):
    def test_reads_mark_funding_and_open_interest(self):
        with mock.patch.object(hyperliquid, "fetch_json", return_value=HL_PAYLOAD):
            result = hyperliquid.fetch_funding_oi(["BTC"])
        self.assertTrue(result.ok)
        self.assertAlmostEqual(float(result.by_key("BTC_mark").value), 81300.0)
        self.assertAlmostEqual(float(result.by_key("BTC_open_interest").value), 12500.5)

    def test_annualises_hourly_funding(self):
        """Hyperliquid funding is hourly; the venues Chain used to quote were 8h."""
        with mock.patch.object(hyperliquid, "fetch_json", return_value=HL_PAYLOAD):
            result = hyperliquid.fetch_funding_oi(["BTC"])
        hourly = float(result.by_key("BTC_funding_hourly").value)
        apr = float(result.by_key("BTC_funding_apr").value)
        self.assertAlmostEqual(apr, hourly * 24 * 365, places=6)
        self.assertAlmostEqual(apr, 0.1095, places=4)

    def test_only_requested_coins_come_back(self):
        with mock.patch.object(hyperliquid, "fetch_json", return_value=HL_PAYLOAD):
            result = hyperliquid.fetch_funding_oi(["BTC", "ETH"])
        keys = {e.key for e in result.evidence}
        self.assertIn("ETH_mark", keys)
        self.assertNotIn("SOL_mark", keys)

    def test_a_missing_coin_is_reported_not_silently_dropped(self):
        with mock.patch.object(hyperliquid, "fetch_json", return_value=HL_PAYLOAD):
            result = hyperliquid.fetch_funding_oi(["BTC", "DOGE"])
        self.assertTrue(result.ok)
        self.assertIn("DOGE", result.error)

    def test_crowding_read_is_three_way(self):
        with mock.patch.object(hyperliquid, "fetch_json", return_value=HL_PAYLOAD):
            btc = hyperliquid.fetch_funding_oi(["BTC"])
            eth = hyperliquid.fetch_funding_oi(["ETH"])
        self.assertIn("calm", hyperliquid.crowding_read(btc, "BTC"))
        self.assertIn("shorts paying", hyperliquid.crowding_read(eth, "ETH"))

    def test_malformed_payload_fails_cleanly(self):
        with mock.patch.object(hyperliquid, "fetch_json", return_value={"unexpected": True}):
            result = hyperliquid.fetch_funding_oi(["BTC"])
        self.assertFalse(result.ok)


# --------------------------------------------------------------------------
# CBOE / GEX
# --------------------------------------------------------------------------

def _chain(**overrides):
    payload = {
        "timestamp": "2026-09-21 13:45:00",
        "data": {
            "current_price": 6800.0,
            "options": [
                {"option": "SPXW260921C06800000", "gamma": 0.0010, "open_interest": 1000},
                {"option": "SPXW260921P06700000", "gamma": 0.0008, "open_interest": 500},
            ],
        },
    }
    payload.update(overrides)
    return payload


class CboeTests(unittest.TestCase):
    def test_parses_strike_and_type_from_the_osi_symbol(self):
        contract = cboe.parse_contract(
            {"option": "SPXW260921C06800000", "gamma": 0.001, "open_interest": 10}
        )
        self.assertEqual(contract.strike, 6800.0)
        self.assertTrue(contract.is_call)
        self.assertEqual(contract.expiry, date(2026, 9, 21))

    def test_explicit_fields_win_over_the_symbol(self):
        contract = cboe.parse_contract(
            {"option": "SPXW260921C06800000", "strike": 6825.0, "option_type": "P",
             "gamma": 0.001, "open_interest": 10}
        )
        self.assertEqual(contract.strike, 6825.0)
        self.assertFalse(contract.is_call)

    def test_a_row_missing_gamma_or_oi_is_skipped_not_zeroed(self):
        """A partial chain must not read as flat positioning."""
        self.assertIsNone(cboe.parse_contract({"option": "SPXW260921C06800000", "gamma": 0.001}))
        self.assertIsNone(cboe.parse_contract({"option": "SPXW260921C06800000", "open_interest": 5}))

    def test_puts_carry_the_opposite_sign(self):
        contracts = [
            cboe.Contract(strike=6800.0, is_call=True, gamma=0.001, open_interest=1000),
            cboe.Contract(strike=6700.0, is_call=False, gamma=0.0008, open_interest=500),
        ]
        buckets = cboe.gex_by_strike(contracts, spot=6800.0)
        self.assertGreater(buckets[6800.0], 0)
        self.assertLess(buckets[6700.0], 0)

    def test_gex_scales_with_the_square_of_spot(self):
        contracts = [cboe.Contract(strike=100.0, is_call=True, gamma=0.01, open_interest=10)]
        low = cboe.gex_by_strike(contracts, spot=100.0)[100.0]
        high = cboe.gex_by_strike(contracts, spot=200.0)[100.0]
        self.assertAlmostEqual(high / low, 4.0, places=6)

    def test_gamma_flip_interpolates_the_zero_crossing(self):
        buckets = {6700.0: -18_496_000.0, 6800.0: 27_744_000.0 + 18_496_000.0}
        # Cumulative: -18.496m at 6700, +27.744m at 6800 -> crosses 40% of the way.
        self.assertAlmostEqual(cboe.gamma_flip(buckets), 6740.0, places=1)

    def test_no_crossing_returns_none(self):
        self.assertIsNone(cboe.gamma_flip({6700.0: -1.0, 6800.0: -2.0}))
        self.assertIsNone(cboe.gamma_flip({}))

    def test_end_to_end_chain_read(self):
        with mock.patch.object(cboe, "fetch_json", return_value=_chain()):
            result = cboe.fetch_gex("_SPX")
        self.assertTrue(result.ok)
        self.assertEqual(result.by_key("call_wall").value, 6800.0)
        self.assertEqual(result.by_key("put_wall").value, 6700.0)
        self.assertEqual(result.by_key("contracts_used").value, 2)

    def test_as_of_comes_from_the_chain_not_the_wall_clock(self):
        """The whole reason this adapter exists."""
        with mock.patch.object(cboe, "fetch_json", return_value=_chain()):
            result = cboe.fetch_gex("_SPX")
        stamped = result.by_key("total_gex").as_of
        self.assertEqual(stamped, datetime(2026, 9, 21, 17, 45, tzinfo=timezone.utc))

    def test_an_undated_chain_is_refused(self):
        payload = _chain()
        payload.pop("timestamp")
        with mock.patch.object(cboe, "fetch_json", return_value=payload):
            result = cboe.fetch_gex("_SPX")
        self.assertFalse(result.ok)
        self.assertIn("no timestamp", result.error)

    def test_expiry_filter(self):
        with mock.patch.object(cboe, "fetch_json", return_value=_chain()):
            same = cboe.fetch_gex("_SPX", expiry=date(2026, 9, 21))
            other = cboe.fetch_gex("_SPX", expiry=date(2026, 10, 16))
        self.assertTrue(same.ok)
        self.assertFalse(other.ok)

    def test_positioning_read_names_the_regime(self):
        with mock.patch.object(cboe, "fetch_json", return_value=_chain()):
            result = cboe.fetch_gex("_SPX")
        self.assertIn("positive gamma", cboe.positioning_read(result))


# --------------------------------------------------------------------------
# EDGAR
# --------------------------------------------------------------------------

def _form4(owner: str, code: str, shares: str, price: str, is_director: str = "1") -> str:
    return f"""<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>{owner}</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>{is_director}</isDirector><isOfficer>0</isOfficer></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-09-17</value></transactionDate>
      <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>{shares}</value></transactionShares>
        <transactionPricePerShare><value>{price}</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


SUBMISSIONS_PAYLOAD = {
    "filings": {"recent": {
        "form": ["4", "4", "8-K", "4"],
        "filingDate": ["2026-09-18", "2026-09-17", "2026-09-16", "2026-09-17"],
        "accessionNumber": ["0001-26-000001", "0001-26-000002", "0001-26-000003", "0001-26-000004"],
        "primaryDocument": ["a.xml", "b.xml", "c.htm", "d.xml"],
    }}
}


class EdgarTests(unittest.TestCase):
    def test_parses_an_open_market_buy(self):
        trades = edgar.parse_form4(_form4("SMITH JANE", "P", "10000", "12.50"))
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].owner, "SMITH JANE")
        self.assertEqual(trades[0].code, "P")
        self.assertAlmostEqual(trades[0].notional, 125_000.0)
        self.assertTrue(trades[0].is_director)

    def test_malformed_xml_raises_rather_than_returning_nothing(self):
        with self.assertRaises(FetchError):
            edgar.parse_form4("<not xml")

    def test_only_form_4s_are_selected(self):
        with mock.patch.object(edgar, "fetch_json", return_value=SUBMISSIONS_PAYLOAD):
            filings = edgar.recent_filings(883902, since=date(2026, 9, 1))
        self.assertEqual(len(filings), 3)
        self.assertTrue(all(f.form == "4" for f in filings))

    def test_cluster_counts_distinct_owners_not_filings(self):
        """One director filing three times is one opinion."""
        docs = [_form4("SMITH JANE", "P", "1000", "10.0"),
                _form4("SMITH JANE", "P", "2000", "10.0"),
                _form4("SMITH JANE", "P", "3000", "10.0")]
        with mock.patch.object(edgar, "fetch_json", return_value=SUBMISSIONS_PAYLOAD), \
             mock.patch.object(edgar, "fetch_text", side_effect=docs):
            result = edgar.fetch_insider_cluster(883902, ticker="SBLK")
        self.assertEqual(result.by_key("SBLK_insider_buyers").value, 1)
        self.assertEqual(result.by_key("SBLK_form4_count").value, 3)
        self.assertIn("one opinion", edgar.cluster_read(result, "SBLK"))

    def test_a_real_cluster_is_counted(self):
        docs = [_form4("SMITH JANE", "P", "1000", "10.0"),
                _form4("DOE JOHN", "P", "2000", "10.0"),
                _form4("ROE RICHARD", "P", "3000", "10.0")]
        with mock.patch.object(edgar, "fetch_json", return_value=SUBMISSIONS_PAYLOAD), \
             mock.patch.object(edgar, "fetch_text", side_effect=docs):
            result = edgar.fetch_insider_cluster(883902, ticker="SBLK")
        self.assertEqual(result.by_key("SBLK_insider_buyers").value, 3)
        self.assertAlmostEqual(float(result.by_key("SBLK_insider_buy_notional").value), 60_000.0)
        self.assertIn("3 distinct insiders", edgar.cluster_read(result, "SBLK"))

    def test_sells_do_not_count_as_a_buy_cluster(self):
        docs = [_form4("SMITH JANE", "S", "1000", "10.0"),
                _form4("DOE JOHN", "S", "2000", "10.0"),
                _form4("ROE RICHARD", "A", "3000", "0.0")]
        with mock.patch.object(edgar, "fetch_json", return_value=SUBMISSIONS_PAYLOAD), \
             mock.patch.object(edgar, "fetch_text", side_effect=docs):
            result = edgar.fetch_insider_cluster(883902, ticker="SBLK")
        self.assertEqual(result.by_key("SBLK_insider_buyers").value, 0)
        self.assertEqual(result.by_key("SBLK_insider_sellers").value, 2)
        self.assertIn("not there", edgar.cluster_read(result, "SBLK"))

    def test_as_of_is_the_filing_date_not_now(self):
        docs = [_form4("A", "P", "1", "1.0")] * 3
        with mock.patch.object(edgar, "fetch_json", return_value=SUBMISSIONS_PAYLOAD), \
             mock.patch.object(edgar, "fetch_text", side_effect=docs):
            result = edgar.fetch_insider_cluster(883902, ticker="SBLK")
        self.assertEqual(result.by_key("SBLK_insider_buyers").as_of.date(), date(2026, 9, 18))

    def test_unreadable_filings_are_surfaced(self):
        with mock.patch.object(edgar, "fetch_json", return_value=SUBMISSIONS_PAYLOAD), \
             mock.patch.object(edgar, "fetch_text", side_effect=FetchError("403")):
            result = edgar.fetch_insider_cluster(883902, ticker="SBLK")
        self.assertIn("unreadable", result.error)


# --------------------------------------------------------------------------
# FRED
# --------------------------------------------------------------------------

class FredTests(unittest.TestCase):
    def test_missing_key_is_reported_before_any_request(self):
        with mock.patch.dict("os.environ", {"FRED_API_KEY": ""}):
            with mock.patch.object(fred, "fetch_json") as opener:
                result = fred.fetch_series("DGS10")
        self.assertFalse(result.ok)
        opener.assert_not_called()

    def test_reads_the_latest_observation_and_the_change(self):
        payload = {"observations": [{"date": "2026-09-18", "value": "4.21"},
                                    {"date": "2026-09-17", "value": "4.15"}]}
        with mock.patch.dict("os.environ", {"FRED_API_KEY": "k"}), \
             mock.patch.object(fred, "fetch_json", return_value=payload):
            result = fred.fetch_series("DGS10")
        self.assertAlmostEqual(float(result.by_key("DGS10").value), 4.21)
        self.assertAlmostEqual(float(result.by_key("DGS10_change").value), 0.06, places=4)

    def test_as_of_is_the_observation_date(self):
        payload = {"observations": [{"date": "2026-09-18", "value": "4.21"}]}
        with mock.patch.dict("os.environ", {"FRED_API_KEY": "k"}), \
             mock.patch.object(fred, "fetch_json", return_value=payload):
            result = fred.fetch_series("DGS10")
        self.assertEqual(result.by_key("DGS10").as_of.date(), date(2026, 9, 18))

    def test_a_missing_print_is_not_zero(self):
        """FRED writes '.' for no observation."""
        payload = {"observations": [{"date": "2026-09-18", "value": "."},
                                    {"date": "2026-09-17", "value": "4.15"}]}
        with mock.patch.dict("os.environ", {"FRED_API_KEY": "k"}), \
             mock.patch.object(fred, "fetch_json", return_value=payload):
            result = fred.fetch_series("DGS10")
        self.assertFalse(result.ok)

    def test_the_key_never_reaches_an_error_string(self):
        with mock.patch.dict("os.environ", {"FRED_API_KEY": "SUPERSECRET"}), \
             mock.patch.object(fred, "fetch_json",
                               side_effect=FetchError("...api_key=SUPERSECRET&file_type=json: HTTP 400")):
            result = fred.fetch_series("DGS10")
        self.assertNotIn("SUPERSECRET", result.error)
        self.assertIn("<redacted>", result.error)

    def test_shorthand_resolves_to_a_series_id(self):
        payload = {"observations": [{"date": "2026-09-18", "value": "0.55"}]}
        with mock.patch.dict("os.environ", {"FRED_API_KEY": "k"}), \
             mock.patch.object(fred, "fetch_json", return_value=payload):
            result = fred.fetch_named("2s10s")
        self.assertIsNotNone(result.by_key("T10Y2Y"))


if __name__ == "__main__":
    unittest.main()
