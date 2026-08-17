"""E-023 — 주간 calendar 등록: 주차 질의의 정식 게이트 통과.

지난 ad-hoc 주차 분석(게이트 밖 원장 직접 계산)과 같은 수치를, 이번에는
등록 window·완결성·항등식 게이트를 전부 통과한 경로에서 얻는다. 월간 시점
원천(재고·활성 고객)의 주간 질의는 grain 게이트가 이름을 밝혀 거부한다.
"""
import unittest
from pathlib import Path

from catalog import load_metric_catalog
from demo import demo_question

try:
    import duckdb
    HAS_DUCKDB = True
except ModuleNotFoundError:
    HAS_DUCKDB = False

DB_PATH = Path(__file__).parent / "store" / "groot.duckdb"

# ad-hoc 분석(주차별 차트)에서 수동 계산했던 참조값 — 이제 게이트가 보증한다.
W29_TOTAL_U = 832
W28_TO_W29 = {"식품": -8, "생활용품": -39, "뷰티": -11, "가전": -68}


class E023WeeklyWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()

    def demo(self, question):
        return demo_question(question, contexts=self.contexts)

    def test_weekly_level_passes_all_gates(self):
        outcome = self.demo("W29 매출은?")
        self.assertEqual("executed", outcome["stage"], outcome)
        self.assertEqual("result", outcome["execution"]["status"])
        selected = next(iter(outcome["execution"]["outputs"].values()))
        self.assertEqual(W29_TOTAL_U, selected["value"])
        window = selected["envelope"]["value"]["slice"]["time_window"]
        self.assertEqual({"kind": "iso_week", "period": "2026-W29"}, window)

    def test_week_ordinal_phrasing_binds_to_the_same_week(self):
        outcome = self.demo("29주차 매출은?")
        self.assertEqual("executed", outcome["stage"], outcome)
        selected = next(iter(outcome["execution"]["outputs"].values()))
        self.assertEqual(W29_TOTAL_U, selected["value"])

    def test_partial_week_suspends_with_completeness_reason(self):
        outcome = self.demo("W31 매출은?")
        self.assertEqual("executed", outcome["stage"])
        self.assertEqual("suspended", outcome["execution"]["status"])
        result = next(iter(outcome["execution"]["results"].values()))
        self.assertIn("5/7일", result["missing_inputs"][0])

    def test_weekly_on_monthly_source_is_a_named_grain_refusal(self):
        for question in ("W29 재고는?", "W29 활성 고객 수는?"):
            with self.subTest(question=question):
                outcome = self.demo(question)
                self.assertEqual("executed", outcome["stage"])
                self.assertEqual("out_of_domain",
                                 outcome["execution"]["status"])
                result = next(iter(
                    outcome["execution"]["results"].values()))
                self.assertEqual("window_registered",
                                 result["violated"][0]["check"])
                self.assertIn("not registered",
                              result["violated"][0]["detail"])

    def test_weekly_change_decomposes_with_closed_identity(self):
        outcome = self.demo("W28 대비 W29 매출이 왜 변했나?")
        self.assertEqual("executed", outcome["stage"], outcome)
        self.assertEqual("result", outcome["execution"]["status"])
        by_axis = {result["group_by"]: result
                   for result in outcome["execution"]["outputs"].values()}
        self.assertEqual({"channel", "category", "customer_type"},
                         set(by_axis))
        category = by_axis["category"]
        self.assertEqual(-126, category["total"]["delta"])
        self.assertEqual(W28_TO_W29,
                         {row["segment"]: row["delta"]
                          for row in category["segments"]})
        # 항등식: 세그먼트 합 = 전체 Δ (contribution_identity 게이트 통과 결과)
        for axis, result in by_axis.items():
            self.assertEqual(result["total"]["delta"],
                             sum(row["delta"] for row in result["segments"]),
                             axis)

    def test_weekly_without_baseline_requires_explicit_comparison(self):
        # 주간 target에는 월 산술 기본값(전월)을 적용하지 않는다 — 명시 요구.
        outcome = self.demo("W29 매출이 왜 변했나?")
        self.assertEqual("intent", outcome["stage"])
        self.assertEqual("out_of_domain", outcome["compiled"]["status"])
        self.assertTrue(any("baseline" in item.get("detail", "")
                            for item in outcome["compiled"]["violated"]))

    def test_monthly_paths_are_untouched(self):
        outcome = self.demo("7월 매출은?")
        selected = next(iter(outcome["execution"]["outputs"].values()))
        self.assertEqual(3860, selected["value"])
        window = selected["envelope"]["value"]["slice"]["time_window"]
        self.assertEqual({"kind": "month", "period": "2026-07"}, window)


@unittest.skipUnless(HAS_DUCKDB and DB_PATH.exists(),
                     "duckdb backend not built (.venv + build_duckdb.py)")
class E023SqlCrossCheckTest(unittest.TestCase):
    """pushdown 증분 0 — SQL lowering이 연산자와 같은 수를 내는지 대조.

    실행 권위는 아직 결정론 연산자에 있다. 이 게이트는 동일 estimand의 SQL
    표현이 값 동일함을 증명해, 이후 pushdown 증분의 발판을 만든다.
    """

    @classmethod
    def setUpClass(cls):
        cls.connection = duckdb.connect(str(DB_PATH), read_only=True)
        cls.contexts = load_metric_catalog("metric_catalog.duckdb.json")

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def sql_one(self, query):
        return self.connection.execute(query).fetchone()[0]

    def test_weekly_total_matches_operator_result(self):
        outcome = demo_question("W29 매출은?", contexts=self.contexts)
        operator_value = next(iter(
            outcome["execution"]["outputs"].values()))["value"]
        sql_value = self.sql_one("""
            SELECT SUM(sales_u) FROM sales_ledger
            WHERE strftime(CAST(date AS DATE), '%G-W%V') = '2026-W29'
        """)
        self.assertEqual(operator_value, sql_value)
        self.assertEqual(W29_TOTAL_U, sql_value)

    def test_weekly_category_deltas_match_operator_segments(self):
        outcome = demo_question("W28 대비 W29 매출이 왜 변했나?",
                                contexts=self.contexts)
        category = next(result for result
                        in outcome["execution"]["outputs"].values()
                        if result["group_by"] == "category")
        sql_rows = self.connection.execute("""
            WITH weekly AS (
                SELECT category,
                       strftime(CAST(date AS DATE), '%G-W%V') AS week,
                       SUM(sales_u) AS total
                FROM sales_ledger GROUP BY 1, 2)
            SELECT after.category, after.total - before.total
            FROM weekly AS after JOIN weekly AS before
              ON after.category = before.category
            WHERE after.week = '2026-W29' AND before.week = '2026-W28'
        """).fetchall()
        self.assertEqual(
            {row["segment"]: row["delta"] for row in category["segments"]},
            dict(sql_rows))

    def test_monthly_level_matches_operator_result(self):
        sql_value = self.sql_one(
            "SELECT SUM(sales_u) FROM sales_ledger WHERE month = '2026-07'")
        self.assertEqual(3860, sql_value)


if __name__ == "__main__":
    unittest.main()
