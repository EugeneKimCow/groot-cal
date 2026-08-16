"""E-014 centralized result normalization and label-ceiling enforcement."""
import copy
from contextlib import redirect_stdout
import inspect
from io import StringIO
import unittest

from analytical_ir import ResultEnvelope
from engine import run_question
from reporter import create_structured_report, lint_structured_report
import reporter
from result_adapter import (adapt_result, claim_ceiling,
                            label_within_ceiling)
from result_store import materialize_result
import run


class ResultAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.sales_level = run_question("7월 온라인 매출은?")
        _, cls.rate_level = run_question("7월 보험 손해율은?")
        _, cls.balance_level = run_question("7월 말 재고는?")
        _, cls.distinct_level = run_question("7월 활성 고객 수는?")
        _, cls.change = run_question("온라인 매출이 7월에 왜 빠졌어?")
        _, cls.profit_change = run_question("7월 영업이익이 왜 줄었나?")
        _, cls.plan_gap = run_question("2026-06-25 계획 대비 7월 매출 어때?")

    def view(self, bundle, key):
        adapted = adapt_result(bundle["results"][key], key)
        self.assertEqual("result", adapted["status"], adapted)
        return adapted["view"]

    def test_four_legacy_level_shapes_share_one_scalar_view(self):
        cases = (
            (self.sales_level, "level", 1580, "0.1억원(u)"),
            (self.rate_level, "level", 0.66, "ratio"),
            (self.balance_level, "level", 190, "개"),
            (self.distinct_level, "level", 5, "명"),
        )
        for bundle, key, value, unit in cases:
            with self.subTest(value=value, unit=unit):
                scalar = self.view(bundle, key)["scalar"]
                self.assertEqual(value, scalar["value"])
                self.assertEqual(unit, scalar["unit"])
                self.assertRegex(scalar["source_ref"],
                                 r"^results\.level\.(value_u|value)$")

    def test_attribution_metadata_normalizes_without_inventing_scalar(self):
        view = self.view(self.change, "contrib:customer_type")
        self.assertEqual("Attribution", view["result_type"])
        self.assertIsNone(view["scalar"])
        self.assertEqual(-220, view["change"]["value"])
        self.assertEqual("0.1억원(u)", view["change"]["unit"])
        self.assertTrue(view["change"]["segments"])
        self.assertEqual("데이터 확인", claim_ceiling(view, "arithmetic"))

    def test_commerce_typed_and_plan_change_shapes_share_one_view(self):
        cases = (
            (self.change, "contrib:customer_type", -220, "0.1억원(u)"),
            (self.profit_change, "contrib:business_unit", -60, "0.1억원(u)"),
            (self.plan_gap, "plan_gap", -390, "0.1억원(u)"),
        )
        for bundle, key, expected, unit in cases:
            with self.subTest(key=key, expected=expected):
                change = self.view(bundle, key)["change"]
                self.assertEqual(expected, change["value"])
                self.assertEqual(unit, change["unit"])
                self.assertRegex(
                    change["source_ref"],
                    r"^results\..+\.total\.(delta_u|gap_u|delta)$")

    def test_ambiguous_change_shape_fails_closed(self):
        result = copy.deepcopy(self.change["results"]["contrib:customer_type"])
        result["total"]["delta"] = result["total"]["delta_u"]
        adapted = adapt_result(result, "contrib:customer_type")
        self.assertEqual("out_of_domain", adapted["status"])
        self.assertIn("exactly one change field",
                      adapted["violated"][0]["detail"])

    def test_event_ceiling_roles_are_derived_from_result_contract(self):
        view = self.view(self.change, "events")
        self.assertEqual("데이터 시사", claim_ceiling(view, "suggestion"))
        self.assertEqual("컨설턴트 판단", claim_ceiling(view, "judgment"))
        self.assertTrue(label_within_ceiling("데이터 시사", "데이터 시사"))
        self.assertFalse(label_within_ceiling("데이터 확인", "데이터 시사"))

    def test_canonical_result_envelope_uses_the_same_view(self):
        result = ResultEnvelope(
            status="result", result_type="MetricScalar",
            value={"value": 22, "unit": "건"},
            operator_ref="evaluate_metric@v1", provenance_ref="eval:abc",
            label_ceiling="data_confirmed")
        adapted = adapt_result(result, "level")
        self.assertEqual("result", adapted["status"])
        self.assertEqual(22, adapted["view"]["scalar"]["value"])
        self.assertEqual("canonical", adapted["view"]["source_shape"])

    def test_ambiguous_or_non_numeric_scalar_fails_closed(self):
        result = copy.deepcopy(self.sales_level["results"]["level"])
        result["value"] = result["value_u"]
        ambiguous = adapt_result(result, "level")
        self.assertEqual("out_of_domain", ambiguous["status"])
        self.assertIn("exactly one", ambiguous["violated"][0]["detail"])

        result = copy.deepcopy(self.sales_level["results"]["level"])
        result["value_u"] = "1580"
        nonnumeric = adapt_result(result, "level")
        self.assertEqual("out_of_domain", nonnumeric["status"])
        self.assertIn("numeric", nonnumeric["violated"][0]["detail"])

    def test_missing_evidence_or_ceiling_fails_closed(self):
        for field in ("operator_ref", "provenance_ref", "label_ceiling"):
            with self.subTest(field=field):
                result = copy.deepcopy(self.sales_level["results"]["level"])
                result.pop(field)
                self.assertEqual(
                    "out_of_domain", adapt_result(result, "level")["status"])

    def test_adapter_is_read_only(self):
        result = copy.deepcopy(self.sales_level["results"]["level"])
        before = copy.deepcopy(result)
        adapt_result(result, "level")
        self.assertEqual(before, result)

    def test_report_generation_fails_closed_on_malformed_selected_result(self):
        bundle = copy.deepcopy(self.sales_level)
        del bundle["results"]["level"]["label_ceiling"]
        report = create_structured_report(bundle)
        self.assertEqual("out_of_domain", report["status"])
        self.assertEqual("result_normalization", report["violated"][0]["check"])

    def test_lint_blocks_arithmetic_claim_above_or_outside_ceiling(self):
        report = copy.deepcopy(create_structured_report(self.change))
        claim = next(row for row in report["claims"]
                     if row["statement_type"] == "arithmetic")
        claim["label"] = "컨설턴트 판단"
        lint = lint_structured_report(report, self.change)
        self.assertTrue(any(row["rule"] == "LBL02"
                            for row in lint["violations"]))

    def test_lint_blocks_suggestive_result_claim_promoted_to_confirmation(self):
        report = copy.deepcopy(create_structured_report(self.change))
        claim = next(row for row in report["claims"]
                     if row["statement_type"] == "suggestion")
        claim["label"] = "데이터 확인"
        lint = lint_structured_report(report, self.change)
        self.assertTrue(any(row["rule"] == "LBL02"
                            for row in lint["violations"]))

    def test_cli_uses_normalized_scalar_format_for_both_legacy_shapes(self):
        sales_output = StringIO()
        with redirect_stdout(sales_output):
            run._summary(self.sales_level)
        self.assertIn("level: result value=158.0억", sales_output.getvalue())

        rate_output = StringIO()
        with redirect_stdout(rate_output):
            run._summary(self.rate_level)
        self.assertIn("level: result value=66.0%", rate_output.getvalue())

    def test_materialization_preserves_public_payload_and_identity(self):
        before = copy.deepcopy(self.sales_level["results"]["level"])
        stored = materialize_result(
            self.sales_level, "level", created_at="2026-08-14T00:00:00Z")
        self.assertEqual(before, stored["payload"])
        self.assertEqual(before["operator_ref"], stored["operator_ref"])

    def test_downstream_level_consumers_have_no_legacy_scalar_probe(self):
        source = inspect.getsource(reporter._add_primary_claims)
        source += inspect.getsource(reporter._dominance_score)
        source += inspect.getsource(run._summary)
        self.assertNotIn("value_u", source)
        self.assertNotIn('"value" in result', source)
        self.assertNotIn("delta_u", source)
        self.assertNotIn("gap_u", source)


if __name__ == "__main__":
    unittest.main()
