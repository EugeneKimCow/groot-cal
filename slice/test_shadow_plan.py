"""Increment 1: canonical plan contracts and shadow compilation tests."""
import copy
import json
from pathlib import Path
import unittest

from analytical_ir import (BindingLedgerEntry, Call, Plan, Ref, ResultEnvelope,
                           Slice)
from catalog import load_metric_catalog
from engine import prepare_question, run_question
from shadow_plan import compile_shadow_plan
from shadow_registry import (OperatorContract, OperatorPort,
                             ShadowOperatorRegistry)


class ShadowPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()

    def compile(self, question):
        envelope, context = prepare_question(question, self.contexts)
        self.assertEqual("spec", envelope["status"], envelope)
        compiled = compile_shadow_plan(envelope, context["sem"])
        return compiled, envelope, context

    def test_level_compiles_to_one_generic_metric_evaluation(self):
        compiled, _, _ = self.compile("7월 매출은?")
        self.assertEqual("result", compiled["status"], compiled)
        plan = compiled["plan"]
        self.assertEqual(["evaluate_metric@v1"],
                         [call.operator_ref for call in plan.calls])
        self.assertEqual("commerce.net_sales@v1", plan.calls[0].inputs["metric"])
        self.assertEqual("2026-07", plan.calls[0].inputs["slice"].period)
        self.assertEqual(Ref("n001"), plan.outputs[0])

    def test_rate_uses_same_evaluate_metric_operator(self):
        compiled, _, _ = self.compile("7월 보험 손해율은?")
        plan = compiled["plan"]
        self.assertEqual("evaluate_metric@v1", plan.calls[0].operator_ref)
        self.assertEqual("insurance.loss_ratio@v1", plan.calls[0].inputs["metric"])

    def test_scope_is_canonicalized_in_slice(self):
        compiled, _, _ = self.compile("7월 온라인 매출은?")
        metric_slice = compiled["plan"].calls[0].inputs["slice"]
        self.assertEqual((("channel", ("온라인",)),), metric_slice.predicates)
        self.assertEqual(
            {"channel": ["온라인"]}, metric_slice.to_dict()["predicates"])

    def test_period_delta_is_an_explicit_typed_dag(self):
        compiled, _, _ = self.compile("7월 매출이 왜 변했나?")
        self.assertEqual("result", compiled["status"], compiled)
        plan = compiled["plan"]
        self.assertEqual(
            ["evaluate_metric@v1", "evaluate_metric@v1", "delta@v1"],
            [call.operator_ref for call in plan.calls])
        self.assertEqual("2026-06", plan.calls[0].inputs["slice"].period)
        self.assertEqual("2026-07", plan.calls[1].inputs["slice"].period)
        self.assertEqual(Ref("n001", "value"), plan.calls[2].inputs["before"])
        self.assertEqual(Ref("n002", "value"), plan.calls[2].inputs["after"])
        self.assertEqual("partial_comparison_root",
                         plan.metadata["intent_fulfillment"])

    def test_calendar_boundary_survives_shadow_compilation(self):
        compiled, _, _ = self.compile("1월 매출이 왜 변했나?")
        self.assertEqual("2025-12", compiled["plan"].calls[0].inputs["slice"].period)

    def test_plan_comparison_fails_closed_in_increment_one(self):
        compiled, _, _ = self.compile("2026-06-25 계획 대비 7월 매출 어때?")
        self.assertEqual("out_of_domain", compiled["status"])
        self.assertEqual("operator_available", compiled["violated"][0]["check"])

    def test_unknown_clause_cannot_be_silently_discarded(self):
        _, envelope, context = self.compile("7월 매출은?")
        altered = copy.deepcopy(envelope)
        altered["query_spec"]["rank"] = {"limit": 3}
        compiled = compile_shadow_plan(altered, context["sem"])
        self.assertEqual("out_of_domain", compiled["status"])
        self.assertEqual("intent_clause_consumed", compiled["violated"][0]["check"])
        rank = next(item for item in compiled["binding_ledger"]
                    if item["clause"] == "rank")
        self.assertEqual("unconsumed", rank["state"])

    def test_nested_unknown_clause_is_detected(self):
        _, envelope, context = self.compile("7월 매출은?")
        altered = copy.deepcopy(envelope)
        altered["query_spec"]["intent"]["breakdown"] = "category"
        compiled = compile_shadow_plan(altered, context["sem"])
        self.assertEqual("out_of_domain", compiled["status"])
        self.assertTrue(any(item["clause"] == "intent.breakdown"
                            for item in compiled["binding_ledger"]))

    def test_serialization_and_hash_are_deterministic(self):
        first, _, _ = self.compile("7월 온라인 매출은?")
        second, _, _ = self.compile("7월 온라인 매출은?")
        self.assertEqual(first["plan"].canonical_json(),
                         second["plan"].canonical_json())
        self.assertEqual(first["plan_hash"], second["plan_hash"])
        self.assertRegex(first["plan_hash"], r"^sha256:[0-9a-f]{64}$")
        json.loads(first["plan"].canonical_json())

    def test_binding_ledger_has_no_unconsumed_known_clause(self):
        compiled, _, _ = self.compile("7월 매출이 왜 변했나?")
        states = {entry.clause: entry.state
                  for entry in compiled["plan"].binding_ledger}
        self.assertNotIn("unconsumed", states.values())
        self.assertEqual("preserved", states["requested_output"])
        self.assertEqual("consumed", states["comparison"])

    def test_registry_rejects_forward_and_wrong_typed_refs(self):
        plan = Plan(
            calls=(
                Call("n001", "delta@v1", {
                    "before": Ref("n002", "value"),
                    "after": Ref("n003", "value"),
                }),
                Call("n002", "evaluate_metric@v1", {
                    "metric": "commerce.net_sales@v1",
                    "slice": Slice("2026-06", "2026-08-06"),
                }),
            ),
            outputs=(Ref("n001"),),
            binding_ledger=(BindingLedgerEntry(
                "test", "consumed", True, ("test",)),),
        )
        checked = ShadowOperatorRegistry().validate_plan(
            plan, {"commerce.net_sales@v1": {}})
        self.assertEqual("out_of_domain", checked["status"])
        details = [item["detail"] for item in checked["violated"]]
        self.assertTrue(any("UnknownRef != Number" in item for item in details))

    def test_registry_rejects_invalid_slice_and_unconsumed_binding(self):
        plan = Plan(
            calls=(Call("n001", "evaluate_metric@v1", {
                "metric": "commerce.net_sales@v1",
                "slice": Slice("2026-13", "not-a-date"),
            }),),
            outputs=(Ref("n001"),),
            binding_ledger=(BindingLedgerEntry(
                "rank", "unconsumed", {"limit": 3}),),
        )
        checked = ShadowOperatorRegistry().validate_plan(
            plan, {"commerce.net_sales@v1": {}})
        details = [item["detail"] for item in checked["violated"]]
        self.assertTrue(any("unconsumed binding clause: rank" in item
                            for item in details))
        self.assertTrue(any("invalid month" in item for item in details))
        self.assertTrue(any("invalid as_of" in item for item in details))

    def test_named_cross_input_validator_rejects_metric_mismatch(self):
        plan = Plan(
            calls=(
                Call("n001", "evaluate_metric@v1", {
                    "metric": "m.one@v1", "slice": Slice("2026-06", "2026-08-06")}),
                Call("n002", "evaluate_metric@v1", {
                    "metric": "m.two@v1", "slice": Slice("2026-07", "2026-08-06")}),
                Call("n003", "delta@v1", {
                    "before": Ref("n001", "value"), "after": Ref("n002", "value")}),
            ),
            outputs=(Ref("n003"),),
            binding_ledger=(),
        )
        checked = ShadowOperatorRegistry().validate_plan(
            plan, {"m.one@v1": {}, "m.two@v1": {}})
        details = [item["detail"] for item in checked["violated"]]
        self.assertTrue(any("same_metric_inputs" in item for item in details))

    def test_duplicate_and_unknown_validator_contracts_are_rejected(self):
        contract = OperatorContract(
            "x@v1", (OperatorPort("x", "Number"),), {"": "Number"})
        registry = ShadowOperatorRegistry(contracts=(contract,))
        with self.assertRaises(ValueError):
            registry.register(contract)
        with self.assertRaises(ValueError):
            ShadowOperatorRegistry(contracts=(OperatorContract(
                "y@v1", (), {"": "Number"}, ("invented_law",)),))

    def test_production_engine_output_does_not_include_shadow_plan(self):
        envelope, bundle = run_question("7월 매출은?", self.contexts)
        self.assertEqual("spec", envelope["status"])
        self.assertEqual(3860, bundle["results"]["level"]["value_u"])
        self.assertNotIn("shadow_plan", envelope)
        self.assertNotIn("shadow_plan", bundle)

    def test_wire_schema_is_present_and_versioned(self):
        path = Path(__file__).parent.parent / "schemas" / "analytical-plan-v1.schema.json"
        schema = json.loads(path.read_text())
        self.assertEqual("groot-cal/analytical-plan-v1", schema["$id"])
        self.assertEqual("1", schema["properties"]["plan_version"]["const"])

    def test_normalized_result_envelope_is_a_strict_tagged_union(self):
        envelope = ResultEnvelope(
            status="result", result_type="MetricScalar", value={"value": 10},
            operator_ref="evaluate_metric@v1", provenance_ref="call-n001",
            label_ceiling="descriptive")
        wire = envelope.to_dict()
        self.assertEqual("result", wire["status"])
        self.assertNotIn("violated", wire)
        self.assertEqual("evaluate_metric@v1",
                         wire["evidence"]["operator_ref"])
        with self.assertRaises(ValueError):
            ResultEnvelope(status="result", result_type="MetricScalar", value=10)
        with self.assertRaises(ValueError):
            ResultEnvelope(status="suspended", result_type="MetricScalar")
        with self.assertRaises(ValueError):
            ResultEnvelope(
                status="out_of_domain", result_type="MetricScalar",
                violated=({"check": "x"},), missing_inputs=("ledger",))

    def test_result_envelope_schema_is_present_and_versioned(self):
        path = (Path(__file__).parent.parent / "schemas" /
                "analytical-result-envelope-v1.schema.json")
        schema = json.loads(path.read_text())
        self.assertEqual("groot-cal/analytical-result-envelope-v1", schema["$id"])
        self.assertEqual(3, len(schema["oneOf"]))


if __name__ == "__main__":
    unittest.main()
