import sys
import unittest
from pathlib import Path


HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "slice"))

from nonadditive_ops import entity_transitions, rate_mix_decomposition  # noqa: E402
from runtime import load_operator_registry  # noqa: E402
from typed_kernel import typed_distinct_decomp  # noqa: E402


class NonAdditiveExperimentTest(unittest.TestCase):
    def test_pure_mix_rate_change_is_not_a_within_segment_rate_effect(self):
        baseline = {"A": (90, 100), "B": (10, 100)}
        target = {"A": (45, 50), "B": (15, 150)}
        result = rate_mix_decomposition(baseline, target)
        self.assertAlmostEqual(result["baseline_rate"], 0.5)
        self.assertAlmostEqual(result["target_rate"], 0.3)
        self.assertAlmostEqual(result["total_change"], -0.2)
        self.assertAlmostEqual(result["rate_effect"], 0.0)
        self.assertAlmostEqual(result["mix_effect"], -0.2)
        self.assertTrue(result["checks"][0]["passed"])

    def test_period_distinct_deltas_hide_entry_exit_and_migration(self):
        before = [
            {"month": "2026-06", "customer_id": "a", "region": "A"},
            {"month": "2026-06", "customer_id": "b", "region": "A"},
            {"month": "2026-06", "customer_id": "c", "region": "B"},
            {"month": "2026-06", "customer_id": "d", "region": "B"},
        ]
        after = [
            {"month": "2026-07", "customer_id": "a", "region": "B"},
            {"month": "2026-07", "customer_id": "b", "region": "A"},
            {"month": "2026-07", "customer_id": "e", "region": "A"},
            {"month": "2026-07", "customer_id": "f", "region": "B"},
        ]
        metric = {"id": "active", "type": "distinct", "unit": "entity",
                  "properties": {"entity_type": "customer"},
                  "bindings": {"entity_id_field": "customer_id"}}
        dimensions = {"region": {"values": ["A", "B"], "mece": True,
                                  "entity_functional": {"customer": True}}}
        current = typed_distinct_decomp(
            metric, dimensions, before + after, "region", "2026-06", "2026-07",
            load_operator_registry())
        self.assertEqual(current["total_delta"], 0)
        self.assertTrue(all(row["delta"] == 0 for row in current["segments"]))

        transition = entity_transitions(before, after, "customer_id", "region")
        self.assertEqual(len(transition["entrants"]), 2)
        self.assertEqual(len(transition["exits"]), 2)
        self.assertEqual(transition["migrations"], [{"entity": "a", "from": "A", "to": "B"}])


if __name__ == "__main__":
    unittest.main()
