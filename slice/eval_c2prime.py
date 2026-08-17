"""C2′ 증분 2 — H2 corpus에서 advisory(자유 실행) 대 계약-아래-LLM 비교.

C2′ = local LLM이 절 바인딩을 제안하고, 검증·컴파일·산술은 결정론 계약이
수행하는 조건. v4의 C1 advisory(문서 열람 + 자유 실행 agent)와 같은 10사례
corpus에서 분석 구간(해석→실행) 결과를 채점한다.

측정 모드 주의: plan 비교 등 미라우팅 capability도 shadow executor로 실행해
채점한다(E-017이 parity를 검증한 범위). 이는 측정이지 라우팅 승격이 아니다.
persistence·reporting은 계약 경로에서 결정론(E-018/019 parity 검증)이므로
LLM 효과 측정 대상이 아니며, 채점 범위를 분석 구간으로 명시 한정한다.
"""
import argparse
import json
import time
from pathlib import Path

from catalog import load_metric_catalog
from shadow_executor import execute_shadow_plan
from shadow_intent import (_has_silent_substitution, compile_shadow_intent,
                           propose_clause_bindings)

HERE = Path(__file__).parent
CASES = HERE.parent / "eval" / "semantic-layer-v1" / "cases.json"

# 정상 결과 사례의 기대 수치 (E-017 shadow parity 게이트와 동일한 정규화 기대)
EXPECTED_VALUES = {
    "scope-online-change": -220,
    "plan-vintage-pinned": -390,
    "plan-scope-online": -320,
    "level-scope-online": 1580,
    "scope-category-change": -200,
}


def score_attempt(case, compiled, contexts):
    """분석 구간 채점: 상태 정합 + 기대 수치 + 침묵 치환·오답 계수."""
    expected = case["expect"]
    row = {"case_id": case["id"], "passed": False,
           "silent_substitution": False, "wrong_value": False,
           "compile_status": compiled["status"]}

    if expected["envelope_status"] in {"clarify", "x1"}:
        row["passed"] = compiled["status"] == "clarify"
        row["outcome"] = compiled["status"]
        return row

    if compiled["status"] != "result":
        row["outcome"] = compiled["status"]
        return row

    row["silent_substitution"] = bool(_has_silent_substitution(compiled))
    executed = execute_shadow_plan(compiled["plan"], contexts=contexts)
    row["outcome"] = executed["status"]
    if executed["status"] != expected["result_status"]:
        return row

    expected_value = EXPECTED_VALUES.get(case["id"])
    if expected_value is not None:
        values = []
        for output in executed["outputs"].values():
            if output.get("total"):
                values.append(output["total"].get("delta"))
            else:
                values.append(output.get("value"))
        if expected_value not in values:
            row["wrong_value"] = executed["status"] == "result"
            return row

    row["passed"] = not row["silent_substitution"]
    return row


def run_condition(proposer, label, attempts, contexts):
    cases = json.loads(CASES.read_text())
    rows = []
    for attempt in range(1, attempts + 1):
        for case in cases:
            started = time.time()
            try:
                compiled = compile_shadow_intent(
                    case["question"], contexts=contexts, proposer=proposer)
            except ValueError as error:
                compiled = {"status": "out_of_domain", "violated": [{
                    "check": "proposal_transport", "detail": str(error)}]}
            row = score_attempt(case, compiled, contexts)
            row.update({"attempt": attempt,
                        "seconds": round(time.time() - started, 1)})
            rows.append(row)
            mark = "✓" if row["passed"] else "✗"
            print(f"{mark} #{attempt} {case['id']:<28} {row['outcome']:<14}"
                  f" sub={row['silent_substitution']}"
                  f" wrong={row['wrong_value']} {row['seconds']}s", flush=True)

    by_case = {}
    for row in rows:
        by_case.setdefault(row["case_id"], set()).add(
            (row["outcome"], row["passed"]))
    summary = {
        "condition": label,
        "attempts": attempts,
        "runs": len(rows),
        "analytical_pass": sum(row["passed"] for row in rows),
        "silent_substitutions": sum(row["silent_substitution"] for row in rows),
        "wrong_values": sum(row["wrong_value"] for row in rows),
        "unstable_cases": sorted(case_id for case_id, outcomes
                                 in by_case.items() if len(outcomes) > 1),
        "scope_note": ("분석 구간(해석→실행) 채점; persistence·reporting은 "
                       "계약 경로에서 결정론이라 제외"),
    }
    return {"summary": summary, "rows": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None,
                        help="Ollama 모델 (미지정 시 규칙 제안자 기준선)")
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    contexts = load_metric_catalog()
    if args.model:
        from llm_intent_adapter import make_llm_proposer
        proposer = make_llm_proposer(model=args.model)
        label = f"c2prime:{args.model}"
    else:
        proposer = propose_clause_bindings
        label = "c2prime:rule-baseline"

    result = run_condition(proposer, label, args.attempts, contexts)
    summary = result["summary"]
    print(f"\n{label}: 분석 통과 {summary['analytical_pass']}/{summary['runs']}"
          f" · 침묵 치환 {summary['silent_substitutions']}"
          f" · 오답 수치 {summary['wrong_values']}"
          f" · 불안정 사례 {summary['unstable_cases'] or '없음'}")
    if args.out:
        Path(args.out).write_text(
            json.dumps(result, ensure_ascii=False, indent=1))
        print(f"→ {args.out}")
    return 0 if summary["silent_substitutions"] == 0 \
        and summary["wrong_values"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
