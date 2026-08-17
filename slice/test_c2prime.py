"""C2′ 측정 하네스의 계약 게이트 (오프라인 — 규칙 제안자)."""
import json
import unittest
from pathlib import Path

from catalog import load_metric_catalog
from eval_c2prime import run_condition
from shadow_intent import (_has_silent_substitution, compile_shadow_intent,
                           propose_clause_bindings)


class C2PrimeHarnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()

    def test_rule_proposer_baseline_scores_10_of_10(self):
        result = run_condition(propose_clause_bindings, "rule", 1,
                               self.contexts)
        summary = result["summary"]
        self.assertEqual(10, summary["analytical_pass"], summary)
        self.assertEqual(0, summary["silent_substitutions"])
        self.assertEqual(0, summary["wrong_values"])
        self.assertEqual([], summary["unstable_cases"])

    def test_plan_gap_subject_consumption_is_not_a_substitution(self):
        # E-024 scorer 수리 고정: plan_gap@v1은 evaluate_metric 없이 metric을
        # 직접 소비한다 — subject 유지로 판정해야 한다.
        compiled = compile_shadow_intent("2026-06-25 계획 대비 7월 매출 어때?",
                                         contexts=self.contexts)
        self.assertEqual("result", compiled["status"])
        self.assertFalse(_has_silent_substitution(compiled))

    def test_dropped_subject_is_still_a_substitution(self):
        # 수리가 검출력을 약화시키지 않았는지: subject를 소비하지 않는 plan은
        # 여전히 치환으로 잡힌다.
        compiled = compile_shadow_intent("7월 매출은?", contexts=self.contexts)
        self.assertEqual("result", compiled["status"])
        import dataclasses
        plan = compiled["plan"]
        gutted = dataclasses.replace(
            plan, calls=tuple(
                dataclasses.replace(
                    call, inputs={name: ("insurance.loss_ratio@v1"
                                         if name == "metric" else value)
                                  for name, value in call.inputs.items()})
                for call in plan.calls))
        self.assertTrue(_has_silent_substitution(
            {**compiled, "plan": gutted}))


if __name__ == "__main__":
    unittest.main()
