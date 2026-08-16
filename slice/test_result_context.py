"""대화 result reference와 현재 source snapshot 연결 테스트."""
import copy
import unittest

from catalog import load_metric_catalog
from engine import run_question
from result_catalog import ResultCatalog
from result_store import materialize_result


class ResultContextTest(unittest.TestCase):
    def catalog_with_online_level(self):
        _, bundle = run_question("7월 온라인 매출은?")
        stored = materialize_result(
            bundle, "level", created_at="2026-08-14T00:00:00Z")
        catalog = ResultCatalog()
        catalog.add(stored, aliases=["latest"])
        return catalog, stored

    def test_staleness_question_requires_result_context(self):
        envelope, bundle = run_question("이 분석 결과가 아직 유효한가?")
        self.assertIsNone(bundle)
        self.assertEqual("clarify", envelope["status"])
        self.assertEqual("결과 참조 미확정", envelope["reason"])

    def test_latest_result_is_fresh_against_same_source(self):
        catalog, stored = self.catalog_with_online_level()
        envelope, bundle = run_question(
            "이 분석 결과가 아직 유효한가?", result_catalog=catalog)
        self.assertEqual("spec", envelope["status"])
        result = bundle["results"]["staleness"]
        self.assertEqual("fresh", result["staleness_status"])
        self.assertEqual(stored["result_id"], result["result_id"])

    def test_changed_current_source_marks_latest_result_stale(self):
        catalog, _ = self.catalog_with_online_level()
        contexts = copy.deepcopy(load_metric_catalog())
        contexts[0]["rows"][0]["sales_u"] += 1
        _, bundle = run_question(
            "이 분석 결과가 아직 유효한가?", contexts=contexts,
            result_catalog=catalog)
        self.assertEqual("stale", bundle["results"]["staleness"]["staleness_status"])


if __name__ == "__main__":
    unittest.main()
