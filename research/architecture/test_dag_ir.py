import sys
import unittest
from pathlib import Path


HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "slice"))

from dag_ir import (Call, Plan, PlanError, execute_plan, greater_than,  # noqa: E402
                    select_max_abs)
from kernel import contrib_decomp, load_ledger, load_semantic  # noqa: E402


class DAGIRExperimentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sem = load_semantic()
        cls.ledger = load_ledger()

    def operators(self):
        def contribution(dim, baseline, target, within):
            return contrib_decomp(
                self.sem, self.ledger, dim, baseline, target,
                {"calls": []}, within=within)

        return {
            "contribution": contribution,
            "select_max_abs": select_max_abs,
            "greater_than": greater_than,
        }

    def test_requested_region_breakdown_is_explicit(self):
        plan = Plan(calls=(
            Call("region", "contribution", {
                "dim": "region", "baseline": "2026-06", "target": "2026-07",
                "within": {"channel": "오프라인"},
            }),
        ), outputs=("region",))
        outputs, _ = execute_plan(plan, self.operators())
        self.assertEqual(outputs["region"]["status"], "result")
        self.assertEqual(
            {row["segment"] for row in outputs["region"]["segments"]},
            {"수도권", "영남", "충청", "호남"})

    def test_nested_drilldown_uses_result_reference_not_new_analysis_operator(self):
        plan = Plan(calls=(
            Call("region", "contribution", {
                "dim": "region", "baseline": "2026-06", "target": "2026-07",
                "within": {"channel": "오프라인"},
            }),
            Call("top_region", "select_max_abs", {
                "rows": {"ref": "region", "path": "segments"},
                "field": "delta_u",
            }),
            Call("category", "contribution", {
                "dim": "category", "baseline": "2026-06", "target": "2026-07",
                "within": {
                    "channel": "오프라인",
                    "region": {"ref": "top_region", "path": "value"},
                },
            }),
        ), outputs=("region", "top_region", "category"))

        outputs, _ = execute_plan(plan, self.operators())
        selected_delta = outputs["top_region"]["row"]["delta_u"]
        nested_delta = outputs["category"]["total"]["delta_u"]
        self.assertEqual(nested_delta, selected_delta)
        self.assertEqual(outputs["category"]["status"], "result")

    def test_forward_reference_is_rejected(self):
        plan = Plan(calls=(
            Call("first", "select_max_abs", {
                "rows": {"ref": "later", "path": "segments"},
                "field": "delta_u",
            }),
        ), outputs=("first",))
        with self.assertRaisesRegex(PlanError, "forward reference"):
            execute_plan(plan, self.operators())

    def test_typed_guard_is_replayable_and_skips_false_branch(self):
        plan = Plan(calls=(
            Call("region", "contribution", {
                "dim": "region", "baseline": "2026-06", "target": "2026-07",
                "within": {"channel": "오프라인"},
            }),
            Call("top", "select_max_abs", {
                "rows": {"ref": "region", "path": "segments"},
                "field": "delta_u",
            }),
            Call("large", "greater_than", {
                "value": {"ref": "top", "path": "row.delta_u"},
                "threshold": 0,
            }),
            Call("category", "contribution", {
                "dim": "category", "baseline": "2026-06", "target": "2026-07",
                "within": {"channel": "오프라인"},
            }, when={"ref": "large", "path": "value"}),
        ), outputs=("large", "category"))
        outputs, _ = execute_plan(plan, self.operators())
        self.assertFalse(outputs["large"]["value"])
        self.assertEqual(outputs["category"]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
