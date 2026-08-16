"""E-017 executable C4 shadow parity tests."""
import dataclasses
import json
from pathlib import Path
import unittest

from catalog import load_metric_catalog
from engine import run_question
from kernel import contrib_decomp
from runtime import load_operator_registry
from shadow_executor import execute_shadow_plan
from shadow_intent import compile_shadow_intent
from typed_kernel import typed_distinct_decomp


class ShadowExecutorParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()

    def shadow(self, question):
        compiled = compile_shadow_intent(question, contexts=self.contexts)
        self.assertEqual("result", compiled["status"], compiled)
        executed = execute_shadow_plan(compiled["plan"], contexts=self.contexts)
        return compiled, executed

    def test_metric_level_parity_across_all_five_metric_algebras(self):
        cases = (
            ("7월 매출은?", "level", 3860),
            ("7월 영업이익은?", "level", 20),
            ("7월 보험 손해율은?", "level", 0.66),
            ("7월 말 재고는?", "level", 190),
            ("7월 활성 고객 수는?", "level", 5),
        )
        for question, key, expected in cases:
            with self.subTest(question=question):
                _, legacy = run_question(question, self.contexts)
                compiled, shadow = self.shadow(question)
                self.assertEqual("result", shadow["status"], shadow)
                current = legacy["results"][key]
                current_value = current.get("value", current.get("value_u"))
                selected = next(iter(shadow["outputs"].values()))
                self.assertEqual(expected, current_value)
                self.assertEqual(current_value, selected["value"])
                self.assertEqual("data_confirmed", selected["label_ceiling"])
                self.assertTrue(compiled["plan"].metadata["shadow_only"])

    def test_current_sales_change_axes_have_numeric_and_segment_parity(self):
        question = "7월 매출이 왜 변했나?"
        _, legacy = run_question(question, self.contexts)
        compiled, shadow = self.shadow(question)
        self.assertEqual("result", shadow["status"], shadow)
        outputs = {result["group_by"]: result
                   for result in shadow["outputs"].values()}
        self.assertEqual({"channel", "category", "customer_type"}, set(outputs))
        for dimension, result in outputs.items():
            current = legacy["results"][f"contrib:{dimension}"]
            self.assertEqual(current["total"]["before_u"], result["total"]["before"])
            self.assertEqual(current["total"]["after_u"], result["total"]["after"])
            self.assertEqual(current["total"]["delta_u"], result["total"]["delta"])
            current_segments = {row["segment"]: row["delta_u"]
                                for row in current["segments"]}
            shadow_segments = {row["segment"]: row["delta"]
                               for row in result["segments"]}
            self.assertEqual(current_segments, shadow_segments)
        self.assertEqual(9, len(compiled["plan"].calls))

    def test_typed_amount_change_uses_same_contribution_runtime(self):
        question = "7월 영업이익이 왜 줄었나?"
        _, legacy = run_question(question, self.contexts)
        _, shadow = self.shadow(question)
        result = next(iter(shadow["outputs"].values()))
        current = legacy["results"]["contrib:business_unit"]
        self.assertEqual(-60, result["total"]["delta"])
        self.assertEqual(current["total"]["delta"], result["total"]["delta"])
        self.assertEqual(
            {row["segment"]: row["delta"] for row in current["segments"]},
            {row["segment"]: row["delta"] for row in result["segments"]})

    def test_period_end_balance_change_has_additive_dimension_parity(self):
        _, legacy = run_question(
            "7월 말 재고는 얼마이고 6월 말 대비 어느 창고에서 증가했나?",
            self.contexts)
        _, shadow = self.shadow("6월 대비 7월 재고 증가를 창고별로 보여줘")
        result = next(iter(shadow["outputs"].values()))
        current = legacy["results"]["contrib:warehouse"]
        self.assertEqual(10, result["total"]["delta"])
        self.assertEqual(current["total"]["delta"], result["total"]["delta"])
        self.assertEqual(
            {row["segment"]: row["delta"] for row in current["segments"]},
            {row["segment"]: row["delta"] for row in result["segments"]})

    def test_distinct_change_uses_explicit_set_transition_operator(self):
        question = "6월 대비 7월 활성 고객 증가를 지역별로 보여줘"
        compiled, shadow = self.shadow(question)
        self.assertEqual("set_transition@v1", compiled["plan"].calls[-1].operator_ref)
        result = next(iter(shadow["outputs"].values()))
        context = self.contexts[4]
        current = typed_distinct_decomp(
            context["sem"]["metric"], context["sem"]["dimensions"],
            context["rows"], "region", "2026-06", "2026-07",
            load_operator_registry())
        self.assertEqual(current["total"], result["total"])
        self.assertEqual(
            {row["segment"]: row["delta"] for row in current["segments"]},
            {row["segment"]: row["delta"] for row in result["segments"]})
        self.assertEqual(["c4", "c5"], result["transitions"]["entrants"])
        self.assertEqual([], result["transitions"]["exits"])

    def test_rate_change_remains_an_explicit_compiler_refusal(self):
        result = compile_shadow_intent("7월 손해율이 왜 변했나?", self.contexts)
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("material_clause_supported",
                         result["violated"][0]["check"])
        self.assertIn("rate-change", result["violated"][0]["detail"])

    def test_plan_gap_matches_current_numeric_segments_and_pinned_vintage(self):
        question = "2026-06-25 계획 대비 7월 매출 어때?"
        _, legacy = run_question(question, self.contexts)
        compiled, shadow = self.shadow(question)
        result = next(iter(shadow["outputs"].values()))
        current = legacy["results"]["plan_gap"]
        self.assertEqual("compare_plan", compiled["plan"].metadata["operation_family"])
        self.assertEqual("2026-06-25", result["scenario_ref"])
        self.assertEqual(current["total"]["plan_u"], result["total"]["plan"])
        self.assertEqual(current["total"]["actual_u"], result["total"]["actual"])
        self.assertEqual(current["total"]["gap_u"], result["total"]["delta"])
        self.assertEqual(
            {row["channel"]: row["gap_u"] for row in current["rows"]},
            {row["segment"]: row["delta"] for row in result["segments"]})

    def test_ranked_product_result_matches_current_contribution_order(self):
        question = "7월 매출 감소 상위 3개 제품군만 보여줘"
        _, legacy = run_question(question, self.contexts)
        _, shadow = self.shadow(question)
        ranked = next(iter(shadow["outputs"].values()))
        expected = [row["segment"] for row in
                    legacy["results"]["contrib:category"]["segments"][:3]]
        self.assertEqual(expected, [row["segment"] for row in ranked["segments"]])
        self.assertEqual(3, len(ranked["segments"]))

    def test_explicit_nested_drilldown_matches_current_kernel(self):
        question = ("가장 큰 매출 하락 제품군을 찾고 그 안에서 "
                    "고객 유형별로 다시 분해해줘")
        _, shadow = self.shadow(question)
        result = next(iter(shadow["outputs"].values()))
        self.assertEqual({"category": "가전"}, result["parent_scope"])
        context = self.contexts[0]
        record = {"calls": []}
        current = contrib_decomp(
            context["sem"], context["rows"], "customer_type",
            "2026-06", "2026-07", record, within={"category": "가전"})
        self.assertEqual(current["total"]["delta_u"], result["total"]["delta"])
        self.assertEqual(
            {row["segment"]: row["delta_u"] for row in current["segments"]},
            {row["segment"]: row["delta"] for row in result["segments"]})

    def test_semantically_invalid_region_drilldown_fails_closed(self):
        question = ("가장 큰 매출 하락 제품군을 찾고 그 안에서 "
                    "지역별로 다시 분해해줘")
        compiled = compile_shadow_intent(question, contexts=self.contexts)
        self.assertEqual("result", compiled["status"])
        shadow = execute_shadow_plan(compiled["plan"], contexts=self.contexts)
        self.assertEqual("out_of_domain", shadow["status"])
        failure = shadow["results"]["n092"]
        self.assertEqual("scope_declared", failure["violated"][0]["check"])

    def test_missing_period_preserves_normalized_suspension(self):
        compiled = compile_shadow_intent("2025년 7월 매출은?", self.contexts)
        shadow = execute_shadow_plan(compiled["plan"], contexts=self.contexts)
        result = shadow["results"][compiled["plan"].calls[0].call_id]
        self.assertEqual("suspended", result["status"])
        self.assertIn("missing_inputs", result)
        self.assertEqual("suspended", shadow["status"])

    def test_budget_is_checked_before_excess_call_executes(self):
        compiled = compile_shadow_intent("7월 매출이 왜 변했나?", self.contexts)
        limited = dataclasses.replace(
            compiled["plan"], limits={**compiled["plan"].limits,
                                      "max_operator_calls": 2})
        shadow = execute_shadow_plan(limited, contexts=self.contexts)
        self.assertEqual("budget_exhausted", shadow["status"])
        self.assertEqual("budget_exhausted", shadow["results"]["n0101c"]["status"])
        self.assertEqual(2, shadow["execution_record"]["budget"]["operator_calls"])

    def test_execution_record_has_plan_identity_calls_budget_and_provenance(self):
        compiled, shadow = self.shadow("7월 오프라인 매출 감소를 지역별로 보여줘")
        record = shadow["execution_record"]
        self.assertEqual(compiled["plan_hash"], record["plan_hash"])
        self.assertEqual(len(compiled["plan"].calls), len(record["calls"]))
        self.assertTrue(record["provenance"])
        self.assertLessEqual(record["budget"]["operator_calls"],
                             record["budget"]["max_operator_calls"])
        self.assertLessEqual(record["budget"]["segments_examined"],
                             record["budget"]["max_segments"])
        self.assertTrue(all(row["operator_ref"].endswith("@v1")
                            for row in record["calls"]))

    def test_enforced_semantic_corpus_has_normalized_shadow_parity_10_of_10(self):
        path = Path(__file__).parent.parent / "eval" / "semantic-layer-v1" / "cases.json"
        cases = json.loads(path.read_text())
        expected_values = {
            "scope-online-change": -220,
            "plan-vintage-pinned": -390,
            "plan-scope-online": -320,
            "level-scope-online": 1580,
            "scope-category-change": -200,
        }
        for case in cases:
            with self.subTest(case=case["id"]):
                compiled = compile_shadow_intent(case["question"], self.contexts)
                envelope_status = case["expect"]["envelope_status"]
                if envelope_status in {"clarify", "x1"}:
                    self.assertEqual("clarify", compiled["status"], compiled)
                    continue
                self.assertEqual("result", compiled["status"], compiled)
                shadow = execute_shadow_plan(compiled["plan"], self.contexts)
                expected_status = case["expect"]["result_status"]
                self.assertEqual(expected_status, shadow["status"], shadow)
                if case["id"] in expected_values:
                    values = []
                    for output in shadow["outputs"].values():
                        if output.get("total"):
                            values.append(output["total"]["delta"])
                        else:
                            values.append(output.get("value"))
                    self.assertIn(expected_values[case["id"]], values)

    def test_default_route_preserves_legacy_execution(self):
        # E-018 이후 C4 실행은 명시적 selector 뒤에만 있다. 기본 호출은 legacy
        # 결과 형태를 그대로 반환해야 한다.
        envelope, bundle = run_question("7월 매출은?", self.contexts)
        self.assertEqual("spec", envelope["status"])
        self.assertEqual(3860, bundle["results"]["level"]["value_u"])
        self.assertNotIn("envelope_version", bundle["results"]["level"])
        self.assertNotIn("route", bundle["execution_record"])


if __name__ == "__main__":
    unittest.main()
