"""C2′ 증분 1 — LLM 절 바인딩 제안자의 fail-closed 계약 테스트.

가짜 transport로 네트워크 없이 계약을 검증한다. 실제 Ollama 연동은 서버가
없으면 skip한다(Seatbelt 테스트와 같은 규율).
"""
import json
import unittest
import urllib.error
import urllib.request

from catalog import load_metric_catalog
from demo import demo_question
from llm_intent_adapter import DEFAULT_HOST, make_llm_proposer
from shadow_intent import compile_shadow_intent


def fake_transport(payload):
    return lambda prompt: json.dumps(payload, ensure_ascii=False)


def _ollama_available():
    try:
        with urllib.request.urlopen(f"{DEFAULT_HOST}/api/tags", timeout=2):
            return True
    except (urllib.error.URLError, OSError):
        return False


class LlmProposerContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = load_metric_catalog()

    def compile_with(self, question, payload):
        proposer = make_llm_proposer(transport=fake_transport(payload))
        return compile_shadow_intent(question, contexts=self.contexts,
                                     proposer=proposer)

    def test_valid_proposal_compiles_to_the_same_calls_as_rule_proposer(self):
        question = "7월 매출은?"
        result = self.compile_with(question, {"clauses": [
            {"text": "7월", "role": "time.target", "state": "consumed",
             "value": "2026-07"},
            {"text": "매출", "role": "subject", "state": "consumed",
             "value": "commerce.net_sales@v1"},
            {"text": "은?", "role": None, "state": "non_semantic",
             "reason": "조사"},
        ]})
        self.assertEqual("result", result["status"], result)
        rule = compile_shadow_intent(question, contexts=self.contexts)
        self.assertEqual(
            [call.to_dict() for call in rule["plan"].calls],
            [call.to_dict() for call in result["plan"].calls])

    def test_hallucinated_metric_ref_fails_closed(self):
        result = self.compile_with("7월 매출은?", {"clauses": [
            {"text": "7월", "role": "time.target", "state": "consumed",
             "value": "2026-07"},
            {"text": "매출", "role": "subject", "state": "consumed",
             "value": "finance.revenue@v9"},
        ]})
        self.assertEqual("out_of_domain", result["status"])
        self.assertEqual("clause_binding_valid", result["violated"][0]["check"])
        self.assertTrue(any("unregistered metric ref" in item["detail"]
                            for item in result["violated"]))

    def test_hallucinated_predicate_value_fails_closed(self):
        result = self.compile_with("7월 온라인 매출은?", {"clauses": [
            {"text": "7월", "role": "time.target", "state": "consumed",
             "value": "2026-07"},
            {"text": "온라인", "role": "filter", "state": "consumed",
             "value": {"dimension_ref": "channel", "values": ["모바일"]}},
            {"text": "매출", "role": "subject", "state": "consumed",
             "value": "commerce.net_sales@v1"},
        ]})
        self.assertEqual("out_of_domain", result["status"])
        self.assertTrue(any("unregistered predicate value" in item["detail"]
                            for item in result["violated"]))

    def test_text_absent_from_question_is_dropped_and_residual_is_confessed(self):
        # 환각 텍스트("작년")는 span 복원이 불가해 버려지고, 그 결과 실제
        # 질문의 미소비 조각("매출")이 unaccounted로 실토된다 — 침묵 손실 없음.
        result = self.compile_with("7월 매출은?", {"clauses": [
            {"text": "7월", "role": "time.target", "state": "consumed",
             "value": "2026-07"},
            {"text": "작년", "role": "time.baseline", "state": "consumed",
             "value": "2025-07"},
        ]})
        self.assertEqual("out_of_domain", result["status"])
        self.assertTrue(any("매출" in item["detail"]
                            for item in result["violated"]), result["violated"])

    def test_relative_baseline_month_is_recomputed_deterministically(self):
        # LLM이 "전월"을 2026-05로 잘못 산술해도 계약이 target-1로 덮어쓴다.
        result = self.compile_with("전월 대비 7월 매출이 왜 변했나?", {"clauses": [
            {"text": "전월 대비", "role": "time.baseline", "state": "consumed",
             "value": "2026-05"},
            {"text": "7월", "role": "time.target", "state": "consumed",
             "value": "2026-07"},
            {"text": "매출", "role": "subject", "state": "consumed",
             "value": "commerce.net_sales@v1"},
            {"text": "이 ", "role": None, "state": "non_semantic", "reason": "조사"},
            {"text": "왜 변했나", "role": "analysis", "state": "consumed",
             "value": "contribution"},
            {"text": "?", "role": None, "state": "non_semantic", "reason": "구두점"},
        ]})
        self.assertEqual("result", result["status"], result)
        baseline = next(row for row in result["binding_record"].clauses
                        if row.role == "time.baseline")
        self.assertEqual("2026-06", baseline.value.value)

    def test_overlapping_proposals_keep_first_and_confess_rest(self):
        result = self.compile_with("7월 매출은?", {"clauses": [
            {"text": "7월", "role": "time.target", "state": "consumed",
             "value": "2026-07"},
            {"text": "7월", "role": "time.baseline", "state": "consumed",
             "value": "2026-06"},
            {"text": "매출", "role": "subject", "state": "consumed",
             "value": "commerce.net_sales@v1"},
            {"text": "은?", "role": None, "state": "non_semantic", "reason": "조사"},
        ]})
        # 두 번째 "7월"은 원문에 더 없으므로 버려진다 — level plan으로 수렴.
        self.assertEqual("result", result["status"], result)
        self.assertEqual("inspect_level",
                         result["plan"].metadata["operation_family"])

    def test_malformed_llm_output_raises_instead_of_guessing(self):
        proposer = make_llm_proposer(transport=lambda prompt: "숫자는 3860입니다")
        with self.assertRaises(ValueError):
            proposer("7월 매출은?", self.contexts)


@unittest.skipUnless(_ollama_available(), "local Ollama server unavailable")
class LlmProposerLiveTest(unittest.TestCase):
    def test_local_model_binds_a_level_question_end_to_end(self):
        contexts = load_metric_catalog()
        proposer = make_llm_proposer()
        outcome = demo_question("7월 매출은?", contexts, proposer=proposer)
        self.assertEqual("executed", outcome["stage"], outcome)
        selected = next(iter(outcome["execution"]["outputs"].values()))
        self.assertEqual(3860, selected["value"])


if __name__ == "__main__":
    unittest.main()
