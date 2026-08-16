"""Materialized result 저장과 staleness 계약 테스트."""
import tempfile
import unittest
from pathlib import Path

from engine import run_question
from result_store import (assess_staleness, load_stored_result,
                          materialize_result, save_stored_result)


class ResultStoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.bundle = run_question("7월 온라인 매출은?")

    def materialized(self, **kwargs):
        return materialize_result(
            self.bundle, "level", created_at="2026-08-14T00:00:00Z", **kwargs)

    def test_materialize_and_reload_round_trip(self):
        stored = self.materialized()
        self.assertTrue(stored["result_id"].startswith("result-"))
        self.assertEqual("metric_level@v1", stored["operator_ref"])
        with tempfile.TemporaryDirectory() as directory:
            path = save_stored_result(stored, Path(directory) / "result.json")
            self.assertEqual(stored, load_stored_result(path))

    def test_store_does_not_overwrite_different_result(self):
        stored = self.materialized()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            save_stored_result(stored, path)
            changed = {**stored, "result_id": "result-different"}
            with self.assertRaises(FileExistsError):
                save_stored_result(changed, path)

    def test_same_source_is_fresh_and_changed_source_is_stale(self):
        stored = self.materialized()
        fresh = assess_staleness(stored, stored["input_snapshot_ref"])
        stale = assess_staleness(stored, "sha256:different")
        self.assertEqual("fresh", fresh["staleness_status"])
        self.assertEqual("stale", stale["staleness_status"])

    def test_source_check_suspends_without_current_snapshot(self):
        result = assess_staleness(self.materialized())
        self.assertEqual("suspended", result["status"])

    def test_expiry_policy_uses_explicit_as_of(self):
        stored = self.materialized(
            policy="expires_at", expires_at="2026-08-15T00:00:00Z")
        self.assertEqual("fresh", assess_staleness(
            stored, as_of="2026-08-14T12:00:00Z")["staleness_status"])
        self.assertEqual("stale", assess_staleness(
            stored, as_of="2026-08-15T00:00:00Z")["staleness_status"])

    def test_immutable_snapshot_does_not_claim_current_freshness(self):
        result = assess_staleness(self.materialized(policy="immutable_snapshot"))
        self.assertEqual("immutable_snapshot", result["staleness_status"])
        self.assertIn("최신 상태 주장 아님", result["reason"])

    def test_failure_result_cannot_be_materialized(self):
        _, bundle = run_question("전년 대비 7월 매출이 왜 변했나?")
        result = materialize_result(bundle, "query_spec")
        self.assertEqual("out_of_domain", result["status"])


if __name__ == "__main__":
    unittest.main()
