"""E-019 controlled period-change routing — 양 selector 공개 경계 parity."""
import unittest

from catalog import load_metric_catalog
from engine import run_question
from reporter import (build_report_spec, create_structured_report,
                      lint_structured_report)
from result_adapter import adapt_result
from result_store import materialize_result


def change_view(bundle, key):
    return adapt_result(bundle["results"][key], key)["view"]


def segment_map(view):
    return {row["segment"]: row["value"] for row in view["change"]["segments"]}


class E019ChangeRoutingParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()

    def both(self, question):
        _, current = run_question(question, self.contexts)
        _, routed = run_question(question, self.contexts, route="c4")
        return current, routed

    def test_sales_change_holds_golden_expectations_on_c4_route(self):
        _, routed = run_question("7월 매출이 왜 변했나?", self.contexts,
                                 route="c4")
        channel = routed["results"]["contrib:channel"]["value"]
        self.assertEqual(
            {"before": 4200, "after": 3860, "delta": -340, "pct_change": -8.1},
            channel["total"])
        self.assertEqual({"온라인": -220, "오프라인": -70, "B2B": -50},
                         {row["segment"]: row["delta"]
                          for row in channel["segments"]})
        customer = routed["results"]["contrib:customer_type"]["value"]
        self.assertEqual(-280, {row["segment"]: row["delta"]
                                for row in customer["segments"]}["신규"])
        category = routed["results"]["contrib:category"]["value"]
        by_category = {row["segment"]: row["delta"]
                       for row in category["segments"]}
        self.assertEqual(-200, by_category["가전"])
        self.assertEqual(80, by_category["뷰티"])

    def test_sales_change_axis_views_have_cross_route_parity(self):
        current, routed = self.both("7월 매출이 왜 변했나?")
        for key in ("contrib:channel", "contrib:category",
                    "contrib:customer_type"):
            with self.subTest(key=key):
                cv, rv = change_view(current, key), change_view(routed, key)
                self.assertEqual(cv["change"]["value"], rv["change"]["value"])
                self.assertEqual(cv["change"]["unit"], rv["change"]["unit"])
                self.assertEqual(cv["change"]["pct_change"]["value"],
                                 rv["change"]["pct_change"]["value"])
                self.assertEqual(segment_map(cv), segment_map(rv))
                self.assertEqual("contribution@v1", rv["operator_ref"])
                self.assertEqual("canonical", rv["source_shape"])

    def test_scoped_change_excludes_fixed_axis_on_both_routes(self):
        current, routed = self.both("온라인 매출이 7월에 왜 빠졌어?")
        for bundle in (current, routed):
            self.assertNotIn("contrib:channel", bundle["results"])
        cv = change_view(current, "contrib:customer_type")
        rv = change_view(routed, "contrib:customer_type")
        self.assertEqual(-220, rv["change"]["value"])
        self.assertEqual(segment_map(cv), segment_map(rv))
        self.assertEqual({"신규": -240, "기존": 20}, segment_map(rv))
        rejected = routed["execution_record"]["operators_considered"][
            "runtime_rejected"]
        self.assertEqual(["contribution@v1:channel"],
                         [row["operator"] for row in rejected])
        self.assertIn("고정된 차원", rejected[0]["reason"])

    def test_typed_additive_changes_have_cross_route_parity(self):
        cases = (
            ("7월 영업이익이 왜 줄었나?", "contrib:business_unit", -60,
             {"리테일": -30, "기업": -30}),
            ("7월 말 재고는 얼마이고 6월 말 대비 어느 창고에서 증가했나?",
             "contrib:warehouse", 10, {"서울": 20, "부산": -10}),
        )
        for question, key, expected_delta, expected_segments in cases:
            with self.subTest(key=key):
                current, routed = self.both(question)
                cv, rv = change_view(current, key), change_view(routed, key)
                self.assertEqual(expected_delta, cv["change"]["value"])
                self.assertEqual(expected_delta, rv["change"]["value"])
                self.assertEqual(expected_segments, segment_map(rv))
                self.assertEqual(segment_map(cv), segment_map(rv))

    def test_distinct_change_preserves_set_transition_semantics(self):
        current, routed = self.both("7월 활성 고객 증가는 어느 지역에서 발생했나?")
        cv = change_view(current, "distinct:region")
        rv = change_view(routed, "distinct:region")
        self.assertEqual(2, rv["change"]["value"])
        self.assertEqual(segment_map(cv), segment_map(rv))
        self.assertEqual("set_transition@v1", rv["operator_ref"])
        value = routed["results"]["distinct:region"]["value"]
        self.assertEqual("set_transition", value["operator_semantics"])
        self.assertEqual(["c4", "c5"], value["transitions"]["entrants"])
        self.assertEqual([], value["transitions"]["exits"])

    def test_rate_change_refusal_is_identical_at_the_result_key(self):
        current, routed = self.both("7월 손해율이 왜 변했나?")
        self.assertEqual(current["results"]["change"],
                         routed["results"]["change"])
        self.assertEqual(
            "change_operator_available",
            routed["results"]["change"]["violated"][0]["check"])
        self.assertIsNotNone(routed["execution_record"])

    def test_event_scan_is_an_explicit_call_with_identical_evidence_rows(self):
        current, routed = self.both("7월 매출이 왜 변했나?")
        self.assertEqual(current["results"]["events"]["events"],
                         routed["results"]["events"]["events"])
        self.assertEqual(current["results"]["events"]["overlap_flags"],
                         routed["results"]["events"]["overlap_flags"])
        self.assertEqual("event_overlap_scan@v1",
                         routed["results"]["events"]["operator_ref"])
        plan_operators = [row["operator_ref"]
                          for row in routed["execution_record"]["calls"]]
        self.assertIn("event_overlap_scan@v1", plan_operators)
        self.assertEqual(
            current["execution_record"]["budget"]["hypotheses_examined"],
            routed["execution_record"]["budget"]["hypotheses_examined"])

    def test_hidden_strategy_outputs_are_declared_absent_on_c4_route(self):
        # synthesis §10: 지배축 자동 드릴다운·VRM은 core dispatch에서 제거된
        # 숨은 전략이다. 현행 경로에는 남아 있고, 라우팅된 경계에는 없다.
        current, routed = self.both("7월 매출이 왜 변했나?")
        current_hidden = [key for key in current["results"]
                          if key.startswith("drill:") or key.startswith("vrm:")]
        self.assertTrue(current_hidden)
        routed_hidden = [key for key in routed["results"]
                         if key.startswith("drill:") or key.startswith("vrm:")]
        self.assertEqual([], routed_hidden)

    def test_change_memo_reports_are_identical_across_routes(self):
        reports = {}
        for route in ("current", "c4"):
            _, bundle = run_question("온라인 매출이 7월에 왜 빠졌어?",
                                     self.contexts, route=route)
            spec = build_report_spec(bundle)
            report = create_structured_report(bundle, report_spec=spec)
            self.assertEqual("result", report["status"], report)
            lint = lint_structured_report(report, bundle)
            self.assertEqual([], lint["violations"], lint)
            reports[route] = report
        self.assertEqual(
            reports["current"]["selected_result"]["result_key"],
            reports["c4"]["selected_result"]["result_key"])
        self.assertEqual(
            {c["claim_id"]: (c["text"], c["label"])
             for c in reports["current"]["claims"]},
            {c["claim_id"]: (c["text"], c["label"])
             for c in reports["c4"]["claims"]})

    def test_contribution_materialization_is_deterministic(self):
        _, routed = run_question("7월 영업이익이 왜 줄었나?", self.contexts,
                                 route="c4")
        stored = materialize_result(routed, "contrib:business_unit",
                                    created_at="2026-08-16T00:00:00Z")
        self.assertIn("result_id", stored)
        self.assertEqual("contribution@v1", stored["operator_ref"])
        _, again = run_question("7월 영업이익이 왜 줄었나?", self.contexts,
                                route="c4")
        stored_again = materialize_result(again, "contrib:business_unit",
                                          created_at="2026-08-16T00:00:00Z")
        self.assertEqual(stored["result_id"], stored_again["result_id"])

    def test_change_record_preserves_plan_identity_and_clean_ledger(self):
        _, routed = run_question("7월 매출이 왜 변했나?", self.contexts,
                                 route="c4")
        record = routed["execution_record"]
        self.assertEqual("c4", record["route"])
        self.assertTrue(record["plan_hash"].startswith("sha256:"))
        self.assertFalse([entry for entry in record["binding_ledger"]
                          if entry["state"] == "unconsumed"])
        _, again = run_question("7월 매출이 왜 변했나?", self.contexts,
                                route="c4")
        self.assertEqual(record["plan_hash"],
                         again["execution_record"]["plan_hash"])


if __name__ == "__main__":
    unittest.main()
