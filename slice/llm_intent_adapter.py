"""C2′ 증분 1 — local LLM 절 바인딩 제안자 (Ollama).

LLM의 역할은 절 제안뿐이다: 질문의 어절을 닫힌 role·kind 어휘로 분류해 제안하면,
검증(`clause_binding.validate_binding_record`)·의미 호환성 강등·미소비 텍스트
실토·컴파일·산술은 전부 기존 결정론 계약이 수행한다. 등록 어휘 밖 값, 원문에
없는 텍스트, 형식 위반은 전부 fail-closed로 끝난다 — LLM은 수치를 만들지 않고
estimand를 치환할 수 없다.

외부 패키지 없이 표준 라이브러리(urllib)로 Ollama HTTP API를 호출한다.
"""
import json
import os
import re
import urllib.error
import urllib.request

from catalog import load_metric_catalog
from clause_binding import BindingValue, ClauseBinding
from query_spec import shift_month
from shadow_intent import _default_as_of, _vocabulary, finalize_clause_record
from shadow_registry import ShadowOperatorRegistry


DEFAULT_MODEL = os.environ.get("GROOT_LLM_MODEL", "qwen2.5-coder:14b")
DEFAULT_HOST = "http://localhost:11434"


class ProposalError(ValueError):
    """모델 출력·전송 실패 — 추측하지 않고 이름을 밝혀 fail-closed로 전달한다."""

ROLE_KINDS = {
    "subject": "metric_ref", "reducer": "reducer_ref",
    "time.target": "month", "time.baseline": "month",
    "filter": "predicate", "breakdown": "dimension_ref",
    "nested_breakdown": "dimension_ref", "analysis": "analysis_ref",
    "ranking": "ranking", "scenario": "scenario_ref", "output": "output_ref",
}


def make_llm_proposer(model=DEFAULT_MODEL, host=DEFAULT_HOST, transport=None):
    """compile_shadow_intent의 proposer 서명에 맞는 제안 함수를 만든다.

    ``transport(prompt) -> str``를 주입하면 네트워크 없이 시험할 수 있다.
    """
    def propose(question, contexts=None, vocabulary=None):
        contexts = contexts or load_metric_catalog()
        vocabulary = vocabulary or _vocabulary(contexts, ShadowOperatorRegistry())
        prompt = build_prompt(question, contexts, vocabulary)
        raw = (transport or _ollama_transport(model, host))(prompt)
        proposals = _parse_proposals(raw)
        clauses = _locate_and_convert(question, proposals)
        clauses = _deterministic_relative_baselines(question, clauses)
        return finalize_clause_record(question, clauses, contexts, vocabulary)

    propose.model = model
    return propose


def build_prompt(question, contexts, vocabulary):
    as_of = _default_as_of(contexts)
    metric_lines = "\n".join(
        f"  - \"{alias}\" → {ref}"
        for alias, ref in sorted(vocabulary["metric_aliases"].items()))
    dimension_lines = "\n".join(
        f"  - {name}: {sorted(values)}"
        for name, values in sorted(vocabulary["dimension_values"].items()))
    return f"""당신은 분석 질의의 절(clause) 바인딩 제안자다. 답을 계산하지 말고,
질문의 모든 조각을 아래 닫힌 어휘로만 분류해 JSON으로 제안하라. 제안은
결정론 검증기가 심사하며, 어휘 밖 값·원문에 없는 텍스트는 거부된다.

## 등록 지표 (subject → metric_ref)
{metric_lines}

## 등록 차원과 값 (filter의 dimension_ref/values, breakdown의 dimension_ref)
{dimension_lines}

## role과 value 형식 (state가 consumed/preserved일 때만 value 필수)
- subject: 지표 언급 → value=metric_ref (위 목록의 값 그대로)
- time.target: 대상 기간 "N월" → value="YYYY-MM"; 주간 "WNN"·"NN주차" →
  value="YYYY-WNN" (연도 미지정 시 {as_of[:4]}년)
- time.baseline: 비교 기간 "N월 대비"·"전월 대비"·"작년 대비"·"WNN 대비" →
  value="YYYY-MM" 또는 "YYYY-WNN"
- filter: 차원 값 언급(예: "온라인", "가전") → value={{"dimension_ref": ..., "values": [...]}}
- breakdown: "~별" 분해 축(예: "제품군별") → value=dimension_ref
- nested_breakdown: "그 안에서 ~별" → value=dimension_ref
- analysis: 분석 종류 → value ∈ level(수준 조회) | delta(변화량) |
  contribution(왜 변했나·원인·동인·감소·증가) | divergence(두 지표 엇갈림) |
  plan(계획 대비)
- ranking: "상위 N개"·"가장 큰" → value={{"measure":"contribution","order":"descending","limit":N}}
- scenario: 계획 빈티지 날짜 "YYYY-MM-DD" → value=그 날짜 문자열
- output: "보여줘"(result)·"만"(only_ranked)·"얼마이고"(target_level) →
  state="preserved", value=해당 output_ref
- reducer: "평균" 같은 명시적 집계 요구 → value ∈ sum|ratio_of_sums|distinct|time_last|time_average

## state 규칙
- consumed: 위 role로 바인딩됨 (value 필수, reason 금지)
- preserved: output처럼 표현 계층에 보존 (value 필수)
- non_semantic: 조사·어미·구두점 등 의미 없는 조각 (reason 필수, value 금지)
- ambiguous: 물어봐야 할 모호함 — 예: 계획 대비인데 빈티지 날짜 없음 →
  role="scenario", reason 필수, value 금지
- unsupported: 어휘에 없는 분석 요구(회전율·둔화·이상치 등) — role 지정,
  reason 필수, value 금지

## 규칙
1. text는 질문 원문의 연속 부분 문자열을 그대로 복사한다 (변형 금지).
2. 질문의 모든 의미 조각을 빠짐없이 분류한다. 조사도 non_semantic으로 명시한다.
3. 어휘 목록에 없는 지표·차원·값은 절대 만들지 않는다 — 모르면 unsupported.
4. "계획 대비"인데 질문에 YYYY-MM-DD 날짜가 없으면 scenario를 ambiguous로 한다.

## 예시 1
질문: "7월 온라인 매출은?"
{{"clauses": [
 {{"text": "7월", "role": "time.target", "state": "consumed", "value": "{as_of[:4]}-07"}},
 {{"text": "온라인", "role": "filter", "state": "consumed", "value": {{"dimension_ref": "channel", "values": ["온라인"]}}}},
 {{"text": "매출", "role": "subject", "state": "consumed", "value": "commerce.net_sales@v1"}},
 {{"text": "은?", "role": null, "state": "non_semantic", "reason": "조사·어미"}}
]}}

## 예시 2
질문: "6월 대비 7월 영업이익이 왜 줄었나?"
{{"clauses": [
 {{"text": "6월 대비", "role": "time.baseline", "state": "consumed", "value": "{as_of[:4]}-06"}},
 {{"text": "7월", "role": "time.target", "state": "consumed", "value": "{as_of[:4]}-07"}},
 {{"text": "영업이익", "role": "subject", "state": "consumed", "value": "finance.operating_profit@v1"}},
 {{"text": "이 ", "role": null, "state": "non_semantic", "reason": "조사"}},
 {{"text": "왜 줄었나", "role": "analysis", "state": "consumed", "value": "contribution"}},
 {{"text": "?", "role": null, "state": "non_semantic", "reason": "구두점"}}
]}}

## 이제 이 질문을 분류하라 (JSON만 출력)
질문: "{question}"
"""


