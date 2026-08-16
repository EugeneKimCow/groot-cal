"""H2 조건 workspace와 Codex JSONL trace parser 테스트."""
import json
import tempfile
import unittest
from pathlib import Path

from eval_h2 import build_packet
from run_h2_isolated import (build_prompt, parse_trace_from_jsonl,
                             prepare_condition_workspace, select_packet_paths,
                             summarize_usage, verify_project_denied)


class H2IsolatedRunnerTest(unittest.TestCase):
    def test_raw_workspace_contains_data_but_not_semantic_or_eval(self):
        with tempfile.TemporaryDirectory() as parent:
            workspace, manifest = prepare_condition_workspace("raw", parent=parent)
            self.assertTrue((workspace / "slice/data/ledger.csv").exists())
            self.assertFalse((workspace / "slice/semantic.json").exists())
            self.assertFalse((workspace / "eval").exists())
            self.assertNotIn("docs/golden-set-v1.md", manifest["copied_files"])

    def test_advisory_workspace_is_allowlisted_not_whole_docs(self):
        with tempfile.TemporaryDirectory() as parent:
            workspace, manifest = prepare_condition_workspace("advisory", parent=parent)
            self.assertTrue((workspace / "slice/semantic.json").exists())
            self.assertTrue((workspace / "docs/report-contract-v0.md").exists())
            self.assertFalse((workspace / "docs/golden-set-v1.md").exists())
            self.assertFalse((workspace / "docs/exemplars-v0.md").exists())

    def test_seatbelt_allows_workspace_and_denies_project(self):
        with tempfile.TemporaryDirectory() as parent:
            workspace, _ = prepare_condition_workspace("raw", parent=parent)
            result = verify_project_denied(workspace)
            if result["allowed_returncode"] == 71 and result["prohibited_returncode"] == 71:
                self.skipTest("현재 실행 환경이 중첩 macOS Seatbelt를 허용하지 않음")
            self.assertTrue(result["passed"], result)

    def test_jsonl_parser_extracts_last_agent_message(self):
        trace = {"trace_version": "1", "condition": "raw"}
        stream = "\n".join([
            json.dumps({"type": "thread.started"}),
            json.dumps({"type": "item.completed", "item": {
                "type": "agent_message", "text": json.dumps(trace)}}),
        ])
        self.assertEqual(trace, parse_trace_from_jsonl(stream))

    def test_prompt_contains_only_allowlisted_resource_payload(self):
        with tempfile.TemporaryDirectory() as parent:
            workspace, manifest = prepare_condition_workspace("raw", parent=parent)
            packet = build_packet("raw", "level-scope-online")
            prompt = build_prompt(packet, "test-model", workspace, manifest)
            self.assertIn("slice/data/ledger.csv", prompt)
            self.assertIn("slice/plan_vintage.json", prompt)
            self.assertNotIn("docs/golden-set-v1.md", prompt)
            self.assertLess(prompt.index("허용 resource payload"),
                            prompt.index("이번 실행 assignment"))

    def test_batch_packet_selection_is_condition_scoped_and_sorted(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent)
            (root / "raw").mkdir()
            (root / "advisory").mkdir()
            for relative in ("raw/b__01.json", "raw/a__02.json", "advisory/c__01.json"):
                (root / relative).write_text("{}")
            selected = select_packet_paths(root, ["raw"], attempts=[1])
            self.assertEqual(["b__01.json"], [path.name for path in selected])

    def test_usage_summary_aggregates_completed_turns_by_condition(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent)
            usage = {"input_tokens": 10, "cached_input_tokens": 4,
                     "output_tokens": 3, "reasoning_output_tokens": 2}
            events = "\n".join([
                json.dumps({"type": "turn.started"}),
                json.dumps({"type": "turn.completed", "usage": usage}),
            ])
            (root / "raw__case__01.jsonl").write_text(events)
            (root / "advisory__case__01.jsonl").write_text(events)
            summary = summarize_usage(root)
            self.assertEqual(1, summary["raw"]["turns"])
            self.assertEqual(10, summary["advisory"]["input_tokens"])


if __name__ == "__main__":
    unittest.main()
