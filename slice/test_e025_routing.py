"""E-025 — rank·drilldown 시연 라우팅 게이트."""
import dataclasses
import unittest

from catalog import load_metric_catalog
from demo import ROUTED_OPERATORS, demo_question
from engine import run_question
from shadow_executor import execute_shadow_plan
from shadow_intent import compile_shadow_intent


class E025RankDrilldownRoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()

    def test_rank_executes_and_matches_legacy_contribution_order(self):
        outcome = demo_question("7월 매출 감소 상위 3개 제품군만 보여줘",
                                self.contexts)
        self.assertEqual("executed", outcome["stage"], outcome)
        ranked = next(iter(outcome["execution"]["outputs"].values()))
        self.assertEqual("RankedSelection", ranked["output_type"])
        _, legacy = run_question("7월 매출이 왜 변했나?", self.contexts)
        expected = [row["segment"] for row in
                    legacy["results"]["contrib:category"]["segments"][:3]]
        self.assertEqual(expected,
                         [row["segment"] for row in ranked["segments"]])

    def test_drilldown_executes_with_parent_scope_and_kernel_parity(self):
        outcome = demo_question(
            "가장 큰 매출 하락 제품군을 찾고 그 안에서 고객 유형별로 다시 분해해줘",
            self.contexts)
        self.assertEqual("executed", outcome["stage"], outcome)
        result = next(iter(outcome["execution"]["outputs"].values()))
        self.assertEqual({"category": "가전"}, result["parent_scope"])
        from kernel import contrib_decomp
        context = next(c for c in self.contexts
                       if c["sem"]["metric"]["id"] == "commerce.net_sales")
        current = contrib_decomp(context["sem"], context["rows"],
                                 "customer_type", "2026-06", "2026-07",
                                 {"calls": []}, within={"category": "가전"})
        self.assertEqual(current["total"]["delta_u"], result["total"]["delta"])
        self.assertEqual(
            {row["segment"]: row["delta_u"] for row in current["segments"]},
            {row["segment"]: row["delta"] for row in result["segments"]})

    def test_drilldown_child_evaluations_are_budget_accounted(self):
        compiled = compile_shadow_intent(
            "가장 큰 매출 하락 제품군을 찾고 그 안에서 고객 유형별로 다시 분해해줘",
            contexts=self.contexts)
        executed = execute_shadow_plan(compiled["plan"], contexts=self.contexts)
        record = executed["execution_record"]
        top_level = len(compiled["plan"].calls)
        self.assertEqual(top_level + 2, record["budget"]["operator_calls"])
        child_ids = [row["call_id"] for row in record["calls"]
                     if "." in row["call_id"]]
        self.assertEqual(2, len(child_ids))
        # 자식 평가가 예산을 넘으면 전체가 budget_exhausted로 닫힌다.
        tight = dataclasses.replace(
            compiled["plan"],
            limits={**compiled["plan"].limits,
                    "max_operator_calls": top_level})
        starved = execute_shadow_plan(tight, contexts=self.contexts)
        self.assertEqual("budget_exhausted", starved["status"])

    def test_invalid_region_drilldown_still_fails_closed(self):
        outcome = demo_question(
            "가장 큰 매출 하락 제품군을 찾고 그 안에서 지역별로 다시 분해해줘",
            self.contexts)
        self.assertEqual("executed", outcome["stage"])
        self.assertEqual("out_of_domain", outcome["execution"]["status"])

    def test_plan_gap_and_alignment_remain_unrouted(self):
        self.assertNotIn("plan_gap@v1", ROUTED_OPERATORS)
        self.assertNotIn("align_metrics@v1", ROUTED_OPERATORS)
        outcome = demo_question("2026-06-25 계획 대비 7월 매출 어때?",
                                self.contexts)
        self.assertEqual("route", outcome["stage"])


if __name__ == "__main__":
    unittest.main()
