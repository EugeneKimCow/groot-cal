"""Query Spec v1 — 해석 결과와 실행 사이의 의미 보존 계약.

이 모듈은 자연어를 해석하지 않는다. 이미 만들어진 spec의 닫힌 식별자, scope,
기간·비교 기준을 검증하고 실행기가 그대로 소비할 수 있는 값을 제공한다.
"""
from datetime import date


def shift_month(month, offset):
    """YYYY-MM을 달력 경계를 보존하며 offset개월 이동한다."""
    year, mon = map(int, month.split("-"))
    index = year * 12 + mon - 1 + offset
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def comparison_period(focal_period, kind):
    if kind == "prior_period":
        return shift_month(focal_period, -1)
    if kind == "year_over_year":
        return shift_month(focal_period, -12)
    return None


def validate_query_spec(spec, sem, ledger=None):
    """Query Spec의 의미 정합을 합 타입으로 반환한다.

    schema 라이브러리에 의존하지 않고 실행에 중요한 불변조건을 검사한다. JSON Schema는
    외부 producer의 구조 검증용이고, 이 함수는 semantic validation의 정본이다.
    """
    if not isinstance(spec, dict):
        return {"status": "out_of_domain", "violated": [{
            "check": "query_spec_valid", "passed": False,
            "detail": "Query Spec은 object여야 함",
        }]}

    problems = []
    if spec.get("spec_version") != "1":
        problems.append("지원하지 않는 spec_version")

    subject = spec.get("subject") or {}
    metric = sem["metric"]
    if subject.get("metric_id") != metric["id"]:
        problems.append(f"metric_id 불일치: {subject.get('metric_id')} != {metric['id']}")
    if subject.get("metric_version") != metric["version"]:
        problems.append("metric version 불일치")

    focal = spec.get("focal_period")
    focal_valid = True
    try:
        if not focal or len(focal) != 7:
            raise ValueError
        year, month = map(int, focal.split("-"))
        date(year, month, 1)
    except (TypeError, ValueError):
        focal_valid = False
        problems.append(f"유효하지 않은 focal_period: {focal}")

    try:
        date.fromisoformat(spec.get("as_of", ""))
    except (TypeError, ValueError):
        problems.append(f"유효하지 않은 as_of: {spec.get('as_of')}")

    scope = spec.get("scope") or {}
    if not isinstance(scope, dict):
        problems.append("scope는 object여야 함")
        scope = {}
    for dim, value in scope.items():
        d = sem["dimensions"].get(dim)
        if d is None:
            problems.append(f"미등록 scope dimension: {dim}")
            continue
        values = value if isinstance(value, list) else [value]
        if not values or any(not isinstance(v, str) for v in values):
            problems.append(f"{dim} scope 값은 문자열 또는 비어 있지 않은 문자열 배열이어야 함")
            continue
        unknown = sorted(set(values) - set(d["values"]))
        if unknown:
            problems.append(f"{dim}의 미등록 scope 값: {unknown}")
        for required_dim, required_value in (d.get("applies_to") or {}).items():
            got = scope.get(required_dim)
            got_values = set(got if isinstance(got, list) else [got])
            if got_values != {required_value}:
                problems.append(
                    f"{dim} scope는 {required_dim}={required_value} 제약과 함께 사용해야 함")

    comp = spec.get("comparison") or {}
    if not isinstance(comp, dict):
        problems.append("comparison은 object여야 함")
        comp = {}
    kind = comp.get("kind")
    valid_kinds = {"prior_period", "year_over_year", "plan", "none"}
    if kind not in valid_kinds:
        problems.append(f"미등록 comparison kind: {kind}")
    expected = comparison_period(focal, kind) if focal_valid and kind in valid_kinds else None
    if expected and comp.get("period") != expected:
        problems.append(f"comparison period 불일치: {comp.get('period')} != {expected}")
    if kind == "plan" and not comp.get("vintage_id"):
        problems.append("계획 대비에는 vintage_id가 필요")

    family = (spec.get("intent") or {}).get("operation_family")
    valid_families = {"explain_change", "compare_plan", "inspect_level"}
    if family not in valid_families:
        problems.append(f"미등록 operation_family: {family}")
    expected_family = {
        "prior_period": "explain_change",
        "year_over_year": "explain_change",
        "plan": "compare_plan",
        "none": "inspect_level",
    }.get(kind)
    if expected_family and family != expected_family:
        problems.append(f"intent/comparison 불일치: {family} vs {kind}")

    if problems:
        return {"status": "out_of_domain", "violated": [
            {"check": "query_spec_valid", "passed": False, "detail": p} for p in problems
        ]}

    if ledger is not None:
        present = {r["month"] for r in ledger}
        required = [focal]
        if comp.get("period"):
            required.append(comp["period"])
        missing = [m for m in required if m not in present]
        if missing:
            return {"status": "suspended",
                    "missing_inputs": [f"ledger {m}" for m in missing],
                    "pass_conditions": "요청·비교 기간 원장이 적재되면 실행 가능"}

    return {"status": "result", "check": "query_spec_valid", "passed": True}
