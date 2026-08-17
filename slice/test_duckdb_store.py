"""DuckDB 저장소 port의 parity 게이트.

저장소 교체는 데이터 변경이 아니다: rows·semantic·input snapshot hash·엔진
번들이 legacy loader와 정확히 일치해야 한다. duckdb 미설치(시스템 python) 또는
DB 미구축 환경에서는 skip한다 — Seatbelt·Ollama 테스트와 같은 규율.
"""
import unittest
from pathlib import Path

try:
    import duckdb  # noqa: F401 — 가용성 검사만
    HAS_DUCKDB = True
except ModuleNotFoundError:
    HAS_DUCKDB = False

DB_PATH = Path(__file__).parent / "store" / "groot.duckdb"


@unittest.skipUnless(HAS_DUCKDB and DB_PATH.exists(),
                     "duckdb backend not built (.venv + build_duckdb.py)")
class DuckdbStoreParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from catalog import load_metric_catalog
        cls.legacy = load_metric_catalog("metric_catalog.json")
        cls.duck = load_metric_catalog("metric_catalog.duckdb.json")

    def test_every_metric_has_identical_semantics_and_rows(self):
        from pipeline import _input_hash
        self.assertEqual(len(self.legacy), len(self.duck))
        for legacy, duck in zip(self.legacy, self.duck):
            name = legacy["sem"]["metric"]["name"]
            with self.subTest(metric=name):
                self.assertEqual(legacy["sem"], duck["sem"])
                self.assertEqual(legacy["rows"], duck["rows"])
                self.assertEqual(_input_hash(legacy["rows"]),
                                 _input_hash(duck["rows"]))

    def test_engine_bundles_are_byte_identical_on_both_backends(self):
        from engine import run_question
        cases = (("7월 매출은?", "current"),
                 ("7월 보험 손해율은?", "current"),
                 ("7월 매출이 왜 변했나?", "c4"),
                 ("7월 말 재고는 얼마이고 6월 말 대비 어느 창고에서 증가했나?", "c4"))
        for question, route in cases:
            with self.subTest(question=question, route=route):
                _, legacy = run_question(question, self.legacy, route=route)
                _, duck = run_question(question, self.duck, route=route)
                self.assertEqual(legacy, duck)

    def test_unregistered_loader_fails_explicitly(self):
        from catalog import _load_rows
        with self.assertRaises(ValueError):
            _load_rows({"loader": "csv_guess"}, DB_PATH.parent)


if __name__ == "__main__":
    unittest.main()
