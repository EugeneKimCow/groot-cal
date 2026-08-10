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


def load_ledger(path=None):
    rows = []
    with open(path or HERE / "data" / "ledger.csv", newline="") as f:
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


def _within_match(r, within):
    """within 제약 매칭 — sel과 동일 의미론(리스트/단일값)."""
    for k, v in (within or {}).items():
        if (r.get(k) not in v) if isinstance(v, list) else (r.get(k) != v):
            return False
    return True


def check_mece_runtime_coverage(sem, ledger, dim, months, within=None):
    """결정론적 데이터 검증: estimand 범위(applies_to 전 키 + within) 안에서
    차원 값이 전부 선언값이고 NULL이 없는가. 범위 밖 행의 결함으로 오발화하지 않도록
    검사 범위를 estimand에 맞춰 좁힌다."""
    declared = set(sem["dimensions"][dim]["values"])
    applies = sem["dimensions"][dim].get("applies_to") or {}
    bad, nulls = set(), 0
    for r in ledger:
        if r["month"] not in months:
            continue
        if any(r.get(k) != v for k, v in applies.items()):
            continue  # 적용 범위 밖 행은 이 차원의 커버리지 대상 아님
        if not _within_match(r, within):
            continue
        v = r[dim]
        if v is None:
            nulls += 1
        elif v not in declared:
            bad.add(v)
    ok = not bad and nulls == 0
    return {"check": "mece_runtime_coverage", "dim": dim, "checker": "machine", "passed": ok,
            "detail": "커버리지 완전" if ok else f"미선언 값={sorted(bad)}, NULL={nulls}"}


def check_partition_coverage(sem, ledger, months, within=None):
    """결정론적 데이터 검증: 가법 파티션에 참여하는 전 차원의 값 커버리지.

    분해 축이 아닌 차원의 오염(미선언 채널 등)은 축별 커버리지 검사에 걸리지 않은 채
    총계에 무표식으로 합산된다 — 어떤 축을 물었든 같은 원장이면 같은 게이트가 서도록
    파티션 전 차원을 검사한다.
    """
    dims = sem["metric"]["decomposition_identities"][0]["dimensions"]
    declared = {d: set(sem["dimensions"][d]["values"]) for d in dims}
    bad = {}
    for r in ledger:
        if r["month"] not in months or not _within_match(r, within):
            continue
        for d in dims:
            v = r.get(d)
            if v is None or v not in declared[d]:
                bad.setdefault(d, set()).add(str(v))
    ok = not bad
    return {"check": "partition_coverage", "checker": "machine", "passed": ok,
            "detail": ("파티션 차원 커버리지 완전" if ok
                       else f"오염 차원: {({d: sorted(v) for d, v in bad.items()})}")}


def check_metric_version(sem, expected_version=1):
    """설계 사실: 비교 기간 양쪽의 지표 정의 버전 동일성 (v0: 단일 버전이라 자명)."""
    ok = sem["metric"]["version"] == expected_version
    return {"check": "metric_version_identical", "checker": "machine", "passed": ok,
            "detail": f"version={sem['metric']['version']}"}


def identity_recheck(independent_delta, contributions):
    """방어 계층(defense-in-depth) post-condition: Σ기여 == 원시 스캔 총계 Δ.

    비교 기준은 raw_scope_total — 세그먼트 조립과 별도 경로의 원시 행 스캔이다.
    선행 게이트(scope/coverage/partition/residual)가 전부 통과한 정상 경로에서는
    산술적으로 실패할 수 없으며, 이 검사의 역할은 조립 경로와 스캔 경로가 갈리는
    구현 결함(기여 조립·정렬·필터 버그)의 검출이다. 범위 침묵 축소의 실제 차단은
    scope_declared·coverage_residual 게이트가 담당한다 — 이 검사를 그 근거로
    인용하지 말 것.
    """
    s = sum(c["delta_u"] for c in contributions)
    return {"check": "identity_recheck", "checker": "machine", "passed": s == independent_delta,
            "detail": f"Σ기여={s}u vs 원시 스캔 Δ={independent_delta}u (방어 계층)"}


def raw_scope_total(ledger, month, within=None):
    """독립 총계 — 분해·집계 로직과 별도 경로의 원시 행 스캔.
    차원값 검사도 세그먼트 분기도 없다: 범위(month, within) 안의 전 행 합."""
    t = 0
    for r in ledger:
        if r["month"] == month and _within_match(r, within):
            t += r["sales_u"]
    return t


