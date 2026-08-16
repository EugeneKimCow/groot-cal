import unittest
from datetime import date, timedelta

from temporal_contracts import (MissingTemporalData, TemporalError,
                                TemporalMetric, TimeWindow,
                                align_daily_actual_to_weekly_plan,
                                evaluate_snapshots, resolve_named_period)


class TemporalContractExperimentTest(unittest.TestCase):
    def setUp(self):
        self.window = TimeWindow(date(2026, 7, 1), date(2026, 7, 3))
        self.metric = TemporalMetric(
            "inventory@v1", "daily_snapshot", "sum",
            ("period_end", "average_daily_snapshot"))
        self.rows = [
            {"date": "2026-07-01", "warehouse": "A", "value": 100},
            {"date": "2026-07-02", "warehouse": "A", "value": 200},
            {"date": "2026-07-03", "warehouse": "A", "value": 300},
        ]

    def test_period_end_and_daily_average_are_distinct_estimands(self):
        ending = evaluate_snapshots(self.metric, self.rows, self.window, "period_end")
        average = evaluate_snapshots(
            self.metric, self.rows, self.window, "average_daily_snapshot")
        self.assertEqual(ending["value"], 300)
        self.assertEqual(average["value"], 200)

    def test_month_end_fixture_cannot_answer_daily_average(self):
        month_end_metric = TemporalMetric(
            "inventory@v1", "monthly_period_end", "sum", ("period_end",))
        with self.assertRaisesRegex(TemporalError, "not allowed"):
            evaluate_snapshots(
                month_end_metric, [self.rows[-1]], self.window,
                "average_daily_snapshot")

    def test_missing_daily_snapshot_suspends_average(self):
        with self.assertRaisesRegex(MissingTemporalData, "missing daily"):
            evaluate_snapshots(
                self.metric, [self.rows[0], self.rows[2]], self.window,
                "average_daily_snapshot")

    def test_daily_actual_aligns_to_week_only_with_complete_grain(self):
        actual = [{"date": str(self.window.start + timedelta(days=i)), "value": 10}
                  for i in range(3)]
        result = align_daily_actual_to_weekly_plan(
            actual, plan=28, window=self.window, rollup="sum")
        self.assertEqual(result["actual"], 30)
        self.assertEqual(result["gap"], 2)
        with self.assertRaisesRegex(MissingTemporalData, "incomplete"):
            align_daily_actual_to_weekly_plan(
                actual[:-1], plan=28, window=self.window, rollup="sum")

    def test_registered_fiscal_period_resolves_to_generic_window(self):
        calendar = {
            date(2026, 2, 1) + timedelta(days=i): "FY26-P01"
            for i in range(28)
        }
        window = resolve_named_period(calendar, "FY26-P01")
        self.assertEqual(window.start, date(2026, 2, 1))
        self.assertEqual(window.end, date(2026, 2, 28))
        self.assertEqual(window.calendar_ref, "registered_calendar")


if __name__ == "__main__":
    unittest.main()
