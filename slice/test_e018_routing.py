"""E-018 controlled metric-level routing — 양 selector 공개 경계 parity."""
import copy
import json
import unittest
from pathlib import Path

from catalog import load_metric_catalog
from engine import run_question
from reporter import (build_report_spec, create_structured_report,
                      lint_structured_report)
from result_adapter import adapt_result
from result_store import assess_staleness, materialize_result


LEVEL_CASES = (
    ("7월 매출은?", 3860),
    ("7월 영업이익은?", 20),
    ("7월 보험 손해율은?", 0.66),
    ("7월 말 재고는?", 190),
    ("7월 활성 고객 수는?", 5),
)


class E018RoutingParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()

    def both(self, question, contexts=None):
        contexts = contexts if contexts is not None else self.contexts
        _, current = run_question(question, contexts)
        _, routed = run_question(question, contexts, route="c4_level")
        return current, routed

    def views(self, current, routed):
        return (adapt_result(current["results"]["level"], "level"),
                adapt_result(routed["results"]["level"], "level"))

    def test_unknown_route_is_rejected(self):
        with self.assertRaises(ValueError):
            run_question("7월 매출은?", self.contexts, route="c4")

    def test_level_parity_across_all_five_metric_algebras(self):
        for question, expected in LEVEL_CASES:
            with self.subTest(question=question):
                current, routed = self.both(question)
                cv, rv = self.views(current, routed)
                self.assertEqual("result", cv["status"], cv)
                self.assertEqual("result", rv["status"], rv)
                self.assertEqual(expected, cv["view"]["scalar"]["value"])
                self.assertEqual(cv["view"]["scalar"]["value"],
                                 rv["view"]["scalar"]["value"])
                self.assertEqual(cv["view"]["scalar"]["unit"],
                                 rv["view"]["scalar"]["unit"])
                self.assertEqual(cv["view"]["label_capabilities"],
                                 rv["view"]["label_capabilities"])
                # 정체성은 사칭 없이 선언된다: canonical wire + C4 operator.
                self.assertEqual("canonical", rv["view"]["source_shape"])
                self.assertEqual("evaluate_metric@v1", rv["view"]["operator_ref"])
                self.assertEqual("1",
                                 routed["results"]["level"]["envelope_version"])

    def test_scoped_level_parity(self):
        current, routed = self.both("7월 온라인 매출은?")
        cv, rv = self.views(current, routed)
        self.assertEqual(1580, cv["view"]["scalar"]["value"])
        self.assertEqual(1580, rv["view"]["scalar"]["value"])
        self.assertEqual(cv["view"]["scalar"]["unit"], rv["view"]["scalar"]["unit"])

    def test_missing_month_suspends_identically_at_query_spec_boundary(self):
        current, routed = self.both("5월 매출은?")
        self.assertEqual("suspended", current["results"]["query_spec"]["status"])
        self.assertEqual(current["results"]["query_spec"],
                         routed["results"]["query_spec"])
        self.assertIsNone(routed["execution_record"])

    def test_bad_scope_fails_identically_at_query_spec_boundary(self):
        current, routed = self.both("7월 호남 매출은?")
        self.assertEqual("out_of_domain", current["results"]["query_spec"]["status"])
        self.assertEqual(current["results"]["query_spec"],
                         routed["results"]["query_spec"])

    def test_duplicate_binding_fails_closed_on_both_routes(self):
        contexts = copy.deepcopy(self.contexts)
        context = next(c for c in contexts
                       if c["sem"]["metric"]["id"] == "insurance.loss_ratio")
        bindings = context["sem"]["metric"]["bindings"]
        bindings["denominator_field"] = bindings["numerator_field"]
        current, routed = self.both("7월 보험 손해율은?", contexts)
        self.assertEqual("out_of_domain", current["results"]["level"]["status"])
        self.assertEqual("out_of_domain", routed["results"]["level"]["status"])
        self.assertEqual(
            "field_binding_unique",
            current["results"]["level"]["violated"][0]["check"])
        self.assertEqual(
            "field_binding_unique",
            routed["results"]["level"]["violated"][0]["check"])

    def test_label_ceiling_and_reporting_parity(self):
        current, routed = self.both("7월 매출은?")
        reports = {}
        for name, bundle in (("current", current), ("routed", routed)):
            spec = build_report_spec(bundle)
            report = create_structured_report(bundle, report_spec=spec)
            self.assertEqual("result", report["status"], report)
            lint = lint_structured_report(report, bundle)
            self.assertEqual([], lint["violations"], lint)
            reports[name] = report
        current_texts = {claim["claim_id"]: (claim["text"], claim["label"])
                         for claim in reports["current"]["claims"]}
        routed_texts = {claim["claim_id"]: (claim["text"], claim["label"])
                        for claim in reports["routed"]["claims"]}
        self.assertEqual(current_texts, routed_texts)

    def test_materialization_is_deterministic_with_declared_identity(self):
        current, routed = self.both("7월 매출은?")
        stored_current = materialize_result(
            current, "level", created_at="2026-08-16T00:00:00Z")
        stored_routed = materialize_result(
            routed, "level", created_at="2026-08-16T00:00:00Z")
        self.assertIn("result_id", stored_current)
        self.assertIn("result_id", stored_routed)
        self.assertEqual("metric_level@v1", stored_current["operator_ref"])
        self.assertEqual("evaluate_metric@v1", stored_routed["operator_ref"])
        self.assertEqual(stored_current["metric_ref"], stored_routed["metric_ref"])
        self.assertEqual(stored_current["input_snapshot_ref"],
                         stored_routed["input_snapshot_ref"])
        # 같은 질의를 다시 실행해도 같은 결정적 result ID가 나온다.
        _, again = run_question("7월 매출은?", self.contexts, route="c4_level")
        stored_again = materialize_result(
            again, "level", created_at="2026-08-16T00:00:00Z")
        self.assertEqual(stored_routed["result_id"], stored_again["result_id"])
        staleness = assess_staleness(
            stored_routed,
            current_input_snapshot_ref=stored_routed["input_snapshot_ref"])
        self.assertEqual("fresh", staleness["staleness_status"])

    def test_execution_record_preserves_plan_and_binding_identity(self):
        current, routed = self.both("7월 매출은?")
        record = routed["execution_record"]
        self.assertEqual("c4_level", record["route"])
        self.assertTrue(record["plan_hash"].startswith("sha256:"))
        self.assertTrue(record["call_provenance"])
        self.assertFalse([entry for entry in record["binding_ledger"]
                          if entry["state"] == "unconsumed"])
        current_provenance = current["execution_record"]["provenance"]
        for key in ("metric_ref", "input_snapshot_ref", "as_of"):
            self.assertEqual(current_provenance[key],
                             record["provenance"][key], key)
        for key in ("consumed_depth", "max_depth", "operator_calls",
                    "max_operator_calls", "segments_examined", "max_segments",
                    "hypotheses_examined", "max_hypotheses"):
            self.assertIn(key, record["budget"], key)
        _, again = run_question("7월 매출은?", self.contexts, route="c4_level")
        self.assertEqual(record["plan_hash"],
                         again["execution_record"]["plan_hash"])

    def test_non_level_is_refused_never_silently_replaced(self):
        for question in ("7월 매출이 왜 변했나?",
                         "2026-06-25 계획 대비 7월 매출 어때?"):
            with self.subTest(question=question):
                _, refused = run_question(question, self.contexts,
                                          route="c4_level")
                self.assertEqual(["route"], sorted(refused["results"]))
                violation = refused["results"]["route"]["violated"][0]
                self.assertEqual("route_capability", violation["check"])
                self.assertIsNone(refused["execution_record"])

    def test_explicit_fallback_matches_current_route_exactly(self):
        for question in ("7월 매출이 왜 변했나?", "작년 대비 7월 매출은?",
                         "2026-06-25 계획 대비 7월 매출 어때?"):
            with self.subTest(question=question):
                _, current = run_question(question, self.contexts)
                _, fallback = run_question(question, self.contexts,
                                           route="c4_level_or_current")
                self.assertEqual(current, fallback)

    def test_result_and_report_workflows_ignore_the_selector(self):
        _, prior = run_question("7월 매출은?", self.contexts, route="c4_level")
        for route in ("current", "c4_level"):
            envelope, bundle = run_question(
                "이 결과를 경영진 메모로 작성해줘", self.contexts,
                report_context=prior, route=route)
            self.assertEqual("spec", envelope["status"])
            self.assertEqual("result", bundle["results"]["report"]["status"])

    def test_h2_enforced_corpus_has_routed_parity(self):
        path = (Path(__file__).parent.parent / "eval" / "semantic-layer-v1"
                / "cases.json")
        for case in json.loads(path.read_text()):
            with self.subTest(case=case["id"]):
                envelope, current = run_question(case["question"], self.contexts)
                routed_envelope, routed = run_question(
                    case["question"], self.contexts,
                    route="c4_level_or_current")
                self.assertEqual(envelope["status"], routed_envelope["status"])
                if current is None:
                    self.assertIsNone(routed)
                    continue
                family = envelope["query_spec"]["intent"]["operation_family"]
                if family != "inspect_level":
                    self.assertEqual(current, routed)
                    continue
                cv, rv = self.views(current, routed)
                self.assertEqual(cv["status"], rv["status"])
                if cv["status"] == "result":
                    self.assertEqual(cv["view"]["scalar"]["value"],
                                     rv["view"]["scalar"]["value"])

    def test_golden_level_cases_hold_normalized_expectations_on_c4_route(self):
        expectations = {
            "sales-level-total": ("7월 매출은?", 3860),
            "sales-level-online": ("7월 온라인 매출은?", 1580),
            "loss-ratio-level": ("7월 보험 손해율은?", 0.66),
        }
        for case_id, (question, expected) in expectations.items():
            with self.subTest(case=case_id):
                _, routed = run_question(question, self.contexts,
                                         route="c4_level")
                view = adapt_result(routed["results"]["level"], "level")["view"]
                self.assertEqual(expected, view["scalar"]["value"])
                self.assertEqual(["data_confirmed"], view["label_capabilities"])
        # 손해율의 분자·분모·집계 규칙은 canonical 값 계약 안에 보존된다.
        _, routed = run_question("7월 보험 손해율은?", self.contexts,
                                 route="c4_level")
        aggregation = routed["results"]["level"]["value"]["aggregation"]
        self.assertEqual("denominator_weighted_mean", aggregation["rule"])
        self.assertEqual(132, aggregation["components"]["numerator"])
        self.assertEqual(200, aggregation["components"]["denominator"])


if __name__ == "__main__":
    unittest.main()