def check_scope_declared(sem, dim, within):
    """설계 사실: 범위 침묵 축소의 양방향 차단.

    (정방향) applies_to가 걸린 분해 차원은 within이 그 범위로 제약되어야 estimand 성립
      — region을 within 없이 부르면 온라인·B2B가 조용히 빠진 총계가 '전사 Δ'로 라벨됨.
    (역방향) within 키 자신이 applies_to를 가지면 그 제약도 within에 함께 선언되어야 함
      — within={'region':'호남'}×channel은 정의역 밖 탈락이 '온라인 Δ0'으로 위장됨.
    미지 차원 이름은 크래시가 아니라 실패 검사로 반환(합 타입 계약 §3.4).
    """
    w = within or {}

    def pinned_to(k, v):
        got = w.get(k)
        return set(got) == {v} if isinstance(got, list) else got == v

    problems = []
    d = sem["dimensions"].get(dim)
    if d is None:
        problems.append(f"분해 차원 '{dim}' 미선언")
    else:
        for k, v in (d.get("applies_to") or {}).items():
            if not pinned_to(k, v):
                problems.append(f"'{dim}'은 {k}={v}에서만 정의 — within 제약 필요")
    for k in w:
        wd = sem["dimensions"].get(k)
        if wd is None:
            problems.append(f"within 차원 '{k}' 미선언")
            continue
        for kk, vv in (wd.get("applies_to") or {}).items():
            if not pinned_to(kk, vv):
                problems.append(f"within 차원 '{k}'은 {kk}={vv}에서만 정의 — 함께 제약 필요")
    ok = not problems
    return {"check": "scope_declared", "dim": dim, "checker": "machine", "passed": ok,
            "detail": "적용 범위 정합" if ok else "; ".join(problems)}


