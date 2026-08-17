"""Metric catalog와 typed core의 주 실행 경로 승격 테스트."""
import copy
import unittest

from catalog import load_metric_catalog
from engine import run_question
from runtime import ExecutionRuntime


class CatalogExecutionTest(unittest.TestCase):
    def test_catalog_exposes_three_closed_metrics(self):
        contexts = load_metric_catalog()
        got = [c["sem"]["metric"]["id"] for c in contexts]
        self.assertEqual(
            ["commerce.net_sales", "finance.operating_profit",
             "insurance.loss_ratio", "operations.inventory_on_hand",
             "growth.active_customers", "weather.precipitation",
             "quality.failure_rate", "quality.inspected_parts"], got)

    def test_operating_profit_runs_through_query_spec_and_runtime(self):
        envelope, bundle = run_question("7월 영업이익이 왜 줄었나?")
        self.assertEqual("spec", envelope["status"])
        result = bundle["results"]["contrib:business_unit"]
        self.assertEqual("result", result["status"])
        self.assertEqual({"before": 80, "after": 20, "delta": -60}, result["total"])
        self.assertEqual("contrib_decomp@v1", result["operator_ref"])
        self.assertEqual("finance.operating_profit@v1",
                         bundle["execution_record"]["provenance"]["metric_ref"])

    def test_loss_ratio_uses_registered_rate_level(self):
        envelope, bundle = run_question("7월 보험 손해율은?")
        self.assertEqual("spec", envelope["status"])
        result = bundle["results"]["level"]
        self.assertEqual("result", result["status"])
        self.assertAlmostEqual(0.66, result["value"])
        self.assertEqual("rate_level@v1", result["operator_ref"])

    def test_rate_change_does_not_fall_through_to_additive_decomposition(self):
        _, bundle = run_question("7월 손해율이 왜 변했나?")
        result = bundle["results"]["change"]
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual([], bundle["execution_record"]["calls"])

    def test_multiple_metrics_require_clarification(self):
        envelope, bundle = run_question("7월 매출과 손해율은?")
        self.assertIsNone(bundle)
        self.assertEqual("clarify", envelope["status"])
        self.assertEqual("복수 지표 지정", envelope["reason"])

    def test_runtime_rejects_metric_type_before_invoke(self):
        loss_metric = load_metric_catalog()[2]["sem"]["metric"]
        runtime = ExecutionRuntime(
            {"max_depth": 1, "max_segments": 3, "max_hypotheses": 0,
             "max_operator_calls": 1}, "explain_change", metric=loss_metric)
        invoked = []
        result = runtime.execute(
            "contrib_decomp:region", 1, 2,
            lambda _: invoked.append(True) or {"status": "result"})
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("metric_type_admissible", result["violated"][0]["check"])
        self.assertEqual([], invoked)

    def test_rate_sign_policy_is_enforced_in_integrated_path(self):
        contexts = load_metric_catalog()
        dirty = copy.deepcopy(contexts)
        dirty[2]["rows"][2]["incurred_claims_u"] = -72
        _, bundle = run_question("7월 보험 손해율은?", dirty)
        result = bundle["results"]["level"]
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("sign_policy", result["violated"][0]["check"])

    def test_duplicate_rate_binding_is_rejected_in_integrated_path(self):
        contexts = copy.deepcopy(load_metric_catalog())
        metric = contexts[2]["sem"]["metric"]
        metric["bindings"]["denominator_field"] = (
            metric["bindings"]["numerator_field"])
        _, bundle = run_question("7월 보험 손해율은?", contexts)
        result = bundle["results"]["level"]
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("field_binding_unique",
                         result["violated"][0]["check"])

    def test_inventory_balance_runs_as_period_end_change(self):
        _, bundle = run_question(
            "7월 말 재고는 얼마이고 6월 말 대비 어느 창고에서 증가했나?")
        result = bundle["results"]["contrib:warehouse"]
        self.assertEqual("result", result["status"])
        self.assertEqual({"before": 180, "after": 190, "delta": 10}, result["total"])
        self.assertEqual("개", result["unit"])

    def test_active_customer_distinct_runs_on_functional_dimension(self):
        _, bundle = run_question("7월 활성 고객 증가는 어느 지역에서 발생했나?")
        result = bundle["results"]["distinct:region"]
        self.assertEqual("result", result["status"])
        self.assertEqual({"before": 3, "after": 5, "delta": 2}, result["total"])
        self.assertEqual("distinct_decomp@v1", result["operator_ref"])


if __name__ == "__main__":
    unittest.main()
