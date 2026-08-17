"""E-027 — 익명 단위 구간(unit_bucket) window와 Bosch 온보딩 게이트."""
import json
import unittest
from pathlib import Path

from analytical_ir import Slice
from catalog import load_metric_catalog
from demo import demo_question
from metric_evaluator import evaluate_metric

RATE_FIXTURE = Path(__file__).parent / "onboarded" / "bosch_failure_rate.json"


def bucket_metric(**overrides):
    metric = {
        "id": "t.rate", "name": "테스트율", "version": 1, "unit": "ratio",
        "type": "rate",
        "properties": {"additive_across_dims": False,
                       "additive_across_time": False,
                       "aggregation_rule": "denominator_weighted_mean",
                       "has_denominator": True, "sign": "nonnegative",
                       "available_windows": ["unit_bucket"],
                       "unit_bucket": {"width": 100}},
        "bindings": {"numerator_field": "f", "denominator_field": "n",
                     "time_field": "t"},
    }
    metric["properties"].update(overrides.pop("properties", {}))
    metric.update(overrides)
    return metric


ROWS = [{"t": 0, "f": 1, "n": 100}, {"t": 99.9, "f": 1, "n": 100},
        {"t": 100, "f": 3, "n": 100}]


class UnitBucketWindowTest(unittest.TestCase):
    def test_bucket_membership_is_floor_by_declared_width(self):
        envelope = evaluate_metric(bucket_metric(), {}, ROWS,
                                   Slice("U0000", "2026-08-06",
                                         window="unit_bucket"), "fixture")
        self.assertEqual("result", envelope.status)
        self.assertAlmostEqual(2 / 200, envelope.value["value"])

    def test_month_is_a_grain_refusal_when_source_has_no_calendar(self):
        envelope = evaluate_metric(bucket_metric(), {}, ROWS,
                                   Slice("2026-07", "2026-08-06"), "fixture")
        self.assertEqual("out_of_domain", envelope.status)
        self.assertEqual("window_registered", envelope.violated[0]["check"])
        self.assertIn("month is not registered",
                      envelope.violated[0]["detail"])

    def test_bucket_without_width_declaration_fails_closed(self):
        metric = bucket_metric()
        del metric["properties"]["unit_bucket"]
        envelope = evaluate_metric(metric, {}, ROWS,
                                   Slice("U0000", "2026-08-06",
                                         window="unit_bucket"), "fixture")
        self.assertEqual("out_of_domain", envelope.status)
        self.assertEqual("window_bucket_contract",
                         envelope.violated[-1]["check"])

    def test_calendar_metrics_still_refuse_unit_bucket(self):
        contexts = load_metric_catalog()
        outcome = demo_question("U0300 구간 매출은?", contexts)
        self.assertEqual("executed", outcome["stage"])
        self.assertEqual("out_of_domain", outcome["execution"]["status"])
        result = next(iter(outcome["execution"]["results"].values()))
        self.assertEqual("window_registered", result["violated"][0]["check"])


@unittest.skipUnless(RATE_FIXTURE.exists(), "bosch onboarding not built")
class BoschOnboardingIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()
        cls.rows = json.loads(RATE_FIXTURE.read_text())["rows"]

    def expected_rate(self, bucket):
        selected = [row for row in self.rows if row["t"] == bucket]
        return (sum(row["failed"] for row in selected)
                / sum(row["inspected"] for row in selected))

    def demo(self, question):
        return demo_question(question, contexts=self.contexts)

    def test_bucket_failure_rate_passes_all_gates(self):
        outcome = self.demo("U0300 구간 불량률은?")
        self.assertEqual("executed", outcome["stage"], outcome)
        selected = next(iter(outcome["execution"]["outputs"].values()))
        self.assertAlmostEqual(self.expected_rate(300), selected["value"])
        self.assertAlmostEqual(591 / 57110, selected["value"])

    def test_count_change_decomposes_across_paths(self):
        outcome = self.demo("U0300 대비 U0400 검사수가 왜 변했나?")
        self.assertEqual("executed", outcome["stage"], outcome)
        result = next(iter(outcome["execution"]["outputs"].values()))
        self.assertEqual(-11400, result["total"]["delta"])
        self.assertEqual(result["total"]["delta"],
                         sum(row["delta"] for row in result["segments"]))
        self.assertEqual("path", result["group_by"])

    def test_rate_change_refuses_under_contract(self):
        outcome = self.demo("U0300 대비 U0400 불량률이 왜 변했나?")
        self.assertEqual("intent", outcome["stage"])
        self.assertEqual("out_of_domain", outcome["compiled"]["status"])

    def test_month_question_is_refused_by_name(self):
        outcome = self.demo("3월 불량률은?")
        self.assertEqual("executed", outcome["stage"])
        self.assertEqual("out_of_domain", outcome["execution"]["status"])
        result = next(iter(outcome["execution"]["results"].values()))
        self.assertIn("month is not registered",
                      result["violated"][0]["detail"])

    def test_path_scoped_bucket_rate(self):
        outcome = self.demo("U0300 구간 L0-L3 불량률은?")
        self.assertEqual("executed", outcome["stage"], outcome)
        selected = next(iter(outcome["execution"]["outputs"].values()))
        scoped = [row for row in self.rows
                  if row["t"] == 300 and row["path"] == "L0-L3"]
        self.assertAlmostEqual(
            sum(row["failed"] for row in scoped)
            / sum(row["inspected"] for row in scoped),
            selected["value"])

    def test_existing_metrics_are_untouched(self):
        outcome = self.demo("7월 매출은?")
        selected = next(iter(outcome["execution"]["outputs"].values()))
        self.assertEqual(3860, selected["value"])


if __name__ == "__main__":
    unittest.main()
