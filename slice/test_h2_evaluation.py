"""H2 condition packet, normalized trace와 단계별 scorer 테스트."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from eval_h2 import (_trace_paths, _write_packets, _write_scores, build_packet, case_by_id,
                     collect_enforced_trace, compare_paired, score_trace, summarize)


class H2EvaluationTest(unittest.TestCase):
    def test_condition_packets_expose_distinct_capabilities(self):
        raw = build_packet("raw", "level-scope-online")
        advisory = build_packet("advisory", "level-scope-online")
        enforced = build_packet("enforced", "level-scope-online")
        self.assertNotIn("slice/semantic.json", raw["capability"]["allowed_resources"])
        self.assertIn("slice/semantic.json", advisory["capability"]["allowed_resources"])
        self.assertNotIn("docs/", advisory["capability"]["allowed_resources"])
        self.assertIn("eval/", advisory["capability"]["prohibited_resources"])
        self.assertEqual(["question", "engine.run_question", "result_envelope"],
                         enforced["capability"]["allowed_resources"])
        template = raw["trace_template"]["observation"]
        self.assertEqual(
            {"metric_id", "metric_version", "operation_family", "scope",
             "focal_period", "comparison"}, set(template["binding"]))
        self.assertEqual(
            {"result_key", "result_status", "primary_value", "values", "gates", "budget"},
            set(template["execution"]))

    def test_enforced_success_trace_passes_observed_stages(self):
        case = case_by_id("scope-online-change")
        scored = score_trace(collect_enforced_trace(case))
        self.assertTrue(scored["passed"], scored)
        for stage in ("resolution", "binding", "selection", "execution", "persistence", "reporting"):
            self.assertEqual("pass", scored["stages"][stage]["status"])
        self.assertTrue(scored["reporting_observed"])

    def test_early_clarification_has_only_applicable_stages(self):
        case = case_by_id("plan-vintage-missing")
        scored = score_trace(collect_enforced_trace(case))
        self.assertTrue(scored["passed"], scored)
        self.assertEqual("pass", scored["stages"]["resolution"]["status"])
        self.assertEqual("not_applicable", scored["stages"]["binding"]["status"])
        self.assertEqual("not_applicable", scored["stages"]["execution"]["status"])
        self.assertEqual("not_applicable", scored["stages"]["reporting"]["status"])

    def test_enforced_reporting_records_reporter_sources_and_lint(self):
        case = case_by_id("level-scope-online")
        trace = collect_enforced_trace(case)
        reporting = trace["observation"]["reporting"]
        self.assertEqual("result", reporting["report_status"])
        self.assertTrue(reporting["lint_passed"])
        self.assertEqual(
            [{"value": 1580, "source_ref": "results.level.value_u"}],
            reporting["numeric_claims"],
        )

    def test_binding_error_is_localized(self):
        case = case_by_id("scope-online-change")
        trace = collect_enforced_trace(case)
        trace["observation"]["binding"]["scope"] = {}
        scored = score_trace(trace)
        self.assertFalse(scored["passed"])
        self.assertEqual("fail", scored["stages"]["binding"]["status"])
        self.assertEqual("pass", scored["stages"]["execution"]["status"])

    def test_prohibited_resource_invalidates_condition(self):
        case = case_by_id("level-scope-online")
        trace = collect_enforced_trace(case)
        trace["access_log"].append("slice/data/ledger.csv")
        scored = score_trace(trace)
        self.assertFalse(scored["passed"])
        self.assertFalse(scored["capability"]["passed"])

    def test_reporting_requires_sources_and_forbids_causal_verdict(self):
        case = case_by_id("level-scope-online")
        trace = collect_enforced_trace(case)
        trace["observation"]["reporting"] = {
            "numeric_claims": [{"value": 1580, "source_ref": None}],
            "causal_claims": ["온라인 정책 때문에 감소했다"],
            "label_violations": [],
        }
        scored = score_trace(trace)
        self.assertEqual("fail", scored["stages"]["reporting"]["status"])

    def test_reporting_allows_bounded_causal_alignment(self):
        case = case_by_id("level-scope-online")
        trace = collect_enforced_trace(case)
        trace["condition"] = "advisory"
        trace["access_log"] = ["question", "slice/data/ledger.csv"]
        trace["observation"]["reporting"] = {
            "numeric_claims": [{"value": 1580, "source_ref": "slice/data/ledger.csv"}],
            "causal_claims": ["행사와 정합하지만 원인으로 확정할 수 없다"],
            "label_violations": [],
        }
        scored = score_trace(trace)
        self.assertEqual("pass", scored["stages"]["reporting"]["status"])

    def test_advisory_operator_version_suffix_is_normalized(self):
        trace = collect_enforced_trace(case_by_id("level-scope-online"))
        trace["condition"] = "advisory"
        trace["access_log"] = ["question", "slice/data/ledger.csv"]
        trace["observation"]["selection"]["selected_operators"] = ["metric_level@v1"]
        scored = score_trace(trace)
        self.assertEqual("pass", scored["stages"]["selection"]["status"])

    def test_raw_reporting_does_not_require_enforced_report_wrapper(self):
        case = case_by_id("level-scope-online")
        trace = collect_enforced_trace(case)
        trace["condition"] = "raw"
        trace["access_log"] = ["question", "slice/data/ledger.csv"]
        trace["observation"]["reporting"] = {
            "numeric_claims": [{"value": 1580, "source_ref": "slice/data/ledger.csv"}],
            "causal_claims": [], "label_violations": [],
        }
        scored = score_trace(trace)
        self.assertEqual("pass", scored["stages"]["reporting"]["status"])

    def test_raw_execution_scores_primary_value_not_enforced_bundle_key(self):
        case = case_by_id("level-scope-online")
        trace = collect_enforced_trace(case)
        trace["condition"] = "raw"
        trace["access_log"] = ["question", "slice/data/ledger.csv"]
        trace["observation"]["execution"] = {
            "result_key": "agent_defined_name", "result_status": "success",
            "primary_value": 1580, "values": {"sales_u": 1580},
            "gates": [], "budget": None,
        }
        scored = score_trace(trace)
        self.assertEqual("pass", scored["stages"]["execution"]["status"])

    def test_batch_packets_cover_requested_conditions_cases_and_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_packets(Path(directory), ["raw", "advisory"], attempts=2)
            self.assertEqual(40, len(paths))
            self.assertTrue(Path(directory, "raw", "scope-online-change__01.json").exists())
            self.assertTrue(Path(directory, "advisory", "unknown-metric__02.json").exists())

    def test_summary_lists_stage_failures_by_case_and_attempt(self):
        trace = collect_enforced_trace(case_by_id("level-scope-online"))
        trace["observation"]["binding"]["scope"] = {}
        summary = summarize([score_trace(trace)])
        self.assertEqual(
            ["level-scope-online#1"],
            summary["enforced"]["stage_failures"]["binding"],
        )

    def test_summary_counts_invalid_trace_in_denominator(self):
        valid = collect_enforced_trace(case_by_id("level-scope-online"))
        valid["condition"] = "raw"
        valid["access_log"] = ["question", "slice/data/ledger.csv"]
        wrapped = {"condition": "raw", "trace_template": copy.deepcopy(valid)}
        summary = summarize([score_trace(valid), score_trace(wrapped)])
        self.assertEqual(2, summary["raw"]["traces"])
        self.assertEqual(1, summary["raw"]["valid_traces"])
        self.assertEqual(1, summary["raw"]["invalid_traces"])
        self.assertEqual(["level-scope-online#1"], summary["raw"]["invalid_trace_ids"])

    def test_paired_comparison_uses_invalid_trace_as_full_failure(self):
        raw = collect_enforced_trace(case_by_id("level-scope-online"))
        raw["condition"] = "raw"
        raw["access_log"] = ["question", "slice/data/ledger.csv"]
        advisory = copy.deepcopy(raw)
        advisory["condition"] = "advisory"
        invalid_raw = score_trace({"condition": "raw", "trace_template": raw})
        compared = compare_paired([invalid_raw, score_trace(advisory)])
        self.assertEqual(1, compared["matched_pairs"])
        self.assertEqual(1, compared["fully_passed"]["improved"])
        self.assertEqual(1, compared["stages"]["resolution"]["improved"])
        self.assertEqual(0, compared["stages"]["resolution"]["excluded_invalid_pairs"])

    def test_trace_paths_exclude_runner_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("raw__case__01.json", "raw__case__01.score.json",
                         "raw__case__01.audit.json", "batch-summary.json"):
                (root / name).write_text("{}")
            self.assertEqual(
                ["raw__case__01.json"],
                [path.name for path in _trace_paths(root)],
            )

    def test_write_scores_refreshes_derived_score(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = collect_enforced_trace(case_by_id("level-scope-online"))
            trace_path = root / "enforced__level-scope-online__01.json"
            trace_path.write_text(json.dumps(trace))
            rows = _write_scores(root)
            self.assertEqual(1, len(rows))
            self.assertTrue((root / "enforced__level-scope-online__01.score.json").exists())


if __name__ == "__main__":
    unittest.main()
