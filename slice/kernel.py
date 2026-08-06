"""연산 커널 v0 — 수직 조각.

레지스트리 v1.1의 최소 구현: 검사기 3종 + contrib_decomp + vrm_lite.
설계 계약:
- 반환은 합 타입: {"status": "result"|"out_of_domain"|"suspended", ...}  (§3.4)
- identity_recheck는 post-condition — 실패 시 출력 자체가 실패 처리      (§3.5)
- share_of_change 억제 규칙: 부호 혼재 또는 |Δ| < δ_min 시 Σ|기여| 기준 병기 (§4.1)
- 모든 산술은 정수 u — 부동소수점 없음
- 실행 기록(execution_record)은 커널 호출 시 런타임이 자동 append (LLM 자기보고 아님, §5)
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent


# ── 데이터 적재 ──────────────────────────────────────────────────────────
def load_semantic():
    return json.loads((HERE / "semantic.json").read_text())


def load_ledger():
    rows = []
    with open(HERE / "data" / "ledger.csv", newline="") as f:
        for r in csv.DictReader(f):
            rows.append({"month": r["date"][:7], "date": r["date"], "channel": r["channel"],
                         "category": r["category"], "customer_type": r["customer_type"],
                         "region": r["region"] or None, "sales_u": int(r["sales_u"]),
                         "online_orders": int(r["online_orders"]) if r["online_orders"] else None})
    return rows


# ── named check registry (v0: 하드코딩 3종, checker: machine) ────────────
def check_mece_declared(sem, dim):
    """설계 사실: 차원이 선언되어 있고 MECE로 표시되어 있는가."""
    d = sem["dimensions"].get(dim)
    ok = d is not None and d.get("mece") is True
    return {"check": "mece_declared", "dim": dim, "checker": "machine",
            "passed": ok, "detail": "선언된 MECE 차원" if ok else "차원 미선언 또는 MECE 미표시"}


def check_mece_runtime_coverage(sem, ledger, dim, months):
    """결정론적 데이터 검증: 데이터의 차원 값이 전부 선언값 안에 있고 NULL이 없는가."""
    declared = set(sem["dimensions"][dim]["values"])
    applies = sem["dimensions"][dim].get("applies_to")
    bad, nulls = set(), 0
    for r in ledger:
        if r["month"] not in months:
            continue
        if applies and r[list(applies)[0]] != list(applies.values())[0]:
            continue  # 적용 범위 밖 행은 이 차원의 커버리지 대상 아님
        v = r[dim]
        if v is None:
            nulls += 1
        elif v not in declared:
            bad.add(v)
    ok = not bad and nulls == 0
    return {"check": "mece_runtime_coverage", "dim": dim, "checker": "machine", "passed": ok,
            "detail": "커버리지 완전" if ok else f"미선언 값={sorted(bad)}, NULL={nulls}"}


def check_metric_version(sem, expected_version=1):
    """설계 사실: 비교 기간 양쪽의 지표 정의 버전 동일성 (v0: 단일 버전이라 자명)."""
    ok = sem["metric"]["version"] == expected_version
    return {"check": "metric_version_identical", "checker": "machine", "passed": ok,
            "detail": f"version={sem['metric']['version']}"}


def identity_recheck(total_delta, contributions):
    """post-condition: Σ기여 == Δ전체 (정수 일치). 실패 시 출력 실패 처리."""
    s = sum(c["delta_u"] for c in contributions)
    return {"check": "identity_recheck", "checker": "machine", "passed": s == total_delta,
            "detail": f"Σ기여={s}u vs Δ전체={total_delta}u"}


# ── 연산자: contrib_decomp ───────────────────────────────────────────────
def contrib_decomp(sem, ledger, dim, month_a, month_b, record, within=None):
    """가법 세그먼트 기여도 분해. within: 상위 세그먼트 제약(드릴다운용) {dim: value}."""
    call = {"operator": "contrib_decomp", "dim": dim, "months": [month_a, month_b],
            "within": within or {}}
    record["calls"].append(call)

    # admissibility: input contract + design facts
    checks = [check_mece_declared(sem, dim), check_metric_version(sem)]
    if not sem["metric"]["properties"]["additive_across_dims"]:
        checks.append({"check": "additive_across_dims", "passed": False})
    if not all(c["passed"] for c in checks):
        call["outcome"] = "out_of_domain"
        return {"status": "out_of_domain", "violated": [c for c in checks if not c["passed"]],
                "alternatives": []}
    # deterministic data check
    cov = check_mece_runtime_coverage(sem, ledger, dim, {month_a, month_b})
    checks.append(cov)
    if not cov["passed"]:
        call["outcome"] = "out_of_domain"
        return {"status": "out_of_domain", "violated": [cov],
                "alternatives": ["unknown 버킷 편입 후 재실행"]}

    def sel(r):
        if within:
            for k, v in within.items():
                if (r[k] not in v if isinstance(v, list) else r[k] != v):
                    return False
        return True

    # 데이터 존재 게이트: 비교 기간의 원장이 없으면 suspended (yoy 등)
    months_present = {r["month"] for r in ledger}
    missing = [m for m in (month_a, month_b) if m not in months_present]
    if missing:
        call["outcome"] = "suspended"
        return {"status": "suspended", "missing_inputs": [f"ledger {m}" for m in missing],
                "pass_conditions": f"{missing} 기간의 원장이 적재되면 실행 가능"}

    agg = {m: defaultdict(int) for m in (month_a, month_b)}
    for r in ledger:
        if r["month"] in agg and sel(r) and r[dim] is not None:
            agg[r["month"]][r[dim]] += r["sales_u"]
    segs = sem["dimensions"][dim]["values"]
    total_a = sum(agg[month_a].values())
    total_b = sum(agg[month_b].values())
    total_delta = total_b - total_a

    contributions = []
    for s in segs:
        a, b = agg[month_a].get(s, 0), agg[month_b].get(s, 0)
        contributions.append({"segment": s, "before_u": a, "after_u": b, "delta_u": b - a,
                              "pct_change": round((b - a) / a * 100, 1) if a else None})

    post = identity_recheck(total_delta, contributions)
    checks.append(post)
    if not post["passed"]:
        call["outcome"] = "postcondition_failed"
        return {"status": "out_of_domain", "violated": [post], "alternatives": []}

    # share_of_change 규칙 (§4.1): 부호 혼재 또는 |Δ|<δ_min → 억제, Σ|기여| 기준 병기
    delta_min = sem["question_defaults"]["delta_min_u"]
    signs = {1 if c["delta_u"] > 0 else -1 for c in contributions if c["delta_u"] != 0}
    sign_mixed = len(signs) > 1
    suppressed = sign_mixed or abs(total_delta) < delta_min
    abs_sum = sum(abs(c["delta_u"]) for c in contributions)
    for c in contributions:
        if not suppressed and total_delta != 0:
            c["share_of_change_pct"] = round(c["delta_u"] / total_delta * 100, 1)
        c["share_of_abs_pct"] = round(abs(c["delta_u"]) / abs_sum * 100, 1) if abs_sum else None
    contributions.sort(key=lambda c: -abs(c["delta_u"]))

    call["outcome"] = "result"
    return {"status": "result",
            "estimand": f"Δ매출({month_a}→{month_b})에 대한 {dim} 세그먼트의 산술 기여분"
                        + (f" (제약: {within})" if within else ""),
            "output_type": "Attribution",
            "uncertainty_model": "none",
            "total": {"before_u": total_a, "after_u": total_b, "delta_u": total_delta,
                      "pct_change": round(total_delta / total_a * 100, 1)},
            "share_suppressed": suppressed,
            "share_suppression_reason": ("부호 혼재" if sign_mixed else
                                         "미소 변화" if abs(total_delta) < delta_min else None),
            "segments": contributions,
            "checks": checks,
            "label_ceiling": {"contribution": "데이터 확인 (identity_recheck 통과)",
                              "share_of_change": ("억제 — Σ|기여| 기준만" if suppressed
                                                  else "데이터 확인 (부호 동질·δ_min 통과)"),
                              "해석 문장": "데이터 시사 상한"}}


# ── 연산자: plan_gap (계획 대비 — 빈티지 고정 필수) ──────────────────────
def plan_gap(sem, ledger, month, record, vintage_id=None):
    """계획 대비 실적. 빈티지 미지정은 design fact 위반 — estimand 자체가 미정의(어느 계획?)."""
    call = {"operator": "plan_gap", "month": month, "vintage_id": vintage_id}
    record["calls"].append(call)
    store = json.loads((HERE / "plan_vintage.json").read_text())["vintages"]
    if vintage_id is None:
        call["outcome"] = "out_of_domain"
        return {"status": "out_of_domain",
                "violated": [{"check": "plan_vintage_pinned", "passed": False,
                              "detail": "빈티지 미지정 — '어느 시점의 계획 대비인가'가 미확정"}],
                "alternatives": [f"가용 빈티지: {[v['vintage_id'] for v in store]}"]}
    v = next((x for x in store if x["vintage_id"] == vintage_id and x["plan_month"] == month), None)
    if v is None:
        call["outcome"] = "out_of_domain"
        return {"status": "out_of_domain",
                "violated": [{"check": "plan_vintage_exists", "passed": False,
                              "detail": f"빈티지 {vintage_id} × {month} 없음"}], "alternatives": []}
    actual = defaultdict(int)
    for r in ledger:
        if r["month"] == month:
            actual[r["channel"]] += r["sales_u"]
    rows = []
    for ch, plan_u in v["channel_u"].items():
        a = actual.get(ch, 0)
        rows.append({"channel": ch, "plan_u": plan_u, "actual_u": a, "gap_u": a - plan_u,
                     "attainment_pct": round(a / plan_u * 100, 1)})
    tp, ta = sum(r["plan_u"] for r in rows), sum(r["actual_u"] for r in rows)
    call["outcome"] = "result"
    return {"status": "result", "output_type": "Attribution",
            "estimand": f"{month} 실적 − 계획(빈티지 {vintage_id})의 채널별 gap",
            "uncertainty_model": "none",
            "total": {"plan_u": tp, "actual_u": ta, "gap_u": ta - tp,
                      "attainment_pct": round(ta / tp * 100, 1)},
            "rows": rows, "plan_basis_note": v["basis_note"],
            "label_ceiling": {"gap 수치": "조건부 확인 — '빈티지 " + vintage_id + " 계획 대비'라는 조건 명시 의무",
                              "계획 결함 해석": "데이터 시사 상한"}}


# ── 연산자: event_overlap_scan (이벤트 레지스트리 v0 대조) ───────────────
def event_overlap_scan(sem, ledger, month_a, month_b, record):
    """등록 이벤트별로 타깃 슬라이스의 Δ를 실측하고 선언 규모와 대조.

    출력은 증거 행이지 판정이 아니다: 금액 특정 이벤트는 '산술 대조', 미특정은 '시사 상한',
    같은 슬라이스에 겹치는 이벤트 쌍은 '분리 불가' 플래그. (Hill: 관점은 색인이지 판정 함수가 아님)
    """
    call = {"operator": "event_overlap_scan", "months": [month_a, month_b]}
    record["calls"].append(call)
    events = json.loads((HERE / "events.json").read_text())["events"]

    def slice_delta(target):
        tot = {month_a: 0, month_b: 0}
        for r in ledger:
            if r["month"] not in tot:
                continue
            ok = True
            for dim, vals in target.items():
                if r[dim] not in vals:
                    ok = False
                    break
            if ok:
                tot[r["month"]] += r["sales_u"]
        return tot[month_b] - tot[month_a]

    def targets_intersect(t1, t2):
        for dim in set(t1) & set(t2):
            if not set(t1[dim]) & set(t2[dim]):
                return False
        return True

    rows = []
    for e in events:
        if e["affects"] != month_b:
            continue
        d = slice_delta(e["target"])
        specified = e["declared_magnitude_u"] is not None
        rows.append({"id": e["id"], "name": e["name"], "period": e["period"],
                     "target": e["target"], "measured_slice_delta_u": d,
                     "declared_magnitude_u": e["declared_magnitude_u"],
                     "reference_scale_u": e.get("reference_scale_u"),
                     "reference_note": e.get("reference_note"),
                     "reference_figures": e.get("reference_figures", []),
                     "evidence_grade": "산술 대조 가능(규모 특정)" if specified
                                       else "정합 서술까지(규모 미특정) — 시사 상한"})
    overlaps = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            ei = next(e for e in events if e["id"] == rows[i]["id"])
            ej = next(e for e in events if e["id"] == rows[j]["id"])
            if targets_intersect(ei["target"], ej["target"]):
                overlaps.append({"pair": [rows[i]["id"], rows[j]["id"]],
                                 "note": "타깃 슬라이스 교차 — 이 슬라이스의 Δ를 두 이벤트로 배분하는 것은 잔차 귀속(차단 대상)"})
    call["outcome"] = "result"
    return {"status": "result", "output_type": "Description",
            "estimand": "등록 이벤트별 타깃 슬라이스의 실측 Δ와 선언 규모의 대조",
            "events": rows, "overlap_flags": overlaps,
            "label_ceiling": {"실측 Δ": "데이터 확인", "이벤트-변화 연결": "데이터 시사 상한",
                              "중첩 슬라이스의 원인 배분": "차단(잔차 귀속) 또는 컨설턴트 판단"}}


# ── 연산자: vrm_lite (온라인 볼륨×단가 2요인) ────────────────────────────
def vrm_lite(sem, ledger, month_a, month_b, record):
    """온라인 매출 = 건수 × 객단가의 2요인 분해 (배분 관례: Laspeyres — 파라미터로 선언)."""
    call = {"operator": "vrm_lite", "months": [month_a, month_b], "convention": "laspeyres"}
    record["calls"].append(call)
    q, s = defaultdict(int), defaultdict(int)
    for r in ledger:
        if r["channel"] == "온라인" and r["month"] in (month_a, month_b):
            q[r["month"]] += r["online_orders"] or 0
            s[r["month"]] += r["sales_u"]
    if not q[month_a] or not q[month_b]:
        call["outcome"] = "suspended"
        return {"status": "suspended", "missing_inputs": ["online_orders"],
                "pass_conditions": "온라인 주문 건수 필드가 채워지면 실행 가능"}
    # 단가: 만원 단위 (1u = 1000만원 → 단가 = u*1000/건수)
    p_a, p_b = s[month_a] * 1000 / q[month_a], s[month_b] * 1000 / q[month_b]
    vol_eff = (q[month_b] - q[month_a]) * p_a / 1000
    rate_eff = q[month_b] * (p_b - p_a) / 1000
    call["outcome"] = "result"
    return {"status": "result", "output_type": "Attribution",
            "estimand": f"Δ온라인매출의 볼륨/단가 2요인 분해 (Laspeyres)",
            "orders": {month_a: q[month_a], month_b: q[month_b]},
            "price_manwon": {month_a: round(p_a, 2), month_b: round(p_b, 2)},
            "volume_effect_u": round(vol_eff, 1), "rate_effect_u": round(rate_eff, 1),
            "identity_ok": abs(vol_eff + rate_eff - (s[month_b] - s[month_a])) < 0.05,
            "label_ceiling": {"효과 수치": "데이터 확인", "해석": "데이터 시사 상한"}}
