"""E-020 시연 진입점 — intent compiler → 라우팅된 executor 게이트."""
import unittest

from catalog import load_metric_catalog
from demo import ROUTED_OPERATORS, demo_question, render_demo
from engine import run_question

ADVERSARIAL_QUESTIONS = (
    "7월 평균 재고는?",
    "7월 재고 회전율은?",
    "7월 오프라인 매출 감소를 지역별로 보여줘",
    "7월 매출 감소 상위 3개 제품군만 보여줘",
    "2025년 7월 매출은?",
    "7월 매출 증가 속도가 둔화되고 있는가?",
    "7월 매출 감소가 일부 고객의 이상치 때문인가?",
    "7월 매출은 제품과 지역 중 어디에 더 집중되어 있나?",
    "7월 매출과 영업이익은 왜 엇갈렸나?",
)

CHANGE_PARAPHRASES = (
    "7월 매출이 왜 변했나?",
    "7월 매출 변화 원인은?",
    "7월 매출 감소 동인은?",
    "7월 매출이 전월 대비 어떻게 달라졌어?",
    "7월 매출 변동을 제품군별 기여로 보여줘",
)


class E020DemoGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()

    def demo(self, question):
        return demo_question(question, contexts=self.contexts)

    def test_level_demo_matches_current_route_value(self):
        outcome = self.demo("7월 매출은?")
        self.assertEqual("executed", outcome["stage"])
        self.assertEqual("result", outcome["execution"]["status"])
        selected = next(iter(outcome["execution"]["outputs"].values()))
        _, current = run_question("7월 매출은?", self.contexts)
        self.assertEqual(current["results"]["level"]["value_u"],
                         selected["value"])

    def test_change_paraphrases_execute_5_of_5_on_routed_operators(self):
        for question in CHANGE_PARAPHRASES:
            with self.subTest(question=question):
                outcome = self.demo(question)
                self.assertEqual("executed", outcome["stage"], outcome)
                self.assertEqual("result", outcome["execution"]["status"])
                plan = outcome["compiled"]["plan"]
                self.assertEqual("explain_change",
                                 plan.metadata["operation_family"])
                self.assertTrue({call.operator_ref for call in plan.calls}
                                <= ROUTED_OPERATORS)

    def test_demo_change_agrees_with_query_spec_route(self):
        outcome = self.demo("7월 매출 변동을 제품군별 기여로 보여줘")
        self.assertEqual("executed", outcome["stage"])
        contribution = next(
            result for result in outcome["execution"]["outputs"].values()
            if result.get("group_by") == "category")
        _, routed = run_question("7월 매출이 왜 변했나?", self.contexts,
                                 route="c4")
        spec_route = routed["results"]["contrib:category"]["value"]
        self.assertEqual(spec_route["total"]["delta"],
                         contribution["total"]["delta"])
        self.assertEqual(
            {row["segment"]: row["delta"] for row in spec_route["segments"]},
            {row["segment"]: row["delta"]
             for row in contribution["segments"]})

    def test_adversarial_corpus_reproduces_through_demo(self):
        # E-025에서 rank(색인 3)가 라우팅 승격되어 executed로 이동했다.
        expected_stages = {
            0: ("intent", "out_of_domain"),
            1: ("intent", "out_of_domain"),
            2: ("executed", "result"),
            3: ("executed", "result"),
            4: ("executed", "suspended"),
            5: ("intent", "out_of_domain"),
            6: ("intent", "out_of_domain"),
            7: ("intent", "out_of_domain"),
            8: ("route", None),
        }
        for index, question in enumerate(ADVERSARIAL_QUESTIONS):
            with self.subTest(index=index, question=question):
                outcome = self.demo(question)
                stage, detail = expected_stages[index]
                self.assertEqual(stage, outcome["stage"], outcome)
                if stage == "intent":
                    self.assertEqual(detail, outcome["compiled"]["status"])
                elif stage == "executed":
                    self.assertEqual(detail, outcome["execution"]["status"])
                else:
                    violation = outcome["route_refusal"]["violated"][0]
                    self.assertEqual("route_capability", violation["check"])
                    self.assertNotIn("execution", outcome)

    def test_unrouted_capability_is_named_not_substituted(self):
        # E-025 이후 미라우팅 잔여는 plan_gap·align_metrics다.
        outcome = self.demo("7월 매출과 영업이익은 왜 엇갈렸나?")
        detail = outcome["route_refusal"]["violated"][0]["detail"]
        self.assertIn("align_metrics@v1", detail)
        self.assertNotIn("execution", outcome)

    def test_render_covers_all_stage_shapes(self):
        for question in ("7월 매출은?",
                         "7월 매출과 영업이익은 왜 엇갈렸나?",
                         "7월 평균 재고는?",
                         "2025년 7월 매출은?"):
            with self.subTest(question=question):
                text = render_demo(self.demo(question), show_plan=True)
                self.assertIn("① 절 바인딩 대장", text)
                self.assertIn("②", text)

    def test_suspended_execution_renders_resume_conditions(self):
        text = render_demo(self.demo("2025년 7월 매출은?"))
        self.assertIn("[SUSPENDED]", text)
        self.assertIn("재개 조건", text)

    def test_default_engine_route_is_untouched_by_demo_module(self):
        _, bundle = run_question("7월 매출은?", self.contexts)
        self.assertEqual(3860, bundle["results"]["level"]["value_u"])
        self.assertNotIn("envelope_version", bundle["results"]["level"])


if __name__ == "__main__":
    unittest.main()
