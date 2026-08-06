"""수직 조각 러너 — 질문: "7월 매출이 왜 변했나? (전월 대비)"

절차(§7.1의 ④~⑦ 구간): 원장 적재 → 3축 분해 → 최대 기여 축 드릴다운(예산 상한 2) →
VRM → Evidence Bundle 조립 → 팩트 시트 외부 대조.
①~③(해석·바인딩·선택)은 v0에서 하드코딩 — 질문 서명과 명세를 코드에 동결.
"""
import json
from pathlib import Path

from kernel import (load_semantic, load_ledger, contrib_decomp, vrm_lite,
                    event_overlap_scan)

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

U = 0.1  # 1u = 0.1억원


def fmt_u(u):
    return f"{u * U:+.1f}억" if isinstance(u, int) else f"{u * U:+.1f}억"


def main():
    sem = load_semantic()
    ledger = load_ledger()
    A, B = "2026-06", "2026-07"

    # 질문 명세 (v0: 하드코딩 — ①~③의 자리 표시)
    spec = {"question": "7월 매출이 왜 변했나?",
            "signature": {"external_criterion": "present", "question_type": "change"},
            "binding": {"metric": "매출@v1", "period": [A, B],
                        "comparison_basis": "prior_period", "as_of": "2026-08-06"},
            "echo": "이렇게 이해했습니다 — 매출[v1], 2026-07, 전월(2026-06) 대비, 전 채널"}

    record = {"calls": [], "budget": {"max_depth": 2, "consumed_depth": 0, "segments_examined": 0}}

    print("=" * 72)
    print(f"질의: {spec['question']}")
    print(f"명세 반향: {spec['echo']}")
    print("=" * 72)

    # ── 1단계: 3축 분해 ──────────────────────────────────────────────
    axes = sem["metric"]["decomposition_identities"][0]["dimensions"]
    results = {}
    for dim in axes:
        r = contrib_decomp(sem, ledger, dim, A, B, record)
        results[dim] = r
        record["budget"]["segments_examined"] += len(r.get("segments", []))
        print(f"\n[contrib_decomp × {dim}]  status={r['status']}")
        if r["status"] != "result":
            print("  ", r)
            continue
        t = r["total"]
        print(f"  전체: {t['before_u']*U:.1f}억 → {t['after_u']*U:.1f}억  "
              f"Δ {fmt_u(t['delta_u'])} ({t['pct_change']:+.1f}%)")
        if r["share_suppressed"]:
            print(f"  ⚠ share_of_change 억제: {r['share_suppression_reason']} → Σ|기여| 기준 병기")
        for s in r["segments"]:
            share = (f"기여도 {s['share_of_change_pct']:+.1f}%" if "share_of_change_pct" in s
                     else f"|기여| {s['share_of_abs_pct']:.1f}%")
            print(f"    {s['segment']:6s} {s['before_u']*U:7.1f} → {s['after_u']*U:7.1f}  "
                  f"Δ {fmt_u(s['delta_u']):>8s} ({s['pct_change']:+.1f}%)  {share}")
        for c in r["checks"]:
            mark = "✓" if c["passed"] else "✗"
            print(f"    {mark} {c['check']}: {c['detail']}")

    # ── 2단계: 최대 기여 축의 top 세그먼트 드릴다운 (예산 depth=2) ────
    top_axis = max((d for d in axes if results[d]["status"] == "result"),
                   key=lambda d: max(abs(s["delta_u"]) for s in results[d]["segments"]))
    top_seg = results[top_axis]["segments"][0]["segment"]
    record["budget"]["consumed_depth"] = 2
    print(f"\n[드릴다운] 최대 기여 축={top_axis}, 세그먼트={top_seg} → 채널 교차 분해")
    drill = contrib_decomp(sem, ledger, "channel", A, B, record,
                           within={top_axis: top_seg})
    record["budget"]["segments_examined"] += len(drill.get("segments", []))
    if drill["status"] == "result":
        total_delta_all = results[top_axis]["total"]["delta_u"]
        for s in drill["segments"]:
            vs_all = s["delta_u"] / total_delta_all * 100
            print(f"    {top_seg}×{s['segment']:6s} Δ {fmt_u(s['delta_u']):>8s} "
                  f"({s['pct_change']:+.1f}%)  전체 Δ 대비 {vs_all:+.1f}%")
        for c in drill["checks"]:
            if c["check"] == "identity_recheck":
                print(f"    {'✓' if c['passed'] else '✗'} {c['check']}: {c['detail']}")

    # ── 2b: 권역 드릴다운 (오프라인 내) ──────────────────────────────
    region_drill = contrib_decomp(sem, ledger, "region", A, B, record,
                                  within={"channel": "오프라인"})
    record["budget"]["segments_examined"] += len(region_drill.get("segments", []))
    if region_drill["status"] == "result":
        print("\n[드릴다운] 오프라인 × 권역")
        for s in region_drill["segments"]:
            print(f"    {s['segment']:4s} Δ {fmt_u(s['delta_u']):>8s} ({s['pct_change']:+.1f}%)")

    # ── 3단계: VRM (온라인 볼륨×단가) ────────────────────────────────
    v = vrm_lite(sem, ledger, A, B, record)
    print(f"\n[vrm_lite × 온라인]  status={v['status']}")
    if v["status"] == "result":
        print(f"    건수: {v['orders'][A]/10000:.1f}만 → {v['orders'][B]/10000:.1f}만  "
              f"객단가: {v['price_manwon'][A]:.2f}만원 → {v['price_manwon'][B]:.2f}만원")
        print(f"    볼륨 효과 {fmt_u(v['volume_effect_u'])}, 단가 효과 {fmt_u(v['rate_effect_u'])}"
              f"  (항등식 닫힘: {v['identity_ok']})")

    # ── 3b: 이벤트 레지스트리 대조 ──────────────────────────────────
    ev = event_overlap_scan(sem, ledger, A, B, record)
    print(f"\n[event_overlap_scan]  status={ev['status']}")
    for e in ev["events"]:
        decl = (f"선언 {e['declared_magnitude_u']*U:+.1f}억" if e["declared_magnitude_u"] is not None
                else f"규모 미특정" + (f" (참조 스케일 {e['reference_scale_u']*U:.1f}억)"
                                     if e["reference_scale_u"] else ""))
        print(f"    {e['id']} {e['name'][:22]:24s} 슬라이스 실측 Δ {fmt_u(e['measured_slice_delta_u']):>8s}"
              f"  | {decl}  | {e['evidence_grade']}")
    for o in ev["overlap_flags"]:
        print(f"    ⚠ 중첩: {'+'.join(o['pair'])} — {o['note'][:40]}…")

    # ── 4단계: Evidence Bundle 조립 ──────────────────────────────────
    bundle = {"spec": spec,
              "results": {**{f"contrib:{d}": results[d] for d in axes},
                          f"drill:{top_axis}={top_seg}×channel": drill,
                          "drill:offline×region": region_drill,
                          "vrm:online": v, "events": ev},
              "execution_record": record,
              "assumption_ledger": [
                  {"assumption": "세그먼트 구성의 기간 간 안정성(개방 코호트)",
                   "status": "unchecked", "evidence_ref": "not_computable_v0",
                   "note": "segment_churn_rate 진단 미구현 — v1 과제"},
              ],
              "external_reference_check": None}

    # ── 5단계: 팩트 시트 외부 대조 (exemplars-v0의 기대값) ────────────
    expect = {"channel": {"온라인": -220, "오프라인": -70, "B2B": -50},
              "category": {"식품": -80, "생활용품": -140, "뷰티": 80, "가전": -200},
              "customer_type": {"신규": -280, "기존": -60}}
    mism = []
    for dim, exp in expect.items():
        got = {s["segment"]: s["delta_u"] for s in results[dim]["segments"]}
        for seg, e in exp.items():
            if got.get(seg) != e:
                mism.append((dim, seg, e, got.get(seg)))
    bundle["external_reference_check"] = {"passed": not mism, "mismatches": mism}
    print(f"\n[팩트 시트 대조] {'✓ 전 세그먼트 일치' if not mism else '✗ 불일치: ' + str(mism)}")
    print(f"[탐색 예산] depth {record['budget']['consumed_depth']}/{record['budget']['max_depth']}, "
          f"검토 세그먼트 {record['budget']['segments_examined']}개, "
          f"커널 호출 {len(record['calls'])}회 — 이 결론은 이 예산 안에서 선택된 것")

    (OUT / "bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=1))
    print(f"\nEvidence Bundle → {OUT/'bundle.json'}")


if __name__ == "__main__":
    main()
