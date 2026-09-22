"""Shadow's routine screen: a buyer who buys every year at this time is a calendar.

Cohen, Malloy and Pomorski split insiders by whether they traded in the same
calendar month in each of the prior three years. Routine trades are more than
half the universe and carry no information; the rest carry all of it. Before
this screen Shadow counted both toward a cluster.
"""

from __future__ import annotations

import unittest
from datetime import date

from desk.adapters.base import FetchResult, evidence, now_utc
from desk.adapters.edgar import ROUTINE_YEARS, cluster_read, is_routine

BUY = date(2026, 9, 15)


class RoutineTests(unittest.TestCase):
    def test_same_month_in_each_of_the_prior_three_years_is_routine(self):
        prior = [date(2025, 9, 3), date(2024, 9, 20), date(2023, 9, 11)]
        self.assertTrue(is_routine(BUY, prior))

    def test_two_prior_years_is_not_enough(self):
        prior = [date(2025, 9, 3), date(2024, 9, 20)]
        self.assertFalse(is_routine(BUY, prior))

    def test_a_gap_year_breaks_the_pattern(self):
        prior = [date(2025, 9, 3), date(2023, 9, 11), date(2022, 9, 1)]
        self.assertFalse(is_routine(BUY, prior))

    def test_the_wrong_month_does_not_count(self):
        prior = [date(2025, 8, 30), date(2024, 9, 20), date(2023, 9, 11)]
        self.assertFalse(is_routine(BUY, prior))

    def test_trades_on_or_after_the_buy_are_not_history(self):
        """A trade cannot make itself routine."""
        prior = [BUY, date(2025, 9, 3), date(2024, 9, 20), date(2023, 9, 11)]
        self.assertTrue(is_routine(BUY, prior))
        later_only = [date(2027, 9, 1), date(2028, 9, 1), date(2029, 9, 1)]
        self.assertFalse(is_routine(BUY, later_only))

    def test_no_history_is_not_routine(self):
        self.assertFalse(is_routine(BUY, []))

    def test_the_window_is_three_years(self):
        self.assertEqual(ROUTINE_YEARS, 3)


class ReadTests(unittest.TestCase):
    def _result(self, buyers: int, routine: int | None) -> FetchResult:
        items = [evidence("SBLK_insider_buyers", "filing", buyers,
                          source="test", as_of=now_utc())]
        if routine is not None:
            items.append(evidence("SBLK_routine_buyers", "filing", routine,
                                  source="test", as_of=now_utc()))
        return FetchResult("sec_submissions", ok=True, evidence=items)

    def test_an_unscreened_count_says_so(self):
        line = cluster_read(self._result(3, None), "SBLK")
        self.assertIn("3 distinct insiders", line)
        self.assertIn("not yet screened", line)

    def test_an_all_routine_cluster_is_called_a_calendar(self):
        line = cluster_read(self._result(3, 3), "SBLK")
        self.assertIn("A calendar, not a cluster", line)

    def test_routine_buyers_are_excluded_from_the_count(self):
        line = cluster_read(self._result(4, 2), "SBLK")
        self.assertIn("2 opportunistic insiders", line)
        self.assertIn("2 routine excluded", line)

    def test_one_survivor_is_one_opinion(self):
        line = cluster_read(self._result(3, 2), "SBLK")
        self.assertIn("one opinion, not a cluster", line)


if __name__ == "__main__":
    unittest.main()
