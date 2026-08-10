"""채점 하네스 — 원인 주입 시나리오에 대한 파이프라인 성능의 실측.

시뮬레이터(simulate.py)가 참 규모를 알고 심은 원인들에 대해, 커널 파이프라인이:
  A. 산술 복원   — 분해가 게이트·검산을 통과하는가 (dirty에서는 시끄럽게 거부하는가)
  B. 이벤트 귀속 — 이벤트별 타깃 슬라이스 실측 Δ가 참 효과를 얼마나 덮는가,
                   선언 규모의 신고-실현 괴리는 얼마인가 (부호 규약: 선언−참, 양수=과대 신고)
  C. 기권 정확성 — 중첩 슬라이스의 분리 정책을 계약 R04와 정합하게 채점:
                   전원 특정 → 잔차 논법 성립(R04 예외), 그 외 → 기권.
                   '전원-1' 잔차 귀속은 계약상 차단되나 시험 삼아 수행한 오차를 실측해
                   차단의 정당성을 수치로 남긴다 (separation_justified).
  D. 미끼 기각   — 참 효과 0인 등록 이벤트를 슬라이스 통상 대역으로 기각하는가
                   + 그 대역의 검정력(대역 폭/슬라이스 규모) 경고
  E. 대역 대 δ_min — 데이터 대역(이벤트 오염 이력)과 반사실 대역(truth의 base 이력)을
                   병기: 이벤트 없는 변화가 대역 안이고, 이벤트 충격이 대역을 벗어나는가
  F. 게이트 발화 — 지저분한 원장에서 커널이 시끄럽게 거부하는가 (A에 통합 기록)
  G. VRM 대조   — rate 개입 시나리오에서 vrm_lite의 단가 효과가 참 효과와 정합하는가

주의: 여기서 채점되는 기권·기각은 결정론적 정책 규칙의 채점이다.
LLM 작성층의 기권은 ⑧루프 측정에서 별도로 채점한다.

알려진 한계(정직 공개): 통상 변동 대역은 원시 월간 Δ의 median±k·MAD로, 폭이 계절
진폭에 지배되고 표본이 5개뿐이라 검정력이 낮다 — 계절조정·장기 이력 확보 전까지
대역 판정은 '설명 요구 트리거'이지 검정이 아니다.
"""
import json
import statistics
from pathlib import Path

from kernel import (load_semantic, load_ledger, contrib_decomp, event_overlap_scan,
                    vrm_lite)

HERE = Path(__file__).parent
SIM = HERE / "sim"
OUT = SIM / "out"
Q_A, Q_B = "2026-06", "2026-07"
AXES = ["channel", "category", "customer_type"]
BAND_K = 3.0
SPLIT_TOL = 0.15          # 분리 정당성 임계: 오차 ≤ 15%·|공유 Δ|


def u(x):
    return f"{x * 0.1:+.1f}억"


def u_abs(x):
    return f"{abs(x) * 0.1:.1f}억"


def monthly_deltas(ledger, months, target=None):
    def tot(m):
        t = 0
        for r in ledger:
            if r["month"] != m:
                continue
            if target:
                vals = {"channel": r["channel"], "category": r["category"],
                        "customer_type": r["customer_type"], "region": r["region"]}
                if not all(vals[k] in v for k, v in target.items()):
                    continue
            t += r["sales_u"]
        return t
    return [tot(months[i + 1]) - tot(months[i]) for i in range(len(months) - 1)]


def usual_band(deltas):
    """통상 변동 대역: median ± k·MAD (무분포 진단 — 게이트 아님, ledger 항목)."""
    med = statistics.median(deltas)
    mad = statistics.median([abs(d - med) for d in deltas]) or 1
    return med - BAND_K * mad, med + BAND_K * mad


def series_deltas(totals_by_month, months):
    return [totals_by_month[months[i + 1]] - totals_by_month[months[i]]
            for i in range(len(months) - 1)]


