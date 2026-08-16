"""E-013 normalized metric evaluator shadow parity and counterexamples."""
import copy
import json
from pathlib import Path
import unittest

from analytical_ir import Slice
from catalog import load_metric_catalog
from engine import prepare_question, run_question
from metric_evaluator import (AggregationStrategyRegistry, SumStrategy,
                              evaluate_metric)
from runtime import load_operator_registry
from typed_kernel import (denominator_weighted_rate, typed_distinct_level,
                          typed_metric_level)


HERE = Path(__file__).parent


class MetricEvaluatorParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()
        cls.by_metric = {
            context["sem"]["metric"]["id"]: context
            for context in cls.contexts
        }
        cls.legacy_registry = load_operator_registry()

    def shadow_for_question(self, question):
        envelope, bundle = run_question(question, self.contexts)
        self.assertEqual("spec", envelope["status"], envelope)
        prepared, context = prepare_question(question, self.contexts)
        self.assertEqual(envelope["query_spec"], prepared["query_spec"])
        spec = envelope["query_spec"]
        provenance = bundle["execution_record"]["provenance"]
        result = evaluate_metric(
            context["sem"]["metric"], context["sem"]["dimensions"],
            context["rows"],
            Slice.from_scope(spec["focal_period"], spec["as_of"], spec["scope"]),
            provenance["semantic_model_ref"])
        return bundle["results"]["level"], result, context, provenance

    def evaluate_case(self, case, period="2026-07", scope=None,
                      semantic_model_ref="challenge-fixture"):
        return evaluate_metric(
            case["metric"], case["dimensions"], case["rows"],
            Slice.from_scope(period, "2026-08-06", scope or {}),
            semantic_model_ref)

    def test_current_and_normalized_level_parity_on_five_metrics_and_scope(self):
        cases = [
            ("7월 매출은?", 3860),
            ("7월 온라인 매출은?", 1580),
            ("7월 영업이익은?", 20),
            ("7월 보험 손해율은?", 0.66),
            ("7월 말 재고는?", 190),
            ("7월 활성 고객 수는?", 5),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                legacy, normalized, context, legacy_provenance = (
                    self.shadow_for_question(question))
                self.assertEqual("result", legacy["status"])
                self.assertEqual("result", normalized.status)
                legacy_value = legacy.get("value", legacy.get("value_u"))
                self.assertEqual(expected, legacy_value)
                self.assertEqual(legacy_value, normalized.value["value"])
                self.assertEqual(context["sem"]["metric"]["unit"],
                                 normalized.value["unit"])
                expected_scope = ({"channel": ["온라인"]}
                                  if "온라인" in question else {})
                self.assertEqual(
                    expected_scope,
                    normalized.value["slice"]["predicates"])
                self.assertEqual(legacy_provenance,
                                 normalized.value["provenance"])
                self.assertTrue(all(check["passed"]
                                    for check in normalized.value["checks"]))
                wire = normalized.to_dict()
                self.assertEqual("evaluate_metric@v1",
                                 wire["evidence"]["operator_ref"])
                self.assertEqual("data_confirmed",
                                 wire["evidence"]["label_ceiling"])
                self.assertTrue(legacy.get("label_ceiling"))
                self.assertTrue(all(
                    "데이터 확인" in ceiling
                    for ceiling in legacy["label_ceiling"].values()))
                json.dumps(wire, ensure_ascii=False, sort_keys=True)

    def test_normalized_carrier_exposes_strategy_specific_components(self):
        rate = self.shadow_for_question("7월 보험 손해율은?")[1]
        self.assertEqual(
            {"numerator": 132, "denominator": 200},
            rate.value["aggregation"]["components"])
        balance = self.shadow_for_question("7월 말 재고는?")[1]
        self.assertEqual(
            "period_end",
            balance.value["aggregation"]["expression"]["time_selection"])
        distinct = self.shadow_for_question("7월 활성 고객 수는?")[1]
        self.assertEqual(
            {"cardinality": 5},
            distinct.value["aggregation"]["components"])

    def test_count_metric_uses_same_sum_strategy_and_matches_legacy_kernel(self):
        case = json.loads((HERE / "challenges" / "order_count.json").read_text())
        legacy = typed_metric_level(
            case["metric"], case["dimensions"], case["rows"], "2026-07",
            self.legacy_registry)
        normalized = self.evaluate_case(case)
        self.assertEqual("result", legacy["status"])
        self.assertEqual(22, legacy["value"])
        self.assertEqual(legacy["value"], normalized.value["value"])
        self.assertEqual("sum", normalized.value["aggregation"]["rule"])
        self.assertEqual("count", case["metric"]["type"])

    def test_nominal_metric_type_is_not_an_execution_dispatch_axis(self):
        context = copy.deepcopy(self.by_metric["finance.operating_profit"])
        metric = context["sem"]["metric"]
        metric["type"] = "count"
        result = evaluate_metric(
            metric, context["sem"]["dimensions"], context["rows"],
            Slice("2026-07", "2026-08-06"), "fixture")
        self.assertEqual("result", result.status)
        self.assertEqual(20, result.value["value"])
        self.assertEqual("sum", result.value["aggregation"]["rule"])

    def test_duplicate_binding_is_rejected_by_candidate_and_live_typed_path(self):
        context = copy.deepcopy(self.by_metric["insurance.loss_ratio"])
        metric = context["sem"]["metric"]
        metric["bindings"]["denominator_field"] = (
            metric["bindings"]["numerator_field"])
        legacy = denominator_weighted_rate(
            metric, context["rows"], "2026-07", self.legacy_registry,
            dimensions=context["sem"]["dimensions"])
        normalized = evaluate_metric(
            metric, context["sem"]["dimensions"], context["rows"],
            Slice("2026-07", "2026-08-06"), "fixture")
        self.assertEqual("out_of_domain", legacy["status"])
        self.assertEqual("field_binding_unique", legacy["violated"][0]["check"])
        self.assertEqual("out_of_domain", normalized.status)
        self.assertEqual("field_binding_unique",
                         normalized.violated[0]["check"])

    def test_failure_check_parity_for_negative_rate_input(self):
        context = copy.deepcopy(self.by_metric["insurance.loss_ratio"])
        context["rows"][2]["incurred_claims_u"] = -72
        metric = context["sem"]["metric"]
        legacy = denominator_weighted_rate(
            metric, context["rows"], "2026-07", self.legacy_registry,
            dimensions=context["sem"]["dimensions"])
        normalized = evaluate_metric(
            metric, context["sem"]["dimensions"], context["rows"],
            Slice("2026-07", "2026-08-06"), "fixture")
        self.assertEqual("out_of_domain", legacy["status"])
        self.assertEqual(legacy["status"], normalized.status)
        self.assertEqual(legacy["violated"][0]["check"],
                         normalized.violated[0]["check"])

    def test_failure_check_parity_for_bad_balance_semantics(self):
        context = copy.deepcopy(self.by_metric["operations.inventory_on_hand"])
        metric = context["sem"]["metric"]
        metric["properties"]["aggregation_rule"] = "sum"
        legacy = typed_metric_level(
            metric, context["sem"]["dimensions"], context["rows"],
            "2026-07", self.legacy_registry)
        normalized = evaluate_metric(
            metric, context["sem"]["dimensions"], context["rows"],
            Slice("2026-07", "2026-08-06"), "fixture")
        self.assertEqual("out_of_domain", legacy["status"])
        self.assertEqual("balance_time_semantics",
                         legacy["violated"][0]["check"])
        self.assertEqual(legacy["status"], normalized.status)
        self.assertEqual("metric_type_aggregation_compatible",
                         normalized.violated[0]["check"])

    def test_null_distinct_entity_failure_matches_legacy(self):
        context = copy.deepcopy(self.by_metric["growth.active_customers"])
        context["rows"][4]["customer_id"] = None
        metric = context["sem"]["metric"]
        legacy = typed_distinct_level(
            metric, context["sem"]["dimensions"], context["rows"],
            "2026-07", self.legacy_registry)
        normalized = evaluate_metric(
            metric, context["sem"]["dimensions"], context["rows"],
            Slice("2026-07", "2026-08-06"), "fixture")
        self.assertEqual("out_of_domain", legacy["status"])
        self.assertEqual(legacy["status"], normalized.status)
        self.assertEqual("entity_id_present", normalized.violated[0]["check"])

    def test_zero_denominator_suspends_in_both_paths(self):
        context = copy.deepcopy(self.by_metric["insurance.loss_ratio"])
        for row in context["rows"]:
            if row["month"] == "2026-07":
                row["earned_premium_u"] = 0
        metric = context["sem"]["metric"]
        legacy = denominator_weighted_rate(
            metric, context["rows"], "2026-07", self.legacy_registry,
            dimensions=context["sem"]["dimensions"])
        normalized = evaluate_metric(
            metric, context["sem"]["dimensions"], context["rows"],
            Slice("2026-07", "2026-08-06"), "fixture")
        self.assertEqual("suspended", legacy["status"])
        self.assertEqual(legacy["status"], normalized.status)
        self.assertEqual(("nonzero denominator",), normalized.missing_inputs)

    def test_missing_bound_field_is_rejected_before_aggregation(self):
        context = copy.deepcopy(self.by_metric["finance.operating_profit"])
        del context["rows"][0]["profit_u"]
        result = evaluate_metric(
            context["sem"]["metric"], context["sem"]["dimensions"],
            context["rows"], Slice("2026-07", "2026-08-06"), "fixture")
        self.assertEqual("out_of_domain", result.status)
        self.assertEqual("field_binding", result.violated[0]["check"])

    def test_unknown_aggregation_rule_fails_closed(self):
        context = copy.deepcopy(self.by_metric["finance.operating_profit"])
        context["sem"]["metric"]["properties"]["aggregation_rule"] = "median"
        result = evaluate_metric(
            context["sem"]["metric"], context["sem"]["dimensions"],
            context["rows"], Slice("2026-07", "2026-08-06"), "fixture")
        self.assertEqual("out_of_domain", result.status)
        self.assertEqual("aggregation_strategy_registered",
                         result.violated[0]["check"])

    def test_unknown_scope_and_missing_period_are_sum_type_failures(self):
        context = self.by_metric["finance.operating_profit"]
        unknown_scope = evaluate_metric(
            context["sem"]["metric"], context["sem"]["dimensions"],
            context["rows"],
            Slice.from_scope("2026-07", "2026-08-06", {"planet": "mars"}),
            "fixture")
        self.assertEqual("out_of_domain", unknown_scope.status)
        self.assertEqual("scope_declared", unknown_scope.violated[0]["check"])
        missing = evaluate_metric(
            context["sem"]["metric"], context["sem"]["dimensions"],
            context["rows"], Slice("2026-05", "2026-08-06"), "fixture")
        self.assertEqual("suspended", missing.status)

    def test_duplicate_slice_predicate_cannot_be_silently_overwritten(self):
        context = self.by_metric["finance.operating_profit"]
        result = evaluate_metric(
            context["sem"]["metric"], context["sem"]["dimensions"],
            context["rows"],
            Slice("2026-07", "2026-08-06", (
                ("business_unit", ("리테일",)),
                ("business_unit", ("기업",)),
            )), "fixture")
        self.assertEqual("out_of_domain", result.status)
        self.assertEqual("slice_valid", result.violated[0]["check"])

    def test_registry_is_closed_and_rejects_duplicate_rules(self):
        registry = AggregationStrategyRegistry(strategies=(SumStrategy(),))
        self.assertEqual(("sum",), registry.rules)
        with self.assertRaises(ValueError):
            registry.register(SumStrategy())

    def test_metric_scalar_schema_is_present(self):
        schema = json.loads(
            (HERE.parent / "schemas" / "metric-scalar-v1.schema.json").read_text())
        self.assertEqual("groot-cal/metric-scalar-v1", schema["$id"])
        self.assertIn("aggregation", schema["required"])


if __name__ == "__main__":
    unittest.main()
