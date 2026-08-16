import unittest

from final_adversarial import (causal_counterfactual_contract,
                               deterministic_reweight,
                               quantile_additivity_counterexample)


class FinalAdversarialTest(unittest.TestCase):
    def test_deterministic_scenario_is_not_labeled_causal(self):
        result = deterministic_reweight(
            {"A": 0.9, "B": 0.1}, {"A": 0.5, "B": 0.5})
        self.assertEqual(result["value"], 0.5)
        self.assertFalse(result["causal"])

    def test_causal_counterfactual_suspends_without_identification(self):
        result = causal_counterfactual_contract(
            "service_level", {"supplier_delay": 0})
        self.assertEqual(result["status"], "suspended")
        self.assertEqual(
            result["missing_inputs"],
            ["causal_model_ref", "identification_contract"])
        self.assertEqual(result["prohibited_fallback"], "observed-row filtering")

    def test_quantile_change_cannot_use_additive_contribution_identity(self):
        result = quantile_additivity_counterexample(
            {"A": [0, 0, 0], "B": [10, 10, 10]},
            {"A": [1, 1, 1], "B": [10, 10, 10]})
        self.assertEqual(result["segment_delta_sum"], 1)
        self.assertEqual(result["total_delta"], 0.5)
        self.assertFalse(result["additive_identity_holds"])


if __name__ == "__main__":
    unittest.main()
