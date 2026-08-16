"""H1 vocabulary generality — signed amount와 rate 반증 실험."""
import copy
import json
import unittest
from pathlib import Path

from runtime import load_operator_registry
from typed_kernel import denominator_weighted_rate, typed_contrib_decomp


HERE = Path(__file__).parent


class GeneralityChallengeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_operator_registry()
        cls.profit = json.loads((HERE / "challenges" / "operating_profit.json").read_text())
        cls.loss = json.loads((HERE / "challenges" / "loss_ratio.json").read_text())

    def test_signed_amount_preserves_negative_values(self):
        case = self.profit
        result = typed_contrib_decomp(
            case["metric"], case["dimensions"], case["rows"], "business_unit",
            "2026-06", "2026-07", self.registry)
        self.assertEqual("result", result["status"])
        self.assertEqual(-60, result["total_delta"])
        got = {s["segment"]: s["delta"] for s in result["segments"]}
        self.assertEqual({"리테일": -30, "기업": -30}, got)

    def test_sign_policy_is_descriptor_driven_not_metric_name_driven(self):
        case = copy.deepcopy(self.profit)
        case["metric"]["properties"]["sign"] = "nonnegative"
        result = typed_contrib_decomp(
            case["metric"], case["dimensions"], case["rows"], "business_unit",
            "2026-06", "2026-07", self.registry)
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("sign_policy", result["violated"][0]["check"])

    def test_rate_uses_ratio_of_sums_not_mean_of_rates(self):
        case = self.loss
        result = denominator_weighted_rate(
            case["metric"], case["rows"], "2026-07", self.registry)
        self.assertEqual("result", result["status"])
        self.assertAlmostEqual(0.66, result["value"])
        naive = ((72 / 120) + (60 / 80)) / 2
        self.assertAlmostEqual(0.675, naive)
        self.assertNotEqual(naive, result["value"])

    def test_rate_cannot_use_additive_contribution_operator(self):
        case = self.loss
        result = typed_contrib_decomp(
            case["metric"], case["dimensions"], case["rows"], "region",
            "2026-06", "2026-07", self.registry)
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("metric_type_admissible", result["violated"][0]["check"])

    def test_rate_requires_denominator_weighted_rule(self):
        case = copy.deepcopy(self.loss)
        case["metric"]["properties"]["aggregation_rule"] = "sum"
        result = denominator_weighted_rate(
            case["metric"], case["rows"], "2026-07", self.registry)
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("rate_aggregation_rule", result["violated"][0]["check"])


if __name__ == "__main__":
    unittest.main()

