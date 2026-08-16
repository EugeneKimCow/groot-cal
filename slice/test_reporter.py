"""Result Envelope 전용 reporter와 구조 lint 테스트."""
import copy
import unittest

from engine import run_question
from reporter import (EXECUTIVE_REQUIRED_SLOTS, build_report_spec,
                      create_structured_report, lint_structured_report,
                      select_report_result, validate_report_spec)


class ReporterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.bundle = run_question("온라인 매출이 7월에 왜 빠졌어?")

    def test_report_uses_result_envelope_only_and_passes_lint(self):
        report = create_structured_report(self.bundle)
        self.assertFalse(report["capability"]["raw_access"])
        self.assertTrue(lint_structured_report(report, self.bundle)["passed"])

    def test_report_spec_and_required_slots_are_materialized(self):
        report = create_structured_report(self.bundle)
        self.assertEqual("1", report["report_version"])
        self.assertEqual("result_envelope_only", report["report_spec"]["input_capability"])
        self.assertEqual(set(EXECUTIVE_REQUIRED_SLOTS),
                         set(report["report_spec"]["required_slots"]))
        self.assertTrue(all(name in report["slots"] for name in EXECUTIVE_REQUIRED_SLOTS))

    def test_default_result_selection_uses_dominant_axis_not_first_result(self):
        key, reason = select_report_result(self.bundle)
        self.assertEqual("contrib:customer_type", key)
        self.assertEqual("largest_absolute_segment_contribution", reason)

    def test_explicit_result_selection_is_preserved_through_engine(self):
        envelope, bundle = run_question(
            "이 결과를 경영진 메모로 작성해줘", report_context=self.bundle,
            report_result_key="contrib:category")
        self.assertEqual("explicit", envelope["report_spec"]["result_selector"]["mode"])
        self.assertEqual(
            "contrib:category", bundle["results"]["report"]["selected_result"]["result_key"])

    def test_unknown_explicit_result_suspends_without_fallback(self):
        spec = build_report_spec(self.bundle, result_key="missing")
        report = create_structured_report(self.bundle, report_spec=spec)
        self.assertEqual("suspended", report["status"])
        self.assertIn("missing", report["pass_conditions"])

    def test_report_spec_capability_and_selector_are_executable_contracts(self):
        spec = build_report_spec(self.bundle)
        spec["input_capability"] = "raw_data"
        spec["result_selector"] = {"mode": "explicit", "result_key": None}
        problems = validate_report_spec(spec)
        self.assertTrue(any("input_capability" in problem for problem in problems))
        self.assertTrue(any("result_key" in problem for problem in problems))
        report = create_structured_report(self.bundle, report_spec=spec)
        self.assertEqual("out_of_domain", report["status"])

    def test_numeric_tampering_is_blocked(self):
        report = copy.deepcopy(create_structured_report(self.bundle))
        report["claims"][0]["value"] += 1
        lint = lint_structured_report(report, self.bundle)
        self.assertFalse(lint["passed"])
        self.assertEqual("SRC01", lint["violations"][0]["rule"])

    def test_causal_language_is_blocked(self):
        report = copy.deepcopy(create_structured_report(self.bundle))
        report["claims"][0]["text"] += " 정책 때문입니다."
        lint = lint_structured_report(report, self.bundle)
        self.assertFalse(lint["passed"])
        self.assertTrue(any(v["rule"] == "CAU01" for v in lint["violations"]))

    def test_bounded_causal_language_with_evidence_is_allowed(self):
        report = create_structured_report(self.bundle)
        claim = next(c for c in report["claims"] if c["slot"] == "cause_mapping_why")
        self.assertIn("원인으로 확정할 수 없습니다", claim["text"])
        self.assertTrue(lint_structured_report(report, self.bundle)["passed"])

    def test_suggestive_claim_without_evidence_is_blocked(self):
        report = copy.deepcopy(create_structured_report(self.bundle))
        claim = next(c for c in report["claims"] if c["label"] == "데이터 시사")
        claim["evidence_refs"] = []
        lint = lint_structured_report(report, self.bundle)
        self.assertTrue(any(v["rule"] == "EVD01" for v in lint["violations"]))

    def test_percentage_claim_requires_denominator_reference(self):
        report = copy.deepcopy(create_structured_report(self.bundle))
        claim = next(c for c in report["claims"] if c.get("unit") == "percent")
        claim["denominator_ref"] = None
        lint = lint_structured_report(report, self.bundle)
        self.assertTrue(any(v["rule"] == "PCT01" for v in lint["violations"]))

    def test_cross_axis_decomposition_is_blocked_structurally(self):
        report = copy.deepcopy(create_structured_report(self.bundle))
        report["slots"]["decomposition_where"]["result_keys"].append("contrib:category")
        lint = lint_structured_report(report, self.bundle)
        self.assertTrue(any(v["rule"] == "AXIS01" for v in lint["violations"]))

    def test_broken_slot_claim_reference_is_blocked(self):
        report = copy.deepcopy(create_structured_report(self.bundle))
        report["slots"]["headline_verdict"]["claim_refs"].append("claim-999")
        lint = lint_structured_report(report, self.bundle)
        self.assertTrue(any(v["rule"] == "REF01" for v in lint["violations"]))

    def test_unassigned_followups_warn_without_inventing_owner_or_due_date(self):
        report = create_structured_report(self.bundle)
        actions = report["slots"]["followup_actions"]["items"]
        self.assertTrue(actions)
        self.assertTrue(all(a["owner"] is None and a["due_at"] is None for a in actions))
        lint = lint_structured_report(report, self.bundle)
        self.assertTrue(lint["passed"])
        self.assertTrue(any(w["rule"] == "ACT01" for w in lint["warnings"]))

    def test_plan_report_keeps_plan_slot_without_cross_slot_claim_alias(self):
        _, plan_bundle = run_question("2026-06-25 계획 대비 7월 매출 어때?")
        report = create_structured_report(plan_bundle)
        self.assertEqual("plan_gap", report["selected_result"]["result_key"])
        self.assertEqual("populated", report["slots"]["plan_gap"]["status"])
        self.assertEqual([], report["slots"]["plan_gap"]["claim_refs"])
        self.assertTrue(lint_structured_report(report, plan_bundle)["passed"])

    def test_report_question_requires_context(self):
        envelope, bundle = run_question("이 결과를 경영진 메모로 작성해줘")
        self.assertIsNone(bundle)
        self.assertEqual("clarify", envelope["status"])


if __name__ == "__main__":
    unittest.main()
