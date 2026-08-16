import copy
import json
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "slice"))

from aggregate_ir import (ContractError, EvaluateMetric, Slice,  # noqa: E402
                          evaluate_metric, scope)
from catalog import load_metric_catalog  # noqa: E402


class AggregateIRExperimentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = {
            context["sem"]["metric"]["id"]: context
            for context in load_metric_catalog()
        }

    def evaluate(self, metric_id, period="2026-07", **predicates):
        context = self.contexts[metric_id]
        metric = context["sem"]["metric"]
        node = EvaluateMetric(
            "n1", f"{metric['id']}@v{metric['version']}",
            Slice(period, scope(**predicates)))
        return evaluate_metric(node, metric, context["rows"])

    def test_one_node_matches_five_existing_metric_level_results(self):
        expected = {
            "commerce.net_sales": 3860,
            "finance.operating_profit": 20,
            "insurance.loss_ratio": 0.66,
            "operations.inventory_on_hand": 190,
            "growth.active_customers": 5,
        }
        for metric_id, value in expected.items():
            with self.subTest(metric_id=metric_id):
                self.assertEqual(self.evaluate(metric_id)["value"], value)

    def test_scope_is_a_node_input_not_an_operator_variant(self):
        result = self.evaluate("commerce.net_sales", channel="온라인")
        self.assertEqual(result["value"], 1580)
        self.assertEqual(result["slice"]["predicates"], [["channel", ["온라인"]]])

    def test_nominal_metric_type_is_not_used_for_dispatch(self):
        context = copy.deepcopy(self.contexts["finance.operating_profit"])
        del context["sem"]["metric"]["type"]
        metric = context["sem"]["metric"]
        node = EvaluateMetric("n1", "test@v1", Slice("2026-07"))
        self.assertEqual(evaluate_metric(node, metric, context["rows"])["value"], 20)

    def test_duplicate_binding_is_rejected(self):
        context = copy.deepcopy(self.contexts["insurance.loss_ratio"])
        metric = context["sem"]["metric"]
        metric["bindings"]["denominator_field"] = metric["bindings"]["numerator_field"]
        node = EvaluateMetric("n1", "test@v1", Slice("2026-07"))
        with self.assertRaisesRegex(ContractError, "duplicate"):
            evaluate_metric(node, metric, context["rows"])

    def test_unknown_algebra_is_rejected_instead_of_type_fallback(self):
        context = copy.deepcopy(self.contexts["finance.operating_profit"])
        metric = context["sem"]["metric"]
        metric["properties"]["aggregation_rule"] = "median"
        node = EvaluateMetric("n1", "test@v1", Slice("2026-07"))
        with self.assertRaisesRegex(ContractError, "unsupported aggregation"):
            evaluate_metric(node, metric, context["rows"])


if __name__ == "__main__":
    unittest.main()
