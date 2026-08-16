"""Query Spec v1과 강제형 실행 계층의 계약 테스트."""
import copy
import unittest

from interpret import interpret
from kernel import load_ledger, load_semantic
from pipeline import execute_query
from query_spec import shift_month, validate_query_spec
from runtime import ExecutionRuntime


class QuerySpecContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sem = load_semantic()
        cls.ledger = load_ledger()

    def execute(self, question, sem=None):
        sem = sem or self.sem
        envelope = interpret(question, sem)
        self.assertEqual("spec", envelope["status"], envelope)
        return execute_query(envelope, sem, self.ledger)

    def test_calendar_boundary(self):
        self.assertEqual("2025-12", shift_month("2026-01", -1))
        envelope = interpret("1월 매출이 왜 변했나?", self.sem)
        self.assertEqual("2025-12", envelope["query_spec"]["comparison"]["period"])

    def test_scope_is_preserved_in_every_initial_decomposition(self):
        bundle = self.execute("온라인 매출이 7월에 왜 빠졌어?")
        self.assertNotIn("contrib:channel", bundle["results"])
        for key in ("contrib:category", "contrib:customer_type"):
            result = bundle["results"][key]
            self.assertEqual("result", result["status"])
            self.assertEqual(-220, result["total"]["delta_u"])
            self.assertIn("'channel': '온라인'", result["estimand"])
        calls = bundle["execution_record"]["calls"]
        for call in calls:
            if call["operator"] in {"contrib_decomp", "event_overlap_scan"}:
                self.assertEqual("온라인", call["within"]["channel"])

    def test_scoped_level(self):
        bundle = self.execute("7월 온라인 매출은?")
        self.assertEqual(1580, bundle["results"]["level"]["value_u"])

    def test_plan_requires_vintage(self):
        envelope = interpret("7월 매출 계획 대비 어때?", self.sem)
        self.assertEqual("clarify", envelope["status"])
        self.assertEqual("계획 빈티지 미확정", envelope["reason"])

    def test_plan_routes_only_to_plan_operator(self):
        bundle = self.execute("2026-06-25 계획 대비 7월 매출 어때?")
        self.assertEqual(["plan_gap"], list(bundle["results"]))
        self.assertEqual(-390, bundle["results"]["plan_gap"]["total"]["gap_u"])

    def test_plan_preserves_channel_scope(self):
        bundle = self.execute("2026-06-25 계획 대비 7월 온라인 매출 어때?")
        result = bundle["results"]["plan_gap"]
        self.assertEqual(-320, result["total"]["gap_u"])
        self.assertEqual(["온라인"], [r["channel"] for r in result["rows"]])

    def test_missing_period_suspends_before_operator_calls(self):
        bundle = self.execute("1월 매출이 왜 변했나?")
        self.assertIsNone(bundle["execution_record"])
        self.assertEqual("suspended", bundle["results"]["query_spec"]["status"])

    def test_invalid_scope_is_rejected(self):
        envelope = interpret("7월 온라인 매출은?", self.sem)
        envelope["query_spec"]["scope"] = {"channel": "우주판매"}
        checked = validate_query_spec(envelope["query_spec"], self.sem, self.ledger)
        self.assertEqual("out_of_domain", checked["status"])

    def test_malformed_period_returns_sum_type_instead_of_raising(self):
        envelope = interpret("7월 매출이 왜 변했나?", self.sem)
        envelope["query_spec"]["focal_period"] = "bogus"
        checked = validate_query_spec(envelope["query_spec"], self.sem, self.ledger)
        self.assertEqual("out_of_domain", checked["status"])
        self.assertTrue(any("focal_period" in v["detail"] for v in checked["violated"]))

    def test_restricted_dimension_level_requires_its_inherent_scope(self):
        bundle = self.execute("7월 호남 매출은?")
        result = bundle["results"]["query_spec"]
        self.assertEqual("out_of_domain", result["status"])
        self.assertTrue(any("channel=오프라인" in v["detail"]
                            for v in result["violated"]))

    def test_budget_is_enforced_before_calls(self):
        sem = copy.deepcopy(self.sem)
        sem["question_defaults"]["exploration_budget"] = {
            "max_depth": 1, "max_segments": 3, "max_operator_calls": 2}
        bundle = self.execute("7월 매출이 왜 변했나?", sem)
        budget = bundle["execution_record"]["budget"]
        self.assertLessEqual(budget["segments_examined"], 3)
        self.assertLessEqual(budget["operator_calls"], 2)
        self.assertTrue(any(v["status"] == "budget_exhausted"
                            for v in bundle["results"].values()))

    def test_unregistered_operator_cannot_execute(self):
        runtime = ExecutionRuntime(self.sem["question_defaults"]["exploration_budget"],
                                   "inspect_level")
        result = runtime.execute("invented_math", 1, 0, lambda _: {"status": "result"})
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual(0, runtime.record["budget"]["operator_calls"])

    def test_actual_hypotheses_cannot_exceed_reserved_budget(self):
        runtime = ExecutionRuntime(
            {"max_depth": 1, "max_segments": 1, "max_hypotheses": 1,
             "max_operator_calls": 1}, "explain_change")

        def invoke(record):
            record["calls"].append({"operator": "event_overlap_scan"})
            return {"status": "result", "events": [{}, {}]}

        result = runtime.execute(
            "event_overlap_scan", 1, 0, invoke, expected_hypotheses=1)
        self.assertEqual("budget_exhausted", result["status"])
        self.assertLessEqual(runtime.record["budget"]["hypotheses_examined"], 1)

    def test_provenance_and_operator_version_are_automatic(self):
        bundle = self.execute("7월 매출은?")
        result = bundle["results"]["level"]
        self.assertRegex(result["provenance_ref"], r"^call-\d{3}$")
        self.assertEqual("metric_level@v1", result["operator_ref"])
        self.assertTrue(bundle["execution_record"]["query_spec_hash"])
        provenance = bundle["execution_record"]["provenance"]
        self.assertEqual("commerce.net_sales@v1", provenance["metric_ref"])
        self.assertRegex(provenance["input_snapshot_ref"], r"^sha256:[0-9a-f]{16}$")
        self.assertTrue(bundle["execution_record"]["gates_passed"])


if __name__ == "__main__":
    unittest.main()
