"""E-026 — 실데이터 온보딩 킷과 그 발견들의 게이트."""
import json
import tempfile
import unittest
from pathlib import Path

from analytical_ir import Slice
from catalog import load_metric_catalog
from demo import demo_question
from metric_evaluator import evaluate_metric
from onboard import build_fixture, profile_csv, scaffold_contract

FIXTURE = Path(__file__).parent / "onboarded" / "seattle_weather.json"


class OnboardingKitTest(unittest.TestCase):
    def write_csv(self, text):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".csv", delete=False, dir=tempfile.gettempdir())
        handle.write(text)
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        return handle.name

    def test_profile_derives_kinds_dimensions_and_span(self):
        path = self.write_csv(
            "date,qty,grade\n2026-01-01,3,A\n2026-01-02,4.5,B\n2026-01-03,,A\n")
        profile = profile_csv(path)
        self.assertEqual("date", profile["columns"]["date"]["kind"])
        self.assertEqual("float", profile["columns"]["qty"]["kind"])
        self.assertEqual(["A", "B"], profile["columns"]["grade"]["values"])
        self.assertEqual(1, profile["columns"]["qty"]["nulls"])
        self.assertEqual("2026-01-03", profile["date_span"]["last"])

    def test_scaffold_refuses_high_cardinality_dimension(self):
        path = self.write_csv(
            "date,qty,note\n" + "\n".join(
                f"2026-01-{i:02d},1,text{i}" for i in range(1, 21)))
        profile = profile_csv(path)
        with self.assertRaises(ValueError):
            scaffold_contract(
                profile, metric_id="x.q", name="수량", aliases=["수량"],
                metric_type="amount", unit="개", value_field="qty",
                sign="nonnegative", dimension_fields=("note",))

    def test_fixture_numeric_type_is_decided_per_column(self):
        # 값 단위 int/float 혼합은 저장소 왕복과 hash를 어긋나게 한다(E-026).
        path = self.write_csv(
            "date,qty,grade\n2026-01-01,0,A\n2026-01-02,1.5,A\n")
        profile = profile_csv(path)
        sem = scaffold_contract(
            profile, metric_id="x.q", name="수량", aliases=["수량"],
            metric_type="amount", unit="개", value_field="qty",
            sign="nonnegative", date_field="date",
            dimension_fields=("grade",), mece_fields=("grade",))
        out = Path(tempfile.gettempdir()) / "e026-fixture.json"
        self.addCleanup(out.unlink)
        fixture = build_fixture(path, sem, out)
        self.assertEqual([0.0, 1.5],
                         [row["qty"] for row in fixture["rows"]])
        self.assertTrue(all(isinstance(row["qty"], float)
                            for row in fixture["rows"]))


class EmptySegmentSemanticsTest(unittest.TestCase):
    """커버된 기간의 빈 세그먼트: 가법은 0 관측, 시점값은 스냅샷 부재."""

    def evaluate(self, metric_type, rule, extra=None):
        metric = {
            "id": "t.m", "name": "테스트", "version": 1, "unit": "개",
            "type": metric_type,
            "properties": {"additive_across_dims": True,
                           "additive_across_time": metric_type != "balance",
                           "aggregation_rule": rule, "sign": "nonnegative",
                           **(extra or {})},
            "bindings": {"value_field": "qty"},
        }
        dimensions = {"grade": {"type": "nominal", "values": ["A", "B"],
                                "mece": True}}
        rows = [{"month": "2026-07", "grade": "A", "qty": 5}]
        return evaluate_metric(
            metric, dimensions, rows,
            Slice("2026-07", "2026-08-06", (("grade", ("B",)),)), "fixture")

    def test_additive_empty_segment_is_a_zero_observation(self):
        envelope = self.evaluate("amount", "sum")
        self.assertEqual("result", envelope.status)
        self.assertEqual(0, envelope.value["value"])

    def test_balance_empty_segment_stays_suspended(self):
        envelope = self.evaluate(
            "balance", "semi_additive:last",
            {"time_semantics": "period_end", "additive_across_time": False})
        self.assertEqual("suspended", envelope.status)
        self.assertIn("시점", envelope.pass_conditions)

    def test_uncovered_period_still_suspends(self):
        metric_slice = Slice("2026-09", "2026-08-06")
        envelope = evaluate_metric(
            {"id": "t.m", "name": "테스트", "version": 1, "unit": "개",
             "type": "amount",
             "properties": {"additive_across_dims": True,
                            "additive_across_time": True,
                            "aggregation_rule": "sum", "sign": "nonnegative"},
             "bindings": {"value_field": "qty"}},
            {}, [{"month": "2026-07", "qty": 5}], metric_slice, "fixture")
        self.assertEqual("suspended", envelope.status)


@unittest.skipUnless(FIXTURE.exists(), "seattle onboarding fixture not built")
class SeattleOnboardingIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()

    def demo(self, question):
        return demo_question(question, contexts=self.contexts)

    def test_real_monthly_level_passes_all_gates(self):
        outcome = self.demo("2015년 3월 강수량은?")
        self.assertEqual("executed", outcome["stage"], outcome)
        selected = next(iter(outcome["execution"]["outputs"].values()))
        self.assertAlmostEqual(113.5, selected["value"], places=6)
        self.assertEqual("mm", selected["unit"])

    def test_year_context_propagates_to_bare_month(self):
        outcome = self.demo("2015년 2월 대비 3월 강수량이 왜 변했나?")
        self.assertEqual("executed", outcome["stage"], outcome)
        self.assertEqual("result", outcome["execution"]["status"])
        result = next(iter(outcome["execution"]["outputs"].values()))
        self.assertAlmostEqual(-20.7, result["total"]["delta"], places=6)

    def test_snowless_month_segment_is_zero_not_missing(self):
        outcome = self.demo("2015년 2월 snow 강수량은?")
        self.assertEqual("executed", outcome["stage"], outcome)
        selected = next(iter(outcome["execution"]["outputs"].values()))
        self.assertEqual("result", selected.get("status", "result")
                         if "value" not in selected else "result")
        self.assertEqual(0, selected["value"])

    def test_partial_week_at_data_edge_suspends(self):
        outcome = self.demo("2015-W53 강수량은?")
        self.assertEqual("suspended", outcome["execution"]["status"])
        result = next(iter(outcome["execution"]["results"].values()))
        self.assertIn("4/7일", result["missing_inputs"][0])

    def test_existing_metrics_are_untouched_by_the_new_entry(self):
        outcome = self.demo("7월 매출은?")
        selected = next(iter(outcome["execution"]["outputs"].values()))
        self.assertEqual(3860, selected["value"])


if __name__ == "__main__":
    unittest.main()
