"""H1 challenge 2 — balance 시간 비가산과 distinct 차원 비가산."""
import copy
import json
import unittest
from pathlib import Path

from runtime import load_operator_registry
from typed_kernel import (typed_contrib_decomp, typed_distinct_decomp,
                          typed_distinct_level, typed_metric_level)


HERE = Path(__file__).parent


class GeneralityChallenge2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_operator_registry()
        cls.balance = json.loads((HERE / "challenges" / "inventory_balance.json").read_text())
        cls.distinct = json.loads((HERE / "challenges" / "active_customers.json").read_text())

    def test_balance_level_sums_across_warehouses_not_time(self):
        case = self.balance
        result = typed_metric_level(
            case["metric"], case["dimensions"], case["rows"], "2026-07", self.registry)
        self.assertEqual("result", result["status"])
        self.assertEqual(190, result["value"])

    def test_balance_change_is_period_end_to_period_end(self):
        case = self.balance
        result = typed_contrib_decomp(
            case["metric"], case["dimensions"], case["rows"], "warehouse",
            "2026-06", "2026-07", self.registry)
        self.assertEqual("result", result["status"])
        self.assertEqual(10, result["total_delta"])
        self.assertEqual({"서울": 20, "부산": -10},
                         {row["segment"]: row["delta"] for row in result["segments"]})

    def test_balance_rejects_sum_aggregation_rule(self):
        case = copy.deepcopy(self.balance)
        case["metric"]["properties"]["aggregation_rule"] = "sum"
        result = typed_metric_level(
            case["metric"], case["dimensions"], case["rows"], "2026-07", self.registry)
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("balance_time_semantics", result["violated"][0]["check"])

    def test_distinct_level_deduplicates_entities(self):
        case = self.distinct
        result = typed_distinct_level(
            case["metric"], case["dimensions"], case["rows"], "2026-07", self.registry)
        self.assertEqual("result", result["status"])
        self.assertEqual(5, result["value"])

    def test_distinct_decomp_requires_entity_functional_dimension(self):
        case = copy.deepcopy(self.distinct)
        case["dimensions"]["region"]["entity_functional"]["customer"] = False
        result = typed_distinct_decomp(
            case["metric"], case["dimensions"], case["rows"], "region",
            "2026-06", "2026-07", self.registry)
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("entity_functional_dimension", result["violated"][0]["check"])

    def test_distinct_runtime_detects_conflicting_entity_assignment(self):
        case = copy.deepcopy(self.distinct)
        case["rows"].append({"month": "2026-07", "customer_id": "c1", "region": "부산"})
        result = typed_distinct_decomp(
            case["metric"], case["dimensions"], case["rows"], "region",
            "2026-06", "2026-07", self.registry)
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("entity_functional_runtime", result["violated"][0]["check"])


if __name__ == "__main__":
    unittest.main()
