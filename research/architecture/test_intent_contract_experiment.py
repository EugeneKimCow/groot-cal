import dataclasses
import json
from pathlib import Path
import unittest

from intent_contract_experiment import (
    ClauseBindingRecord, IntentCase, REGISTERED_OPERATORS, binding_hash,
    comparison_metrics, compile_bound_intent, compile_direct_plan,
    compile_existing_bound_spec, inconsistent_bound_spec, intent_cases,
    select_contract,
)


class IntentContractExperimentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = intent_cases()

    def assert_same_outcome(self, case):
        bound = compile_bound_intent(case)
        direct = compile_direct_plan(case)
        self.assertEqual(bound["status"], direct["status"])
        if bound["status"] == "result":
            self.assertEqual(bound["plan"].canonical_json(),
                             direct["plan"].canonical_json())
        else:
            self.assertEqual(bound["violated"], direct["violated"])
        return direct

    def test_shared_record_is_versioned_spanned_and_fully_accounted(self):
        for case in self.cases.values():
            with self.subTest(case=case.case_id):
                for record in case.records:
                    self.assertEqual("1", record.record_version)
                    self.assertEqual(
                        record.source_text,
                        case.question[record.start:record.end])
                    self.assertIn(record.state, {
                        "consumed", "preserved", "ambiguous", "unsupported",
                        "non_semantic",
                    })
                    if record.material:
                        self.assertNotEqual("non_semantic", record.state)
                json.loads(json.dumps(
                    [record.to_dict() for record in case.records],
                    ensure_ascii=False, sort_keys=True))

    def test_both_candidates_have_plan_and_refusal_parity(self):
        metrics = comparison_metrics(self.cases)
        self.assertEqual(12, metrics["cases"])
        self.assertEqual(7, metrics["successful_cases"])
        self.assertEqual(7, metrics["plan_byte_parity"])
        self.assertEqual(5, metrics["refusal_parity"])
        for case in self.cases.values():
            with self.subTest(case=case.case_id):
                self.assert_same_outcome(case)

    def test_average_inventory_preserves_requested_reducer(self):
        result = self.assert_same_outcome(self.cases["average_inventory"])
        self.assertEqual("result", result["status"])
        call = result["plan"].calls[0]
        self.assertEqual("scm.inventory_balance@v1", call.inputs["metric"])
        self.assertEqual("time_average", call.inputs["reducer"])
        self.assertEqual("2026-07", call.inputs["slice"].period)

    def test_inventory_turnover_refuses_instead_of_binding_inventory(self):
        result = self.assert_same_outcome(self.cases["inventory_turnover"])
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("material_clause_supported",
                         result["violated"][0]["check"])
        self.assertIn("c02", result["violated"][0]["detail"])

    def test_filter_breakdown_and_comparison_all_reach_plan(self):
        result = self.assert_same_outcome(self.cases["filtered_region_change"])
        calls = result["plan"].calls
        self.assertEqual(
            ["evaluate_metric@v1", "evaluate_metric@v1", "contribution@v1"],
            [call.operator_ref for call in calls])
        self.assertEqual("2026-06", calls[0].inputs["slice"].period)
        self.assertEqual("2026-07", calls[1].inputs["slice"].period)
        self.assertEqual(("오프라인",),
                         calls[1].inputs["slice"].predicates[0][1])
        self.assertEqual(["region"], calls[1].inputs["group_by"])

    def test_rank_limit_breakdown_and_only_output_are_not_dropped(self):
        result = self.assert_same_outcome(self.cases["top3_product_change"])
        rank = result["plan"].calls[-1]
        self.assertEqual("rank@v1", rank.operator_ref)
        self.assertEqual(3, rank.inputs["limit"])
        self.assertEqual("descending", rank.inputs["order"])
        evaluations = [call for call in result["plan"].calls
                       if call.operator_ref == "evaluate_metric@v1"]
        self.assertTrue(all(call.inputs["group_by"] == ["product_category"]
                            for call in evaluations))
        self.assertEqual(["only_ranked", "result"],
                         result["plan"].metadata["outputs"])

    def test_explicit_year_survives_without_current_year_substitution(self):
        result = self.assert_same_outcome(self.cases["explicit_year"])
        self.assertEqual("2025-07", result["plan"].calls[0].inputs["slice"].period)

    def test_explicit_comparison_has_two_time_operands_and_delta(self):
        result = self.assert_same_outcome(self.cases["explicit_comparison"])
        calls = result["plan"].calls
        self.assertEqual("2025-06", calls[0].inputs["slice"].period)
        self.assertEqual("2025-07", calls[1].inputs["slice"].period)
        self.assertEqual("delta@v1", calls[2].operator_ref)

    def test_unsupported_analytical_objectives_fail_closed(self):
        for case_id in ("acceleration", "outlier", "concentration"):
            with self.subTest(case=case_id):
                result = self.assert_same_outcome(self.cases[case_id])
                self.assertEqual("out_of_domain", result["status"])
                self.assertEqual("material_clause_supported",
                                 result["violated"][0]["check"])

    def test_multi_metric_and_nested_intent_have_explicit_calls(self):
        multi = self.assert_same_outcome(
            self.cases["multi_metric_divergence"])["plan"]
        metric_refs = [call.inputs["metric"] for call in multi.calls
                       if call.operator_ref == "evaluate_metric@v1"]
        self.assertEqual(2, len(set(metric_refs)))
        self.assertEqual("align_metrics@v1", multi.calls[-1].operator_ref)

        nested = self.assert_same_outcome(self.cases["nested_diagnosis"])["plan"]
        self.assertEqual("rank@v1", nested.calls[-2].operator_ref)
        self.assertEqual("drilldown@v1", nested.calls[-1].operator_ref)
        self.assertEqual("region", nested.calls[-1].inputs["group_by"])

    def test_ambiguity_returns_clarify_with_clause_local_errors(self):
        result = self.assert_same_outcome(self.cases["ambiguous_performance"])
        self.assertEqual("clarify", result["status"])
        self.assertEqual(2, len(result["violated"]))
        self.assertIn("c01", result["violated"][0]["detail"])
        self.assertIn("c02", result["violated"][1]["detail"])

    def test_malformed_span_and_unknown_semantic_ref_fail_identically(self):
        base = self.cases["explicit_year"]
        bad_span = dataclasses.replace(base.records[0], start=1)
        case = dataclasses.replace(base, records=(bad_span,) + base.records[1:])
        result = self.assert_same_outcome(case)
        self.assertEqual("clause_binding_valid", result["violated"][0]["check"])
        self.assertIn("c01", result["violated"][0]["detail"])

        bad_subject = dataclasses.replace(
            base.records[1], value="invented.metric@v1")
        case = dataclasses.replace(base, records=(base.records[0], bad_subject,
                                                  base.records[2]))
        result = self.assert_same_outcome(case)
        self.assertIn("unregistered semantic ref", result["violated"][0]["detail"])

    def test_invalid_rank_and_material_nonsemantic_fail_closed(self):
        base = self.cases["top3_product_change"]
        records = tuple(dataclasses.replace(
            row, value={"order": "descending", "limit": 0})
            if row.role == "ranking" else row for row in base.records)
        result = self.assert_same_outcome(dataclasses.replace(base, records=records))
        self.assertIn("invalid ranking", result["violated"][0]["detail"])

        record = dataclasses.replace(
            base.records[0], state="non_semantic", role=None, value=None,
            target_refs=(), reason="claimed discourse")
        result = self.assert_same_outcome(dataclasses.replace(
            base, records=(record,) + base.records[1:]))
        self.assertIn("material clause cannot be non_semantic",
                      result["violated"][0]["detail"])

        records = tuple(dataclasses.replace(row, value="invented_output")
                        if row.role == "output" else row for row in base.records)
        result = self.assert_same_outcome(dataclasses.replace(base, records=records))
        self.assertIn("unregistered output restriction",
                      result["violated"][0]["detail"])

    def test_multiple_objectives_cannot_silently_select_the_first(self):
        base = self.cases["average_inventory"]
        original = next(row for row in base.records if row.role == "analysis")
        extra = dataclasses.replace(
            original, clause_id="c05", source_text="평균",
            start=base.question.index("평균"),
            end=base.question.index("평균") + len("평균"), value="delta")
        case = dataclasses.replace(base, records=base.records + (extra,))
        result = self.assert_same_outcome(case)
        self.assertIn("multiple bindings require explicit composition",
                      result["violated"][0]["detail"])

    def test_record_order_does_not_change_plan_or_binding_identity(self):
        base = self.cases["top3_product_change"]
        reversed_case = dataclasses.replace(base, records=tuple(reversed(base.records)))
        first = compile_direct_plan(base)
        second = compile_direct_plan(reversed_case)
        self.assertEqual(first["plan"].canonical_json(),
                         second["plan"].canonical_json())
        self.assertEqual(binding_hash(base.records),
                         binding_hash(reversed_case.records))

    def test_bound_intent_adds_a_consistency_failure_state(self):
        case = self.cases["average_inventory"]
        inconsistent = inconsistent_bound_spec(case)
        result = compile_existing_bound_spec(case, inconsistent)
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("bound_intent_consistent",
                         result["violated"][0]["check"])
        self.assertIn("reducer", result["violated"][0]["detail"])

    def test_decision_rule_selects_direct_plan_plus_binding_record(self):
        decision = select_contract(self.cases)
        self.assertEqual("direct_plan_plus_binding_record", decision["selected"])
        self.assertEqual("bound_intent_spec", decision["rejected"])
        metrics = decision["metrics"]
        self.assertEqual(1, metrics["shared_record_types"])
        self.assertEqual(1,
                         metrics["candidate_a"]["additional_serialized_contracts"])
        self.assertEqual(0,
                         metrics["candidate_b"]["additional_serialized_contracts"])
        self.assertGreater(
            metrics["candidate_a"]["additional_intermediate_bytes"], 0)
        self.assertGreater(
            metrics["candidate_a"]["duplicated_bound_values"], 0)

    def test_emitted_operator_vocabulary_is_closed_and_shadow_only(self):
        for case in self.cases.values():
            compiled = compile_direct_plan(case)
            if compiled["status"] != "result":
                continue
            self.assertTrue(all(call.operator_ref in REGISTERED_OPERATORS
                                for call in compiled["plan"].calls))
            self.assertTrue(compiled["plan"].metadata["shadow_only"])
            self.assertEqual("E-015", compiled["plan"].metadata["experiment"])

        engine_source = (Path(__file__).resolve().parents[2] / "slice" /
                         "engine.py").read_text()
        self.assertNotIn("intent_contract_experiment", engine_source)


if __name__ == "__main__":
    unittest.main()
