"""시뮬 시나리오 번들 생성기 — ⑧루프 확장 측정용 (rise/flat/fall_dirty).

run.py의 ④~⑦ 구간을 시나리오-중립으로 재구성: 3축 분해 → (가능하면) 최대 기여
축 top 세그먼트 × 나머지 축 드릴다운(예산 depth=2) → VRM → 이벤트 대조 →
대역 진단(ADR-0004: 게이트 아닌 설명 요구 트리거) → Evidence Bundle 조립.
원 시나리오 전용 하드코딩 드릴(run.py 2b~2d)과 팩트 시트 대조는 없다.
truth.json은 정답지이므로 번들에 싣지 않는다.

계획 대비: 시뮬 데이터셋에는 계획 빈티지 저장소가 없어 suspended로 정직 기록.

사용: python3 run_sim.py [scenario ...]   (기본: rise flat fall_dirty)
출력: out/loop8x/<scenario>/bundle.json
"""
import json
import statistics
import sys
from pathlib import Path

from kernel import (load_semantic, load_ledger, contrib_decomp, vrm_lite,
                    event_overlap_scan)

HERE = Path(__file__).parent
Q_A, Q_B = "2026-06", "2026-07"
BAND_K = 3.0


def usual_band(deltas):
    med = statistics.median(deltas)
    mad = statistics.median([abs(d - med) for d in deltas]) or 1
    return med - BAND_K * mad, med + BAND_K * mad


def build(scenario):
    sem = load_semantic()
    d = HERE / "sim" / scenario
    ledger = load_ledger(d / "ledger.csv")
    record = {"calls": [], "budget": {"max_depth": 2, "consumed_depth": 0,
                                      "segments_examined": 0}}

    spec = {"status": "spec", "question": "7월 매출이 왜 변했나?",
            "signature": {"external_criterion": "present", "question_type": "change"},
            "binding": {"metric": "매출@v1", "month": Q_B,
                        "comparison_basis": "prior_period", "within": {},
                        "as_of": "2026-08-06"},
            "echo": "이렇게 이해했습니다 — 매출[v1], 2026-07, 전월(2026-06) 대비, 전 채널"}

    axes = sem["metric"]["decomposition_identities"][0]["dimensions"]
    results = {}
    for dim in axes:
        r = contrib_decomp(sem, ledger, dim, Q_A, Q_B, record)
        results[f"contrib:{dim}"] = r
        record["budget"]["segments_examined"] += len(r.get("segments", []))

    ok_axes = [dm for dm in axes if results[f"contrib:{dm}"]["status"] == "result"]
    if ok_axes:
        top_axis = max(ok_axes, key=lambda dm: max(
            abs(s["delta_u"]) for s in results[f"contrib:{dm}"]["segments"]))
        top_seg = results[f"contrib:{top_axis}"]["segments"][0]["segment"]
        record["budget"]["consumed_depth"] = 2
        for other in axes:
            if other == top_axis:
                continue
            dr = contrib_decomp(sem, ledger, other, Q_A, Q_B, record,
                                within={top_axis: top_seg})
            results[f"drill:{top_axis}={top_seg}×{other}"] = dr
            record["budget"]["segments_examined"] += len(dr.get("segments", []))

    results["plan_gap"] = {
        "status": "suspended",
        "missing_inputs": ["plan_vintage 저장소 — 이 데이터셋에 등록된 계획 빈티지 없음"],
        "pass_conditions": "계획 빈티지가 등록되면 실행 가능"}
    results["vrm:online"] = vrm_lite(sem, ledger, Q_A, Q_B, record)
    results["events"] = event_overlap_scan(sem, ledger, Q_A, Q_B, record,
                                           events_path=d / "events.json")

    # 대역 진단 — ADR-0004: 검정이 아니라 설명 요구 트리거, ledger 진단 항목
    def tot(m):
        return sum(r["sales_u"] for r in ledger if r["month"] == m)

    months = sorted({r["month"] for r in ledger})
    hist = months[:months.index(Q_B)]
    deltas = [tot(hist[i + 1]) - tot(hist[i]) for i in range(len(hist) - 1)]
    lo, hi = usual_band(deltas)
    total_delta = tot(Q_B) - tot(Q_A)
    dmin = sem["question_defaults"]["delta_min_u"]
    results["band_diagnostic"] = {
        "status": "result", "output_type": "Description",
        "estimand": "전사 월간 Δ의 통상 변동 대역 대비 위치 (무분포 진단)",
        "history_deltas_u": deltas, "band_u": [round(lo), round(hi)],
        "total_delta_u": total_delta, "within_band": lo <= total_delta <= hi,
        "delta_min_u": dmin,
        "delta_min_verdict": ("유의미(|Δ|≥δ_min)" if abs(total_delta) >= dmin
                              else "미소 변화(|Δ|<δ_min)"),
        "role": "검정이 아니라 설명 요구 트리거 — 게이트 아님 (ADR-0004)",
        "caveat": "대역 폭은 계절 진폭 지배(원시 MoM Δ, n=5, 계절조정 부재) — 검정력 없음",
        "label_ceiling": {"대역 내/이탈": "데이터 확인(계산 자체)",
                          "'통상적/이례적' 해석": "데이터 시사 상한"}}

    bundle = {"spec": spec, "results": results, "execution_record": record,
              "assumption_ledger": [
                  {"assumption": "세그먼트 구성의 기간 간 안정성(개방 코호트)",
                   "status": "unchecked", "evidence_ref": "not_computable_v0",
                   "note": "segment_churn_rate 진단 미구현 — v1 과제"},
              ],
              "external_reference_check": None}

    outdir = HERE / "out" / "loop8x" / scenario
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=1))

    statuses = {k: v.get("status") for k, v in results.items()}
    print(f"[{scenario}] Δ {total_delta}u ({total_delta*0.1:+.1f}억) "
          f"대역 [{round(lo)}, {round(hi)}]u 내={lo <= total_delta <= hi}")
    for k, s in statuses.items():
        print(f"  {k}: {s}")
    print(f"  → {outdir/'bundle.json'}")


if __name__ == "__main__":
    for sc in (sys.argv[1:] or ["rise", "flat", "fall_dirty"]):
        build(sc)