def score_scenario(name):
    d = SIM / name
    sem = load_semantic()
    ledger = load_ledger(d / "ledger.csv")
    truth = json.loads((d / "truth.json").read_text())
    events = json.loads((d / "events.json").read_text())["events"]
    ev_by_id = {e["id"]: e for e in events}
    truth_ev = {t["id"]: t for t in truth["events"]}
    months = sorted(truth["monthly_totals_u"])
    hist = months[:months.index(Q_B)]          # 질문 월 이전까지의 이력 (Q_A 포함)
    record = {"calls": []}
    S = {"scenario": name}

    # A. 산술 복원 / 게이트 — 3축 분해
    axes = {}
    for dim in AXES:
        r = contrib_decomp(sem, ledger, dim, Q_A, Q_B, record)
        row = {"status": r["status"]}
        if r["status"] == "result":
            row["delta_u"] = r["total"]["delta_u"]
            row["identity"] = all(c["passed"] for c in r["checks"])
            row["share_suppressed"] = r["share_suppressed"]
        else:
            row["violated"] = [c["check"] for c in r["violated"]]
        axes[dim] = row
    S["A_arithmetic"] = axes

    # F. 게이트 발화 (dirty 시나리오): 전 축 + region 드릴 + vrm + 부호 규범
    if truth.get("dirty"):
        rg = contrib_decomp(sem, ledger, "region", Q_A, Q_B, record,
                            within={"channel": "오프라인"})
        v = vrm_lite(sem, ledger, Q_A, Q_B, record)
        neg_rows = sum(1 for r in ledger if r["sales_u"] < 0)
        S["F_gates"] = {"axes_blocked": {k: a.get("violated") for k, a in axes.items()
                                         if a["status"] != "result"},
                        "region_drill_status": rg["status"],
                        "region_violated": [c["check"] for c in rg.get("violated", [])],
                        "vrm_status": v["status"],
                        "vrm_missing": v.get("missing_inputs"),
                        "negative_rows": neg_rows,
                        "negative_rows_gated": False}   # 부호 규범 미검사 — 알려진 공백
        return S  # dirty는 게이트 채점까지만

    # B. 이벤트 귀속 — 실측 Δ vs 참 효과, 선언 오차(선언−참)
    ev = event_overlap_scan(sem, ledger, Q_A, Q_B, record, events_path=d / "events.json")
    attribution = []
    for row in ev["events"]:
        te = truth_ev[row["id"]]
        true_eff = te["target_slice_delta_effect_u"]
        meas = row["measured_slice_delta_u"]
        item = {"id": row["id"], "measured_slice_delta_u": meas,
                "true_effect_u": true_eff,
                "attribution_gap_u": meas - true_eff,    # 기저 추세+타 이벤트+잡음의 몫
                "evidence_grade": row["evidence_grade"]}
        if "injected_u" in te:
            item["injected_u"] = te["injected_u"]        # 명목 주입치 (신고-실현 괴리용)
        if row["declared_magnitude_u"] is not None:
            item["declared_u"] = row["declared_magnitude_u"]
            item["declaration_error_u"] = row["declared_magnitude_u"] - true_eff
        if row["reference_scale_u"] is not None:
            item["reference_scale_u"] = row["reference_scale_u"]
            item["reference_error_pct"] = round(
                (row["reference_scale_u"] / max(1, abs(te["month_a_slice_effect_u"]
                                                       or te["month_b_slice_effect_u"])) - 1) * 100, 1)
        attribution.append(item)
    S["B_attribution"] = attribution

    # C. 기권 정확성 — 계약 R04 정합 정책 + 차단된 논법의 오차 실측
    abstention = []
    for ov in truth["overlaps"]:
        e1, e2 = ov["pair"]
        undeclared = [e for e in (e1, e2) if ev_by_id[e]["declared_magnitude_u"] is None]
        D = ov["shared_slice_delta_full_u"]
        t1, t2 = ov["true_split_u"][e1], ov["true_split_u"][e2]
        item = {"pair": ov["pair"], "shared_slice": ov["shared_slice"],
                "shared_delta_u": D, "true_split_u": ov["true_split_u"],
                "base_residual_u": ov["base_residual_u"]}
        if not undeclared:
            item["policy"] = "전원 특정 — R04 예외 성립(잔차 논법 허용)"
            item["declared_errors_u"] = {
                e: ev_by_id[e]["declared_magnitude_u"]
                   - truth_ev[e]["target_slice_delta_effect_u"] for e in (e1, e2)}
        elif len(undeclared) == 1:
            item["policy"] = "분리 불가 — 기권 (R04: 후보 전원 특정 시에만 잔차 논법 성립)"
            pinned = e1 if e1 not in undeclared else e2
            other = e2 if pinned == e1 else e1
            meas_pinned = monthly_deltas(ledger, [Q_A, Q_B], ev_by_id[pinned]["target"])[0]
            declared = ev_by_id[pinned]["declared_magnitude_u"]
            true_pinned = truth_ev[pinned]["target_slice_delta_effect_u"]
            est_other = meas_pinned - declared
            true_other = ov["true_split_u"][other]
            err = est_other - true_other
            item["residual_experiment"] = {
                "설명": "계약상 차단되는 '전원-1' 잔차 귀속을 시험 수행한 오차 실측",
                "estimate_u": est_other, "true_u": true_other, "error_u": err,
                "error_decomposition": {
                    "선언 오차(선언−참)": declared - true_pinned,
                    "기저·교호·기타 잔여": meas_pinned - true_pinned - true_other},
                "separation_justified": abs(err) <= SPLIT_TOL * max(1, abs(D))}
        else:
            item["policy"] = "분리 불가 — 기권"
            strategies = {"반반": (D / 2, D / 2), f"전부 {e1}": (D, 0), f"전부 {e2}": (0, D)}
            r1 = ev_by_id[e1].get("reference_scale_u")
            r2 = ev_by_id[e2].get("reference_scale_u")
            if r1 and r2:
                w = abs(r1) / (abs(r1) + abs(r2))
                strategies["참조 스케일 비례"] = (D * w, D * (1 - w))
            errs = {k: max(abs(a - t1), abs(b - t2)) for k, (a, b) in strategies.items()}
            best = min(errs.values())                    # 판정은 라운딩 전 값으로
            item["naive_split_max_error_u"] = {k: round(v, 1) for k, v in errs.items()}
            item["best_naive_error_u"] = round(best, 1)
            item["abstention_justified"] = best > abs(D) * SPLIT_TOL
        abstention.append(item)
    S["C_abstention"] = abstention

    # D. 미끼 기각 — 슬라이스 통상 대역 + 검정력 경고
    decoys = []
    for t in truth["events"]:
        if not t.get("decoy"):
            continue
        e = ev_by_id[t["id"]]
        deltas = monthly_deltas(ledger, hist, e["target"])
        lo, hi = usual_band(deltas)
        meas = monthly_deltas(ledger, [Q_A, Q_B], e["target"])[0]
        slice_scale = max(1, sum(r["sales_u"] for r in ledger
                                 if r["month"] == Q_A and
                                 all({"channel": r["channel"], "category": r["category"],
                                      "customer_type": r["customer_type"],
                                      "region": r["region"]}[k] in v
                                     for k, v in e["target"].items())))
        width_pct = round((hi - lo) / slice_scale * 100, 1)
        low_power = width_pct > 10
        call = "기각(통상 변동 범위 내)" if lo <= meas <= hi else "오판 위험 — 대역 밖"
        decoys.append({"id": t["id"], "measured_slice_delta_u": meas,
                       "band_u": [round(lo), round(hi)],
                       "band_width_pct_of_slice": width_pct,
                       "within_band": lo <= meas <= hi,
                       "correct_call": call + (f" [검정력 낮음 — 대역 폭이 슬라이스 월총계의 "
                                               f"{width_pct}%]" if low_power else "")})
    if decoys:
        S["D_decoy"] = decoys

    # E. 대역 대 δ_min — 데이터 대역과 반사실(base) 대역의 병기
    deltas = monthly_deltas(ledger, hist)
    lo, hi = usual_band(deltas)
    base_tot = truth["base_monthly_totals_u"]
    base_deltas = series_deltas(base_tot, hist)
    blo, bhi = usual_band(base_deltas)
    base_q_delta = base_tot[Q_B] - base_tot[Q_A]
    total_delta = monthly_deltas(ledger, [Q_A, Q_B])[0]
    has_events = any(t["total_delta_effect_u"] for t in truth["events"])
    S["E_band"] = {
        "history_deltas_u": deltas, "band_data_u": [round(lo), round(hi)],
        "band_base_u": [round(blo), round(bhi)],
        "base_q_delta_u": base_q_delta, "measured_q_delta_u": total_delta,
        "delta_min_verdict": ("유의미(|Δ|≥δ_min)" if abs(total_delta) >=
                              sem["question_defaults"]["delta_min_u"] else "미소 변화"),
        "band_data_verdict": ("통상 변동 범위 내" if lo <= total_delta <= hi
                              else "통상 대역 이탈 — 설명 요구됨"),
        "counterfactual_check": {
            "무이벤트 Δ가 base 대역 내": blo <= base_q_delta <= bhi,
            "이벤트 충격이 base 대역 밖": (not (blo <= total_delta <= bhi))
                                           if has_events else None},
        "warning": "대역 폭은 계절 진폭 지배(원시 MoM Δ, n=5, 계절조정 부재) — "
                   "판정은 검정이 아니라 설명 요구 트리거로만 사용"}

    # G. VRM 대조 — rate 개입의 검출
    v = vrm_lite(sem, ledger, Q_A, Q_B, record)
    if v["status"] == "result":
        rate = v["rate_effect_u"]
        g = {"rate_effect_u": rate, "volume_effect_u": v["volume_effect_u"]}
        if "E6" in truth_ev:
            true_rate = truth_ev["E6"]["target_slice_delta_effect_u"]
            g["true_E6_effect_u"] = true_rate
            g["gap_u"] = round(rate - true_rate, 1)
            g["consistent"] = abs(rate - true_rate) <= max(15, 0.15 * abs(true_rate))
            g["note"] = "허용 오차에 Laspeyres 관례·교호작용 차이 포함"
        else:
            g["consistent"] = abs(rate) <= 10
            g["note"] = "rate 개입 없음 — 단가 효과 ≈ 0 기대"
        S["G_vrm"] = g
    return S


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    names = [p.name for p in sorted(SIM.iterdir()) if p.is_dir() and p.name != "out"]
    results = []
    for name in names:
        S = score_scenario(name)
        (OUT / f"score_{name}.json").write_text(json.dumps(S, ensure_ascii=False, indent=1))
        results.append(S)

    lines = ["# 원인 주입 채점표 (simulate.py seed=20260810 · score.py)",
             "", "부호 규약: 선언오차 = 선언 − 참 (양수 = 과대 신고). "
             "오차·대역의 '±' 없는 값은 절대량.", ""]
    for S in results:
        n = S["scenario"]
        lines.append(f"## {n}\n")
        ax = S["A_arithmetic"]
        blocked = {k: v.get("violated") for k, v in ax.items() if v["status"] != "result"}
        ok = not blocked and all(v.get("identity", True) for v in ax.values())
        lines.append(f"- **A 산술/게이트**: 3축 분해 "
                     + ("전부 result·검산 통과" if ok else f"게이트 발동 {blocked}"))
        if "F_gates" in S:
            f = S["F_gates"]
            lines.append(f"- **F 게이트 발화**: 전 축 차단 {f['axes_blocked']}; region 드릴 → "
                         f"{f['region_drill_status']}({', '.join(f['region_violated'])}); "
                         f"vrm → {f['vrm_status']}({f['vrm_missing']}); "
                         f"환불(음수) 행 {f['negative_rows']}개는 **무게이트 통과 — 알려진 공백**\n")
            continue
        for a in S.get("B_attribution", []):
            decl = ""
            if "declaration_error_u" in a:
                decl = f" 선언오차 {u(a['declaration_error_u'])}"
                if "injected_u" in a:
                    decl += f" (명목 {u(a['injected_u'])} vs 실현 {u(a['true_effect_u'])})"
            elif "reference_error_pct" in a:
                decl = f" 참조오차 {a['reference_error_pct']:+.0f}%"
            lines.append(f"- **B {a['id']}**: 실측 {u(a['measured_slice_delta_u'])} vs "
                         f"참 {u(a['true_effect_u'])} (귀속갭 {u(a['attribution_gap_u'])}){decl}")
        for c in S.get("C_abstention", []):
            pair = "+".join(c["pair"])
            if "declared_errors_u" in c:
                errs = ", ".join(f"{k} {u(v)}" for k, v in c["declared_errors_u"].items())
                lines.append(f"- **C {pair}**: {c['policy']} — 선언 대조({errs}), "
                             f"기저 잔차 {u(c['base_residual_u'])}")
            elif "residual_experiment" in c:
                ex = c["residual_experiment"]
                ed = ex["error_decomposition"]
                lines.append(f"- **C {pair}**: {c['policy']} — 차단된 논법의 시험 오차 "
                             f"{u(ex['error_u'])} (선언 {u(ed['선언 오차(선언−참)'])}, "
                             f"잔여 {u(ed['기저·교호·기타 잔여'])}) → 분리 "
                             f"{'정당화 가능' if ex['separation_justified'] else '부당 — 차단이 옳음'}")
            else:
                lines.append(f"- **C {pair}**: {c['policy']} — 최선 naive 배분 오차 "
                             f"{u_abs(c['best_naive_error_u'])} → 기권 "
                             f"{'정당' if c['abstention_justified'] else '과잉(재검토)'}")
        for dc in S.get("D_decoy", []):
            lines.append(f"- **D {dc['id']}(미끼)**: 실측 {u(dc['measured_slice_delta_u'])}, "
                         f"대역 [{u(dc['band_u'][0])}, {u(dc['band_u'][1])}] → {dc['correct_call']}")
        e = S["E_band"]
        cf = e["counterfactual_check"]
        lines.append(f"- **E 대역 vs δ_min**: Δ {u(e['measured_q_delta_u'])} — δ_min "
                     f"'{e['delta_min_verdict']}' / 데이터 대역 [{u(e['band_data_u'][0])}, "
                     f"{u(e['band_data_u'][1])}] '{e['band_data_verdict']}' / base 대역 "
                     f"[{u(e['band_base_u'][0])}, {u(e['band_base_u'][1])}]: 무이벤트 Δ "
                     f"{u(e['base_q_delta_u'])} 포함={cf['무이벤트 Δ가 base 대역 내']}, "
                     f"이벤트 충격 검출={cf['이벤트 충격이 base 대역 밖']}")
        if "G_vrm" in S:
            g = S["G_vrm"]
            tail = (f" vs 참 E6 {u(g['true_E6_effect_u'])} (갭 {u(g['gap_u'])})"
                    if "true_E6_effect_u" in g else "")
            lines.append(f"- **G VRM**: 단가 효과 {u(g['rate_effect_u'])}{tail} → "
                         f"{'정합' if g['consistent'] else '불일치 — 재검토'}")
        lines.append(f"  - ⚠ {e['warning']}\n")
    (OUT / "scorecard.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