def _ollama_transport(model, host):
    def call(prompt):
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 1500},
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{host}/api/chat", data=payload,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError) as error:
            raise ProposalError(f"local LLM 전송 실패({model}): {error}") from error
        return body["message"]["content"]

    return call


def _parse_proposals(raw):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProposalError(
            f"모델이 JSON 제안을 반환하지 않음: {raw[:60]!r}") from error
    rows = data.get("clauses")
    if not isinstance(rows, list):
        raise ProposalError("proposal must contain a clauses list")
    return rows


def _locate_and_convert(question, proposals):
    """텍스트를 원문 span으로 결정론 복원한다.

    원문에 없는 텍스트(환각)는 조용히 버린다 — 해당 구간은 이후
    ``_unaccounted_clauses``가 unsupported/non_semantic으로 실토하므로
    침묵 손실이 되지 않는다. 겹치는 제안은 앞선 것이 이긴다.
    """
    used = []
    clauses = []
    for row in proposals:
        text = row.get("text")
        if not isinstance(text, str) or not text:
            continue
        span = _find_span(question, text, used)
        if span is None:
            continue
        state = row.get("state")
        role = row.get("role")
        value = row.get("value")
        kind = ROLE_KINDS.get(role)
        binding_value = None
        if state in {"consumed", "preserved"} and kind is not None:
            if isinstance(value, dict) and "values" in value \
                    and isinstance(value["values"], list):
                value = {"dimension_ref": value.get("dimension_ref"),
                         "values": list(value["values"])}
            binding_value = BindingValue(kind, value)
        used.append(span)
        clauses.append(ClauseBinding(
            clause_id="pending", source_text=text,
            start=span[0], end=span[1],
            material=(state != "non_semantic"),
            state=state if state in {"consumed", "preserved", "ambiguous",
                                     "unsupported", "non_semantic"} else "unsupported",
            role=role,
            value=binding_value,
            reason=row.get("reason") if state not in {"consumed", "preserved"}
            else None,
        ))
    return clauses


def _find_span(question, text, used):
    start = 0
    while True:
        index = question.find(text, start)
        if index < 0:
            return None
        span = (index, index + len(text))
        if not any(span[0] < other[1] and other[0] < span[1] for other in used):
            return span
        start = index + 1


def _deterministic_relative_baselines(question, clauses):
    """상대 기간의 산술은 LLM에 맡기지 않는다.

    "전월/작년/전년 대비"의 baseline 월은 target에서 shift_month로 재계산해
    덮어쓴다 — 검증기는 형식만 보므로, 여기서만 잡을 수 있는 침묵 오차다.
    """
    target = next((row.value.value for row in clauses
                   if row.role == "time.target" and row.value), None)
    if target is None:
        return clauses
    result = []
    for row in clauses:
        if (row.role == "time.baseline" and row.value
                and re.search(r"전월", row.source_text)):
            row = ClauseBinding(
                row.clause_id, row.source_text, row.start, row.end,
                row.material, row.state, row.role,
                BindingValue("month", shift_month(target, -1)), row.target_refs,
                row.reason)
        elif (row.role == "time.baseline" and row.value
                and re.search(r"작년|전년", row.source_text)):
            row = ClauseBinding(
                row.clause_id, row.source_text, row.start, row.end,
                row.material, row.state, row.role,
                BindingValue("month", shift_month(target, -12)), row.target_refs,
                row.reason)
        result.append(row)
    return result
