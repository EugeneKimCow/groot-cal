import unittest

from integrated_vertical_slice import (
    CallSpec, DeltaNode, ExplicitPlan, GenericPlan, GroupedMetricNode,
    PlanTypeError, Ref, ScalarMetricNode, comparison_metrics, compile_explicit,
    execute_explicit, execute_generic, explicit_cases, generic_cases)


class IntegratedVerticalSliceTest(unittest.TestCase):
    def test_c3_and_c4_have_result_and_trace_parity(self):
        for case_id, c4_plan in generic_cases().items():
            with self.subTest(case_id=case_id):
                c4 = execute_generic(c4_plan)
                c3 = execute_explicit(explicit_cases()[case_id])
                self.assertEqual(c4["results"], c3["results"])
                self.assertEqual(c4["execution_record"], c3["execution_record"])

    def test_representative_values_and_ratio_components(self):
        sales = execute_generic(generic_cases()["Q001"])["results"]["level"]
        ratio = execute_generic(generic_cases()["Q004"])["results"]["level"]
        delta = execute_generic(generic_cases()["Q006"])["results"]["delta"]
        self.assertEqual(sales["value"], 420)
        self.assertEqual(ratio["value"], 0.25)
        self.assertEqual(ratio["components"], {"numerator": 100, "denominator": 400})
        self.assertEqual(delta["value"], 20)

    def test_contribution_and_conditional_drill_close(self):
        contribution = execute_generic(generic_cases()["Q011"])["results"]
        self.assertEqual(contribution["contrib"]["total_delta"], 20)
        self.assertEqual(contribution["top"]["value"], "offline")
        self.assertEqual(contribution["top"]["magnitude"], 60)

        conditional = execute_generic(generic_cases()["Q050"])["results"]
        self.assertTrue(conditional["large"]["value"])
        self.assertEqual(
            conditional["drill"]["rows"],
            [{"segment": "electronics", "value": 140},
             {"segment": "food", "value": 120}])

    def test_data_requirements_sql_provenance_and_budget_are_integrated(self):
        result = execute_generic(generic_cases()["Q050"])
        record = result["execution_record"]
        self.assertEqual(record["budget"], {"max_calls": 20, "operator_calls": 6})
        self.assertEqual(len(record["data_requirements"]), 3)
        self.assertTrue(all(row["backend"] == "sqlite"
                            and row["sql_ref"].startswith("sql:")
                            for row in record["data_requirements"]))
        self.assertTrue(record["provenance"]["source_snapshot_ref"].startswith("sha256:"))
        self.assertTrue(all("operator_ref" in value and "provenance_ref" in value
                            for value in result["results"].values()))

    def test_budget_exhaustion_is_a_normalized_failure(self):
        base = generic_cases()["Q006"]
        limited = GenericPlan(base.calls, base.outputs, max_calls=2)
        result = execute_generic(limited)
        self.assertEqual(result["execution_record"]["dag"][-1]["status"],
                         "budget_exhausted")
        self.assertEqual(result["results"]["delta"]["status"], "budget_exhausted")
        self.assertEqual(result["results"]["delta"]["output_type"], "Failure")

    def test_c4_generic_error_names_operator_port_and_actual_type(self):
        plan = GenericPlan((
            CallSpec("grouped", "evaluate_grouped",
                     {"metric_ref": "sales@v1", "period": "2026-06",
                      "dimension": "channel"}),
            CallSpec("bad", "delta",
                     {"before": Ref("grouped", "rows"), "after": 1}),
        ), ("bad",))
        with self.assertRaisesRegex(
                PlanTypeError, r"bad.before: expected number.*segment_rows"):
            execute_generic(plan)

    def test_c3_explicit_error_is_not_materially_better_after_lowering(self):
        plan = ExplicitPlan((
            GroupedMetricNode("grouped", "sales@v1", "2026-06", "channel"),
            DeltaNode("bad", Ref("grouped", "rows"), Ref("grouped", "rows")),
        ), ("bad",))
        with self.assertRaisesRegex(
                PlanTypeError, r"bad.before: expected number.*segment_rows"):
            compile_explicit(plan)

    def test_explicit_node_taxonomy_cost_is_measured(self):
        metrics = comparison_metrics()
        self.assertEqual(metrics["cases"], ["Q001", "Q004", "Q006", "Q011", "Q050"])
        self.assertEqual(metrics["c4"]["node_classes"], 1)
        self.assertEqual(metrics["c3"]["node_classes"], 6)
        self.assertEqual(metrics["c3"]["lowering_dispatch_cases"], 6)
        self.assertEqual(metrics["c3"]["compiled_serialized_bytes"],
                         metrics["c4"]["serialized_bytes"])
        self.assertGreater(metrics["c3"]["serialized_bytes"], 0)
        self.assertGreater(metrics["c4"]["serialized_bytes"], 0)

    def test_registry_cross_input_invariant_rejects_dimension_before_sql(self):
        c4 = GenericPlan((
            CallSpec("bad", "evaluate_grouped",
                     {"metric_ref": "sales@v1", "period": "2026-07",
                      "dimension": "warehouse"}),
        ), ("bad",))
        with self.assertRaisesRegex(
                PlanTypeError, r"bad.dimension: 'warehouse' is not registered"):
            execute_generic(c4)

        c3 = ExplicitPlan((
            GroupedMetricNode("bad", "sales@v1", "2026-07", "warehouse"),
        ), ("bad",))
        with self.assertRaisesRegex(
                PlanTypeError, r"bad.dimension: 'warehouse' is not registered"):
            compile_explicit(c3)


if __name__ == "__main__":
    unittest.main()
