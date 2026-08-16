"""E-020 시연 진입점 — intent compiler → 라우팅된 C4 executor.

한국어 질의 한 건을 절 바인딩 대장 → 컴파일된 Plan → 실행 기록 → 증거 한정
결과의 순서로 관찰한다. 기본 CLI 경로는 바꾸지 않는다. 라우팅 승격되지 않은
capability(rank·drilldown·plan 비교·metric 정렬)는 인접 분석으로 대체하지 않고
그 이름을 밝히며 fail-closed로 끝난다 — 거부가 기능이다.
"""
from catalog import load_metric_catalog
from shadow_executor import execute_shadow_plan
from shadow_intent import compile_shadow_intent


# E-018/E-019에서 라우팅 승격된 실행 어휘. 이 밖의 연산자를 포함한 Plan은
# shadow 검증만 완료된 상태이므로 시연 경로에서 실행하지 않는다.
ROUTED_OPERATORS = frozenset({
    "evaluate_metric@v1", "delta@v1", "contribution@v1",
    "set_transition@v1", "event_overlap_scan@v1",
})


def demo_question(question, contexts=None, proposer=None):
    """질의 1건의 시연 파이프라인을 실행하고 단계별 산출물을 반환한다.

    ``proposer``로 절 바인딩 제안자를 교체할 수 있다(예: local LLM). 검증·
    컴파일·산술의 결정론 권위는 제안자와 무관하게 유지된다.
    """
    contexts = contexts or load_metric_catalog()
    compiled = compile_shadow_intent(question, contexts=contexts,
                                     proposer=proposer)
    outcome = {"question": question, "compiled": compiled,
               "interpreter": getattr(proposer, "model", None) or "rule"}
    if compiled["status"] != "result":
        outcome["stage"] = "intent"
        return outcome

    plan = compiled["plan"]
    unrouted = sorted({call.operator_ref for call in plan.calls}
                      - ROUTED_OPERATORS)
    if unrouted:
        outcome["stage"] = "route"
        outcome["route_refusal"] = {
            "status": "out_of_domain",
            "violated": [{
                "check": "route_capability", "passed": False,
                "detail": (f"미라우팅 capability {unrouted} — shadow parity는 "
                           "검증됐지만 실행 승격 전입니다. 현행 경로 실행은 "
                           "기본 CLI(route 미지정)로 가능합니다."),
            }],
        }
        return outcome

    outcome["stage"] = "executed"
    outcome["execution"] = execute_shadow_plan(plan, contexts=contexts)
    return outcome


def render_demo(outcome, show_plan=False):
    """시연 산출물을 사람이 읽는 계층 텍스트로 렌더링한다."""
    interpreter = outcome.get("interpreter", "rule")
    lines = [f"질의: {outcome['question']}  [해석: {interpreter}]"]
    compiled = outcome["compiled"]

    record = compiled.get("binding_record")
    if record is not None:
        lines.append("① 절 바인딩 대장")
        for row in sorted(record.clauses, key=lambda r: (r.start, r.end)):
            marker = {"consumed": "✓", "preserved": "○"}.get(row.state, "✗")
            detail = f"   {marker} [{row.start}:{row.end}] \"{row.source_text}\""
            if row.role:
                detail += f" → {row.role}"
            if row.value is not None:
                detail += f" = {row.value.kind}:{row.value.value}"
            if row.state not in {"consumed", "preserved"} and row.reason:
                detail += f" — {row.reason}"
            lines.append(detail)

    if outcome["stage"] == "intent":
        check = (compiled.get("violated") or [{}])[0].get("check", "clause_binding")
        lines.append(f"② 컴파일: [{compiled['status'].upper()}] {check}")
        for item in compiled.get("violated", []):
            lines.append(f"   - {item.get('detail')}")
        return "\n".join(lines)

    plan = compiled["plan"]
    lines.append(f"② Plan {compiled['plan_hash'][:18]}… "
                 f"(family: {plan.metadata.get('operation_family')})")
    if show_plan:
        for call in plan.calls:
            inputs = ", ".join(_input_summary(name, value)
                               for name, value in sorted(call.inputs.items()))
            lines.append(f"   {call.call_id}: {call.operator_ref}({inputs})")

    if outcome["stage"] == "route":
        refusal = outcome["route_refusal"]["violated"][0]
        lines.append(f"③ 라우팅: [OUT_OF_DOMAIN] {refusal['detail']}")
        return "\n".join(lines)

    executed = outcome["execution"]
    record = executed["execution_record"]
    budget = record["budget"]
    lines.append(f"③ 실행 기록: calls "
                 f"{budget['operator_calls']}/{budget['max_operator_calls']}, "
                 f"segments {budget['segments_examined']}/{budget['max_segments']}, "
                 f"provenance {len(record['provenance'])}건")
    for row in record["calls"]:
        if row["status"] != "result":
            lines.append(f"   {row['call_id']} {row['operator_ref']}: {row['status']}")

    lines.append(f"④ 결과: [{executed['status'].upper()}]")
    for key, result in executed["outputs"].items():
        lines.extend(_result_lines(key, result))
    for call_id, result in executed["results"].items():
        if result.get("status") != "result" and not any(
                key.startswith(call_id) for key in executed["outputs"]):
            lines.extend(_result_lines(call_id, result))
    return "\n".join(lines)


def _input_summary(name, value):
    kind = type(value).__name__
    if kind == "Slice":
        predicates = {dim: list(values) for dim, values in value.predicates}
        return f"{name}={value.period}{predicates if predicates else ''}"
    if kind == "Ref":
        return f"{name}→{value.call_id}"
    return f"{name}={value}"


def _result_lines(key, result):
    status = result.get("status")
    if status != "result":
        lines = [f"   {key}: [{status}]"]
        for item in result.get("violated", []):
            lines.append(f"      - {item.get('check')}: {item.get('detail')}")
        for item in result.get("missing_inputs", []):
            lines.append(f"      - 누락 입력: {item}")
        if result.get("pass_conditions"):
            lines.append(f"      - 재개 조건: {result['pass_conditions']}")
        return lines

    ceiling = result.get("label_ceiling")
    lines = []
    total = result.get("total")
    if isinstance(total, dict) and "delta" in total:
        axis = f" (축: {result['group_by']})" if result.get("group_by") else ""
        lines.append(f"   {key}{axis}: Δ={total['delta']} "
                     f"(before {total.get('before')} → after {total.get('after')}) "
                     f"[상한: {ceiling}]")
        for row in result.get("segments", [])[:4]:
            lines.append(f"      {row['segment']}: Δ={row['delta']}")
        transitions = result.get("transitions")
        if transitions:
            lines.append(f"      전이: 진입 {transitions['entrants']}, "
                         f"이탈 {transitions['exits']}, "
                         f"이동 {len(transitions['migrations'])}건")
    elif "value" in result:
        value_text = f"{result['value']} {result.get('unit') or ''}".strip()
        lines.append(f"   {key}: {value_text} [상한: {ceiling}]")
    else:
        lines.append(f"   {key}: [{status}]")
    return lines
