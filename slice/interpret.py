"""해석·바인딩 v0 — 샌드위치 ①~③의 계약 데모.

실제 시스템에서 이 단계는 LLM이다(§7.1의 ①~③). 이 모듈은 그 LLM이 지켜야 할 계약 —
닫힌 어휘 착지, 모호하면 전진 금지(X1/반문), 명세의 물화·반향 — 을 결정론적 바인더로
구현한 것이다. LLM 슬롯인은 이 함수의 서명을 유지한 채 내부만 교체한다.

반환도 합 타입: {"status": "spec"|"x1"|"clarify", ...}
"""
import re

from query_spec import comparison_period


def interpret(question, sem):
    dims = sem["dimensions"]

    # ── 지표 바인딩 (닫힌 어휘: 등록 지표만) ──
    metrics = sem["metric"].get("aliases", [sem["metric"]["name"]])
    hit = [m for m in metrics if m in question]
    if not hit:
        return {"status": "x1", "reason": "지표 미확정 — 질문에서 등록된 지표를 찾지 못함",
                "candidates": metrics,
                "message": f"등록된 지표는 {metrics}입니다. 어느 지표를 물으시는 건가요?"}
    metric = sem["metric"]["name"]

    # ── 기간 바인딩 ──
    m = re.search(r"(\d{1,2})월", question)
    if m:
        month_n = int(m.group(1))
        if not 1 <= month_n <= 12:
            return {"status": "clarify", "reason": "기간 범위 오류",
                    "message": "월은 1월부터 12월 사이로 지정해 주세요."}
        month = f"2026-{month_n:02d}"
    elif re.search(r"(지난달|전월)", question):
        as_of = sem["question_defaults"]["as_of"]
        month = comparison_period(as_of[:7], "prior_period")
    else:
        return {"status": "clarify", "reason": "기간 미확정",
                "message": "어느 기간을 보시겠습니까? (예: 7월, 지난달)"}

    # ── 비교 기저 바인딩 ──
    if re.search(r"계획|예산|목표", question):
        basis = "plan"
    elif re.search(r"작년|전년|YoY|yoy", question):
        basis = "year_over_year"
    else:
        basis = sem["question_defaults"]["comparison_basis"]  # prior_period

    # ── 질문 유형 ──
    qtype = "change" if re.search(
        r"왜|원인|변했|변화|빠졌|늘었|줄었|증가|감소|대비|차이|달성", question) else "level"

    # ── 범위(차원 값 언급) 바인딩 — 닫힌 어휘 대조 ──
    within = {}
    for dim, spec_d in dims.items():
        found = [v for v in spec_d["values"] if v in question]
        if found:
            within[dim] = found[0] if len(found) == 1 else found

    if basis == "plan":
        vm = re.search(r"(20\d{2}-\d{2}-\d{2}).{0,8}(계획|예산|목표)|(계획|예산|목표).{0,8}(20\d{2}-\d{2}-\d{2})", question)
        vintage_id = next((g for g in (vm.groups() if vm else [])
                           if g and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", g)), None)
        if vintage_id is None:
            return {"status": "clarify", "reason": "계획 빈티지 미확정",
                    "message": "어느 시점에 확정된 계획과 비교할까요? (예: 2026-06-25 계획)"}
        comp_period = None
        operation_family = "compare_plan"
    elif basis == "year_over_year":
        vintage_id = None
        comp_period = comparison_period(month, basis)
        operation_family = "explain_change" if qtype == "change" else "inspect_level"
    elif qtype == "change":
        vintage_id = None
        comp_period = comparison_period(month, basis)
        operation_family = "explain_change"
    else:
        vintage_id = None
        comp_period = None
        basis = "none"
        operation_family = "inspect_level"

    basis_txt = {"prior_period": f"전월({comp_period}) 대비", "plan": f"계획({vintage_id}) 대비",
                 "year_over_year": f"전년 동월({comp_period}) 대비", "none": "비교 기준 없음"}[basis]
    scope_txt = ", ".join(f"{k}={v}" for k, v in within.items()) or "전체 범위"
    query_spec = {
            "spec_version": "1",
            "question": question,
            "subject": {"metric_id": sem["metric"]["id"],
                        "metric_version": sem["metric"]["version"]},
            "intent": {"operation_family": operation_family},
            "scope": within,
            "focal_period": month,
            "comparison": {"kind": basis, "period": comp_period, "vintage_id": vintage_id},
            "as_of": sem["question_defaults"]["as_of"],
            "requested_output": {"genre": "analysis_note"},
            "defaults_applied": (["comparison=prior_period"]
                                 if basis == "prior_period" and not re.search(r"전월|지난달", question)
                                 else [])}
    return {"status": "spec",
            "question": question,
            "signature": {"external_criterion": "absent" if basis == "none" else "present",
                          "question_type": qtype},
            "binding": {"metric": f"{metric}@v{sem['metric']['version']}", "month": month,
                        "comparison_basis": basis, "within": within,
                        "as_of": sem["question_defaults"]["as_of"]},
            "query_spec": query_spec,
            "echo": f"이렇게 이해했습니다 — {metric}[v{sem['metric']['version']}], {month}, {basis_txt}, {scope_txt}"}


if __name__ == "__main__":
    import json
    from pathlib import Path
    sem = json.loads((Path(__file__).parent / "semantic.json").read_text())
    for q in ["7월 매출이 왜 변했나?",
              "7월 매출 계획 대비 어때?",
              "작년 대비 7월 매출은?",
              "7월 이익이 왜 줄었지?",
              "매출 추이 좀 볼까?",
              "온라인 매출이 7월에 왜 빠졌어?"]:
        r = interpret(q, sem)
        out = r.get("echo") or f"[{r['status']}] {r['message']}"
        print(f"Q: {q}\n → {out}\n")