# ── 연산자: contrib_decomp ───────────────────────────────────────────────
def contrib_decomp(sem, ledger, dim, month_a, month_b, record, within=None):
    """가법 세그먼트 기여도 분해. within: 상위 세그먼트 제약(드릴다운용) {dim: value}."""
    call = {"operator": "contrib_decomp", "dim": dim, "months": [month_a, month_b],
            "within": within or {}}
    record["calls"].append(call)

    # admissibility: input contract + design facts
    checks = [check_mece_declared(sem, dim), check_metric_version(sem),
              check_scope_declared(sem, dim, within)]
    if not sem["metric"]["properties"]["additive_across_dims"]:
        checks.append({"check": "additive_across_dims", "passed": False})
    if not all(c["passed"] for c in checks):
        call["outcome"] = "out_of_domain"
        return {"status": "out_of_domain", "violated": [c for c in checks if not c["passed"]],
                "alternatives": (["within={...}으로 적용 범위를 제약해 재실행"]
                                 if not checks[2]["passed"] else [])}
    # 데이터 존재 게이트: 비교 기간의 원장이 없으면 suspended (yoy 등)
    months_present = {r["month"] for r in ledger}
    missing = [m for m in (month_a, month_b) if m not in months_present]
    if missing:
        call["outcome"] = "suspended"
        return {"status": "suspended", "missing_inputs": [f"ledger {m}" for m in missing],
                "pass_conditions": f"{missing} 기간의 원장이 적재되면 실행 가능"}

    # deterministic data checks — estimand 범위로 좁힌 축 커버리지 + 파티션 전 차원 커버리지
    cov = check_mece_runtime_coverage(sem, ledger, dim, {month_a, month_b}, within)
    part = check_partition_coverage(sem, ledger, {month_a, month_b}, within)
    checks += [cov, part]
    if not (cov["passed"] and part["passed"]):
        call["outcome"] = "out_of_domain"
        return {"status": "out_of_domain",
                "violated": [c for c in (cov, part) if not c["passed"]],
                "alternatives": ["unknown 버킷 편입 후 재실행"]}

    def sel(r):
        return _within_match(r, within)

    # 세그먼트 집계는 선언값만 편입, 독립 총계는 별도 경로(raw_scope_total)의 원시 스캔 —
    # 둘의 차이(coverage_residual)가 선행 게이트들이 놓친 오염의 결정론적 잔차 검출기다.
    segs = sem["dimensions"][dim]["values"]
    declared_set = set(segs)
    agg = {m: defaultdict(int) for m in (month_a, month_b)}
    for r in ledger:
        if r["month"] in agg and sel(r) and r[dim] in declared_set:
            agg[r["month"]][r[dim]] += r["sales_u"]
    indep_total = {m: raw_scope_total(ledger, m, within) for m in (month_a, month_b)}
    total_a, total_b = indep_total[month_a], indep_total[month_b]
    total_delta = total_b - total_a

    residual = {m: indep_total[m] - sum(agg[m].values()) for m in (month_a, month_b)}
    if any(residual.values()):
        call["outcome"] = "out_of_domain"
        return {"status": "out_of_domain",
                "violated": [{"check": "coverage_residual", "dim": dim, "checker": "machine",
                              "passed": False,
                              "detail": f"세그먼트 합산에서 빠진 잔차 {residual}u — "
                                        f"선행 커버리지 게이트가 놓친 NULL/미선언 값"}],
                "alternatives": ["unknown 버킷 편입 후 재실행"]}

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
                      "pct_change": round(total_delta / total_a * 100, 1) if total_a else None},
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
    # 커버리지 게이트: 계획 키 밖 채널의 실적이 침묵 탈락하면 '전사 실적' 라벨이 거짓이 된다
    unallocated = {ch: a for ch, a in actual.items() if ch not in v["channel_u"] and a != 0}
    if unallocated:
        call["outcome"] = "out_of_domain"
        return {"status": "out_of_domain",
                "violated": [{"check": "plan_channel_coverage", "checker": "machine",
                              "passed": False,
                              "detail": f"계획에 없는 채널의 실적 {unallocated}u — "
                                        f"전사 실적 집계에서 침묵 탈락 불가"}],
                "alternatives": ["계획 빈티지에 채널 추가 또는 unallocated 행 명시 후 재실행"]}
    rows = []
    for ch, plan_u in v["channel_u"].items():
        a = actual.get(ch, 0)
        rows.append({"channel": ch, "plan_u": plan_u, "actual_u": a, "gap_u": a - plan_u,
                     "attainment_pct": round(a / plan_u * 100, 1) if plan_u else None})
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
def event_overlap_scan(sem, ledger, month_a, month_b, record, events_path=None):
    """등록 이벤트별로 타깃 슬라이스의 Δ를 실측하고 선언 규모와 대조.

    출력은 증거 행이지 판정이 아니다: 금액 특정 이벤트는 '산술 대조', 미특정은 '시사 상한',
    같은 슬라이스에 겹치는 이벤트 쌍은 '분리 불가' 플래그. (Hill: 관점은 색인이지 판정 함수가 아님)
    """
    call = {"operator": "event_overlap_scan", "months": [month_a, month_b]}
    record["calls"].append(call)
    events = json.loads(Path(events_path or HERE / "events.json").read_text())["events"]

    def slice_tots(target):
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
        return tot

    def slice_delta(target):
        tot = slice_tots(target)
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
            if not targets_intersect(ei["target"], ej["target"]):
                continue
            # 차원별 교집합만으로는 공유 차원이 없는 쌍이 무조건 교차 판정됨(가짜 중첩).
            # 실측 교집합 슬라이스의 매출이 양 기간 모두 0이면 경험적으로 무의미 — 플래그 억제.
            shared = dict(ei["target"])
            for dm, vals in ej["target"].items():
                shared[dm] = (sorted(set(shared[dm]) & set(vals)) if dm in shared
                              else list(vals))
            tots = slice_tots(shared)
            if not tots[month_a] and not tots[month_b]:
                continue
            overlaps.append({"pair": [rows[i]["id"], rows[j]["id"]],
                             "shared_slice": shared,
                             "shared_slice_totals_u": tots,
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
    null_rows = 0
    for r in ledger:
        if r["channel"] == "온라인" and r["month"] in (month_a, month_b):
            if r["online_orders"] is None:
                null_rows += 1     # NULL을 0으로 삼키면 건수 과소·객단가 과대가 조용히 발생
                continue
            q[r["month"]] += r["online_orders"]
            s[r["month"]] += r["sales_u"]
    if null_rows or not q[month_a] or not q[month_b]:
        call["outcome"] = "suspended"
        return {"status": "suspended",
                "missing_inputs": [f"online_orders (NULL {null_rows}행)" if null_rows
                                   else "online_orders"],
                "pass_conditions": "온라인 주문 건수 필드가 전 행 채워지면 실행 가능"}
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
