"""E-016 shadow intent fidelity and closed binding contract tests."""
import dataclasses
import json
from pathlib import Path
import unittest

from catalog import load_metric_catalog
from clause_binding import (BindingValue, ClauseBinding,
                            SourceClauseBindingRecord, validate_binding_record)
from engine import run_question
from shadow_intent import (compile_shadow_intent, fidelity_report,
                           propose_clause_bindings)
from shadow_registry import ShadowOperatorRegistry


ADVERSARIAL_QUESTIONS = (
    "7월 평균 재고는?",
    "7월 재고 회전율은?",
    "7월 오프라인 매출 감소를 지역별로 보여줘",
    "7월 매출 감소 상위 3개 제품군만 보여줘",
    "2025년 7월 매출은?",
    "7월 매출 증가 속도가 둔화되고 있는가?",
    "7월 매출 감소가 일부 고객의 이상치 때문인가?",
    "7월 매출은 제품과 지역 중 어디에 더 집중되어 있나?",
    "7월 매출과 영업이익은 왜 엇갈렸나?",
)

CHANGE_PARAPHRASES = (
    "7월 매출이 왜 변했나?",
    "7월 매출 변화 원인은?",
    "7월 매출 감소 동인은?",
    "7월 매출이 전월 대비 어떻게 달라졌어?",
    "7월 매출 변동을 제품군별 기여로 보여줘",
)


class ShadowIntentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()

    def compile(self, question):
        return compile_shadow_intent(question, contexts=self.contexts)

    def test_required_adversarial_gate_has_zero_silent_substitutions(self):
        report = fidelity_report(ADVERSARIAL_QUESTIONS, contexts=self.contexts)
        self.assertEqual(9, len(report))
        self.assertTrue(all(not row["silent_substitution"] for row in report))
        by_question = {row["question"]: row for row in report}
        supported = {
            ADVERSARIAL_QUESTIONS[2], ADVERSARIAL_QUESTIONS[3],
            ADVERSARIAL_QUESTIONS[4], ADVERSARIAL_QUESTIONS[8],
        }
        for question, row in by_question.items():
            expected = "result" if question in supported else "out_of_domain"
            self.assertEqual(expected, row["status"], question)

    def test_average_inventory_refuses_incompatible_reducer(self):
        result = self.compile(ADVERSARIAL_QUESTIONS[0])
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("material_clause_supported",
                         result["violated"][0]["check"])
        average = next(row for row in result["binding_record"].clauses
                       if row.source_text == "평균")
        self.assertEqual("unsupported", average.state)
        self.assertIn("time_average", average.reason)

    def test_inventory_turnover_does_not_bind_neighboring_inventory_metric(self):
        result = self.compile(ADVERSARIAL_QUESTIONS[1])
        self.assertEqual("out_of_domain", result["status"])
        turnover = next(row for row in result["binding_record"].clauses
                        if "회전율" in row.source_text)
        self.assertEqual("unsupported", turnover.state)
        self.assertFalse(any(row.role == "subject" and row.value
                             for row in result["binding_record"].clauses))

    def test_filter_breakdown_and_period_reach_contribution_plan(self):
        result = self.compile(ADVERSARIAL_QUESTIONS[2])
        self.assertEqual("result", result["status"], result)
        calls = result["plan"].calls
        self.assertEqual(
            ["evaluate_metric@v1", "evaluate_metric@v1", "contribution@v1"],
            [call.operator_ref for call in calls])
        self.assertEqual("2026-06", calls[0].inputs["slice"].period)
        self.assertEqual("2026-07", calls[1].inputs["slice"].period)
        self.assertEqual(("오프라인",), calls[1].inputs["slice"].predicates[0][1])
        self.assertEqual(["region"], calls[1].inputs["group_by"])

    def test_rank_limit_product_breakdown_and_only_output_are_preserved(self):
        result = self.compile(ADVERSARIAL_QUESTIONS[3])
        self.assertEqual("result", result["status"], result)
        rank = result["plan"].calls[-1]
        self.assertEqual("rank@v1", rank.operator_ref)
        self.assertEqual(3, rank.inputs["limit"])
        evaluations = [call for call in result["plan"].calls
                       if call.operator_ref == "evaluate_metric@v1"]
        self.assertTrue(all(call.inputs["group_by"] == ["category"]
                            for call in evaluations))
        self.assertEqual(["only_ranked", "result"],
                         result["plan"].metadata["outputs"])

    def test_explicit_year_is_not_replaced_by_default_year(self):
        result = self.compile(ADVERSARIAL_QUESTIONS[4])
        self.assertEqual("result", result["status"])
        self.assertEqual("2025-07", result["plan"].calls[0].inputs["slice"].period)

    def test_unsupported_objectives_have_clause_local_refusals(self):
        for question in ADVERSARIAL_QUESTIONS[5:8]:
            with self.subTest(question=question):
                result = self.compile(question)
                self.assertEqual("out_of_domain", result["status"])
                self.assertEqual("material_clause_supported",
                                 result["violated"][0]["check"])
                unsupported = [row for row in result["binding_record"].clauses
                               if row.state == "unsupported"]
                self.assertTrue(any(row.role == "analysis" for row in unsupported))

    def test_multi_metric_divergence_has_explicit_composition(self):
        result = self.compile(ADVERSARIAL_QUESTIONS[8])
        self.assertEqual("result", result["status"], result)
        metrics = [call.inputs["metric"] for call in result["plan"].calls
                   if call.operator_ref == "evaluate_metric@v1"]
        self.assertEqual({"commerce.net_sales@v1",
                          "finance.operating_profit@v1"}, set(metrics))
        self.assertEqual("align_metrics@v1",
                         result["plan"].calls[-1].operator_ref)

    def test_five_change_paraphrases_normalize_to_one_family(self):
        report = fidelity_report(CHANGE_PARAPHRASES, contexts=self.contexts)
        self.assertEqual(5, len(report))
        self.assertEqual({"result"}, {row["status"] for row in report})
        self.assertEqual({"explain_change"},
                         {row["operation_family"] for row in report})
        self.assertTrue(all(not row["silent_substitution"] for row in report))

    def test_successful_material_clauses_have_exact_spans_and_plan_consumers(self):
        question = ADVERSARIAL_QUESTIONS[3]
        result = self.compile(question)
        record = result["binding_record"]
        for row in record.clauses:
            self.assertEqual(row.source_text, question[row.start:row.end])
            if row.material:
                self.assertIn(row.state, {"consumed", "preserved"})
                self.assertTrue(row.target_refs, row)
        wire = json.loads(record.canonical_json())
        self.assertEqual("1", wire["record_version"])
        self.assertRegex(record.binding_hash(), r"^sha256:[0-9a-f]{64}$")

    def test_serialization_plan_and_binding_hashes_are_deterministic(self):
        first = self.compile(ADVERSARIAL_QUESTIONS[2])
        second = self.compile(ADVERSARIAL_QUESTIONS[2])
        self.assertEqual(first["plan"].canonical_json(),
                         second["plan"].canonical_json())
        self.assertEqual(first["plan_hash"], second["plan_hash"])
        self.assertEqual(first["binding_record"].canonical_json(),
                         second["binding_record"].canonical_json())
        self.assertEqual(first["binding_hash"], second["binding_hash"])

    def test_unknown_analytical_language_fails_closed(self):
        result = self.compile("7월 매출 마법 분석해줘")
        self.assertEqual("out_of_domain", result["status"])
        self.assertTrue(any("unrecognized analytical language" in item["detail"]
                            for item in result["violated"]))

    def test_contract_rejects_bad_span_unknown_ref_and_multiple_objectives(self):
        proposed = propose_clause_bindings("2025년 7월 매출은?", self.contexts)
        vocabulary = {
            "metric_refs": {"commerce.net_sales@v1"},
            "dimension_refs": set(), "dimension_values": {},
        }
        bad_span = dataclasses.replace(proposed.clauses[0], start=1)
        record = dataclasses.replace(
            proposed, clauses=(bad_span,) + proposed.clauses[1:])
        self.assertTrue(any("source span/text mismatch" in problem
                            for problem in validate_binding_record(record, vocabulary)))

        subject_index = next(index for index, row in enumerate(proposed.clauses)
                             if row.role == "subject")
        unknown = dataclasses.replace(
            proposed.clauses[subject_index],
            value=BindingValue("metric_ref", "invented.metric@v1"))
        rows = list(proposed.clauses)
        rows[subject_index] = unknown
        record = dataclasses.replace(proposed, clauses=tuple(rows))
        self.assertTrue(any("unregistered metric ref" in problem
                            for problem in validate_binding_record(record, vocabulary)))

        question = "7월 매출 변화 감소"
        duplicate = SourceClauseBindingRecord(question, (
            ClauseBinding("c01", "7월", 0, 2, True, "consumed", "time.target",
                          BindingValue("month", "2026-07")),
            ClauseBinding("c02", "매출", 3, 5, True, "consumed", "subject",
                          BindingValue("metric_ref", "commerce.net_sales@v1")),
            ClauseBinding("c03", "변화", 6, 8, True, "consumed", "analysis",
                          BindingValue("analysis_ref", "delta")),
            ClauseBinding("c04", "감소", 9, 11, True, "consumed", "analysis",
                          BindingValue("analysis_ref", "contribution")),
        ))
        self.assertTrue(any("multiple bindings require registered composition"
                            in problem for problem in validate_binding_record(
                                duplicate, vocabulary)))

    def test_all_successful_references_are_registry_governed(self):
        operator_refs = ShadowOperatorRegistry().operator_refs
        for question in ADVERSARIAL_QUESTIONS + CHANGE_PARAPHRASES:
            result = self.compile(question)
            if result["status"] != "result":
                continue
            self.assertTrue(all(call.operator_ref in operator_refs
                                for call in result["plan"].calls))
            self.assertEqual("E-016", result["plan"].metadata["experiment"])
            self.assertTrue(result["plan"].metadata["shadow_only"])

    def test_engine_routing_and_output_remain_unchanged(self):
        envelope, bundle = run_question("7월 매출은?", self.contexts)
        self.assertEqual("spec", envelope["status"])
        self.assertEqual(3860, bundle["results"]["level"]["value_u"])
        self.assertNotIn("shadow_intent", envelope)
        self.assertNotIn("shadow_intent", bundle)
        engine_source = (Path(__file__).parent / "engine.py").read_text()
        self.assertNotIn("shadow_intent", engine_source)

    def test_binding_wire_schema_is_present_and_versioned(self):
        path = (Path(__file__).parent.parent / "schemas" /
                "source-clause-bindings-v1.schema.json")
        schema = json.loads(path.read_text())
        self.assertEqual("groot-cal/source-clause-bindings-v1", schema["$id"])
        self.assertEqual("1", schema["properties"]["record_version"]["const"])


if __name__ == "__main__":
    unittest.main()
