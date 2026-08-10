"""원인 주입 시뮬레이터 v2 — 검증 방향의 반전.

generate_data.py(v0)는 팩트 시트(정답지)에서 원장을 역생성했다(답→데이터).
이 시뮬레이터는 기저 프로세스 + 이벤트 개입으로 원장을 전방 생성한다(원인→데이터):

  기저 프로세스: 채널·카테고리·고객구분(·권역) 셀별 수준 × 계절성 × 요일 효과 × 셀 잡음
  이벤트 = 프로세스 파라미터에 대한 개입 (승법 multiplier / 가법 lump)
  정답 원장 = leave-one-out 반사실: 잡음이 (day, cell) 해시로 고정되므로
             '이벤트 하나 끈 원장'과의 차이가 그 이벤트의 실현 효과와 정수 일치

핵심 설계:
- 참 규모(truth.json)와 선언 규모(events.json)의 분리 — 선언은 현실처럼 오염됨
  (정확 신고 / ±3% 신고 잡음 / 규모 미특정 + 참조 스케일 ±15% / 무선언 / 미끼)
- 시나리오 7종: fall, rise, flat, overlap_blind, overlap_pinned, decoy, fall_dirty
- 지저분함 다이얼(fall_dirty): NULL 권역·미선언 채널 값·환불(음수) 행 — 게이트 발화 시험용
- 산술: 최종 원장은 정수 u. 기간: 2026-01-01 ~ 07-31 (통상 변동 대역 재료 6개월 + 질문 월)
"""
import csv
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
SIM = HERE / "sim"

SEED = 20260810
START, END = date(2026, 1, 1), date(2026, 7, 31)
Q_A, Q_B = "2026-06", "2026-07"  # 질문: 7월이 전월 대비 왜 변했나

CH = ["온라인", "오프라인", "B2B"]
CAT = ["식품", "생활용품", "뷰티", "가전"]
CUST = ["신규", "기존"]
REG = ["수도권", "영남", "호남", "충청"]

MONTH_BASE_U = 4200                      # 월 총계 기준 스케일 (420억)
CH_SHARE = {"온라인": 0.43, "오프라인": 0.36, "B2B": 0.21}
CAT_SHARE = {"온라인": {"식품": 0.30, "생활용품": 0.25, "뷰티": 0.20, "가전": 0.25},
             "오프라인": {"식품": 0.42, "생활용품": 0.26, "뷰티": 0.15, "가전": 0.17},
             "B2B": {"식품": 0.28, "생활용품": 0.20, "뷰티": 0.07, "가전": 0.45}}
NEW_SHARE = {"온라인": 0.25, "오프라인": 0.15, "B2B": 0.11}
REG_SHARE = {"수도권": 0.52, "영남": 0.28, "호남": 0.12, "충청": 0.08}
SEASON = {1: 0.96, 2: 0.92, 3: 1.00, 4: 1.02, 5: 1.05, 6: 1.00, 7: 0.98}
WD = {"온라인": {"wd": 0.97, "sat": 1.06, "sun": 1.10},
      "오프라인": {"wd": 0.93, "sat": 1.22, "sun": 1.16},
      "B2B": {"wd": 1.38, "sat": 0.05, "sun": 0.03}}
NOISE_SIGMA = 0.10
PRICE_MANWON_DEFAULT = 5.0


def days():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=1)


def cells():
    for ch in CH:
        for cat in CAT:
            for cu in CUST:
                if ch == "오프라인":
                    for rg in REG:
                        yield (ch, cat, cu, rg)
                else:
                    yield (ch, cat, cu, None)


def cell_noise(day, cell):
    """(day, cell) 해시 고정 잡음 — 이벤트 on/off가 다른 셀·날의 잡음을 건드리지 않아야
    leave-one-out 차이가 순수 이벤트 효과가 된다."""
    rng = random.Random(f"{SEED}|{day.isoformat()}|{'|'.join(str(x) for x in cell)}")
    return math.exp(rng.gauss(0.0, NOISE_SIGMA))


def cell_matches(cell, target):
    ch, cat, cu, rg = cell
    vals = {"channel": ch, "category": cat, "customer_type": cu, "region": rg}
    return all(vals[k] in v for k, v in target.items())


def base_level(day, cell):
    ch, cat, cu, rg = cell
    m = day.month
    ndays = (date(2026, m % 12 + 1, 1) - timedelta(days=1)).day if m < 12 else 31
    wd = WD[ch]["sat" if day.weekday() == 5 else "sun" if day.weekday() == 6 else "wd"]
    v = (MONTH_BASE_U / ndays) * SEASON[m] * CH_SHARE[ch] * CAT_SHARE[ch][cat] * wd
    v *= NEW_SHARE[ch] if cu == "신규" else (1 - NEW_SHARE[ch])
    if rg is not None:
        v *= REG_SHARE[rg]
    return v


# ── 이벤트 개입 ──────────────────────────────────────────────────────────
def in_period(day, period):
    return period[0] <= day.isoformat() <= period[1]


def gen_ledger(events, active_ids, price_by_month):
    """활성 이벤트 집합으로 원장 생성. 반환: rows(dict list)"""
    rows = []
    add_events = [e for e in events if e["kind"] == "add" and e["id"] in active_ids]
    for day in days():
        month = day.isoformat()[:7]
        for cell in cells():
            v = base_level(day, cell)
            for e in events:
                if e["id"] not in active_ids or e["kind"] != "mult":
                    continue
                if in_period(day, e["period"]) and cell_matches(cell, e["target"]):
                    v *= e["factor"]
            v *= cell_noise(day, cell)
            sales = max(0, round(v))
            ch, cat, cu, rg = cell
            rows.append({"date": day.isoformat(), "channel": ch, "category": cat,
                         "customer_type": cu, "region": rg or "",
                         "sales_u": sales, "month": month})
    # 가법 이벤트: 대상 행의 매출 용량 비례 분배 (주말 등 0 셀에서의 클램프 소실 방지)
    for e in add_events:
        tgt_rows = [r for r in rows if r["month"] == e["month"]
                    and cell_matches((r["channel"], r["category"], r["customer_type"],
                                      r["region"] or None), e["target"])]
        cap = sum(r["sales_u"] for r in tgt_rows)
        amt = e["amount_u"]
        sign = 1 if amt > 0 else -1
        remaining = abs(amt)
        # 큰 셀부터 용량 비례 정수 배분 — 감액은 셀 잔액을 넘지 않음
        for r in sorted(tgt_rows, key=lambda x: -x["sales_u"]):
            if remaining == 0 or cap == 0:
                break
            share = min(remaining, max(1, round(abs(amt) * r["sales_u"] / cap)))
            if sign < 0:
                share = min(share, r["sales_u"])
            r["sales_u"] += sign * share
            remaining -= share
    # 주문 건수 (온라인만): 객단가는 월별 파라미터
    for r in rows:
        if r["channel"] == "온라인":
            p = price_by_month.get(r["month"], PRICE_MANWON_DEFAULT)
            r["online_orders"] = round(r["sales_u"] * 1000 / p)
        else:
            r["online_orders"] = ""
    return rows


# ── 집계 헬퍼 ────────────────────────────────────────────────────────────
def slice_total(rows, month, target=None):
    t = 0
    for r in rows:
        if r["month"] != month:
            continue
        if target and not cell_matches((r["channel"], r["category"], r["customer_type"],
                                        r["region"] or None), target):
            continue
        t += r["sales_u"]
    return t


def slice_delta(rows, a, b, target=None):
    return slice_total(rows, b, target) - slice_total(rows, a, target)


def targets_intersect(t1, t2):
    for dim in set(t1) & set(t2):
        if not set(t1[dim]) & set(t2[dim]):
            return None
    shared = dict(t1)
    for dim, vals in t2.items():
        shared[dim] = sorted(set(shared.get(dim, vals)) & set(vals)) if dim in shared else vals
    # 차원별 교집합이 있어도 셀 수준 교집합이 공집합일 수 있다
    # (예: 온라인 × region=호남 — 온라인 행에는 region이 없음) → 가짜 중첩 방지
    if not any(cell_matches(c, shared) for c in cells()):
        return None
    return shared


# ── 선언 정책: 참 규모 → (오염된) 신고치 ─────────────────────────────────
def tgauss(rng, sigma, cap=2.0):
    """절단 정규 — 고정 시드에서 극단 draw가 벤치마크에 영구 박제되는 것을 방지
    (E3의 -2.6σ 신고오차가 '±3% 잡음' 명세와 체감 괴리를 낳았던 결함)."""
    z = rng.gauss(0, 1)
    while abs(z) > cap:
        z = rng.gauss(0, 1)
    return z * sigma


def declare(e, truth_ev):
    """declared_magnitude_u / reference_scale_u를 선언 정책에 따라 생성.
    선언 잡음의 rng는 이벤트 id로 고정 — 시나리오 간 재현.

    exact 정책의 가법 이벤트는 명목 주입치(amount_u)를 신고한다 — 배분·클램프로
    실현 효과가 명목과 어긋나는 것 자체가 시험 대상(신고-실현 괴리)이므로,
    실현치를 신고하면 그 시험이 설계에서 소거된다.
    """
    rng = random.Random(f"{SEED}|declare|{e['id']}")
    pol = e["declare"]
    d = {"declared_magnitude_u": None, "reference_scale_u": None,
         "reference_note": e.get("note", "")}
    true_delta = truth_ev["target_slice_delta_effect_u"]
    if pol == "exact":
        d["declared_magnitude_u"] = e.get("amount_u", true_delta)
    elif pol == "noisy3":
        d["declared_magnitude_u"] = round(true_delta * (1 + tgauss(rng, 0.03)))
    elif pol == "noisy1":
        d["declared_magnitude_u"] = round(true_delta * (1 + tgauss(rng, 0.01)))
    elif pol == "ref_noisy":
        # 참조 스케일: 기여 월의 참 기여 규모에 ±15% 집계 오차 ("팀 집계")
        base = abs(truth_ev["month_a_slice_effect_u"]) or abs(truth_ev["month_b_slice_effect_u"])
        d["reference_scale_u"] = round(base * (1 + tgauss(rng, 0.15)))
    # pol == "none" / "decoy": 아무 수치도 없음
    return d


# ── 시나리오 정의 ────────────────────────────────────────────────────────
def _promo_june(declare_pol="ref_noisy"):
    return {"id": "E1", "name": "6월 첫구매 프로모션(6/1~30) — 7월 기저효과",
            "kind": "mult", "factor": 1.45, "period": ("2026-06-01", "2026-06-30"),
            "target": {"channel": ["온라인"], "customer_type": ["신규"]},
            "declare": declare_pol, "note": "마케팅팀 집계 — 코호트 데이터 미확보"}


def _competitor():
    return {"id": "E2", "name": "경쟁사 M몰 미드이어 페스타(7/14~20)",
            "kind": "mult", "factor": 0.72, "period": ("2026-07-14", "2026-07-20"),
            "target": {"channel": ["온라인"], "category": ["가전", "생활용품"]},
            "declare": "none", "note": "행사 전후 트래픽 데이터 미보유"}


def _closure():
    return {"id": "E3", "name": "호남 오프라인 B점 폐점(7/1)",
            "kind": "mult", "factor": 0.72, "period": ("2026-07-01", "2026-07-31"),
            "target": {"channel": ["오프라인"], "region": ["호남"]},
            "declare": "noisy3", "note": "점포 단위 수치는 원장 밖 신고치"}


def _order_shift():
    return {"id": "E4", "name": "B2B K전자양판 정기발주 8월 이월",
            "kind": "add", "amount_u": -55, "month": "2026-07",
            "period": ("2026-07-01", "2026-07-31"),
            "target": {"channel": ["B2B"], "category": ["가전"], "customer_type": ["기존"]},
            "declare": "exact", "note": "영업팀 확인 — 소멸 아닌 이월"}


def _beauty(factor=1.12):
    return {"id": "E5", "name": "뷰티 신규 브랜드 입점(7/1~)",
            "kind": "mult", "factor": factor, "period": ("2026-07-01", "2026-07-31"),
            "target": {"channel": ["온라인", "오프라인"], "category": ["뷰티"]},
            "declare": "ref_noisy", "note": "브랜드 단위는 원장 밖 집계"}


def _decoy():
    return {"id": "EX", "name": "수도권 물류 파업 루머(7월)", "kind": "mult",
            "factor": 1.0, "period": ("2026-07-01", "2026-07-31"),
            "target": {"channel": ["오프라인"], "region": ["수도권"]},
            "declare": "decoy", "note": "업계지 보도 — 실제 영향 미확인"}


def _online_rate_up():
    return {"id": "E6", "name": "온라인 가격 개편(7/1) — 객단가 +5%",
            "kind": "mult", "factor": 1.05, "period": ("2026-07-01", "2026-07-31"),
            "target": {"channel": ["온라인"]},
            "declare": "none", "note": "단가 개편 공지 — 매출 효과 미집계"}


SCENARIOS = {
    "fall": {"events": [_promo_june(), _competitor(), _closure(), _order_shift(), _beauty()],
             "price": {}},
    "rise": {"events": [{**_promo_june("ref_noisy"), "period": ("2026-07-01", "2026-07-31"),
                         "name": "7월 첫구매 프로모션 개시"},
                        _beauty(1.30), _online_rate_up()],
             "price": {"2026-07": 5.25}},
    "flat": {"events": [], "price": {}},
    "overlap_blind": {"events": [_promo_june("ref_noisy"), _competitor()], "price": {}},
    "overlap_pinned": {"events": [_promo_june("noisy1"), _competitor()], "price": {}},
    # R04 예외의 실제 시험대: 후보 원인 전원의 금액이 특정된 유일한 케이스
    "overlap_specified": {"events": [_promo_june("noisy1"),
                                     {**_competitor(), "declare": "noisy3",
                                      "note": "사후 트래픽 패널 분석으로 이탈 규모 특정"}],
                          "price": {}},
    "decoy": {"events": [_decoy()], "price": {}},
    "fall_dirty": {"events": [_promo_june(), _competitor(), _closure(), _order_shift(), _beauty()],
                   "price": {}, "dirty": {"null_region": 0.03, "alien_channel": 0.01,
                                          "refund": 0.02}},
}


def apply_dirty(rows, dirty):
    """지저분함 다이얼 — 행 해시 고정이라 재현 가능."""
    out = []
    for i, r in enumerate(rows):
        rng = random.Random(f"{SEED}|dirty|{i}|{r['date']}|{r['channel']}|{r['category']}")
        r = dict(r)
        if r["channel"] == "오프라인" and rng.random() < dirty.get("null_region", 0):
            r["region"] = ""                     # NULL 권역
        if rng.random() < dirty.get("alien_channel", 0):
            r["channel"] = "마켓플레이스"          # 미선언 채널 값
        out.append(r)
        if r["sales_u"] > 2 and rng.random() < dirty.get("refund", 0):
            ref = dict(r)
            ref["sales_u"] = -max(1, r["sales_u"] // 10)   # 환불(음수) 행
            ref["online_orders"] = ""
            out.append(ref)
    return out


def build_scenario(name, cfg):
    events = cfg["events"]
    mech_ids = {e["id"] for e in events if e["declare"] != "decoy"}
    price = cfg["price"]

    full = gen_ledger(events, mech_ids, price)
    base = gen_ledger(events, set(), price)

    # leave-one-out 정답: 잡음 고정이라 (full − loo)가 해당 이벤트의 실현 효과
    truth_events = []
    marg_total = 0
    loo_cache = {}
    for e in events:
        if e["declare"] == "decoy":
            truth_events.append({"id": e["id"], "decoy": True,
                                 "target_slice_delta_effect_u": 0,
                                 "month_a_slice_effect_u": 0, "month_b_slice_effect_u": 0,
                                 "total_delta_effect_u": 0})
            continue
        loo = gen_ledger(events, mech_ids - {e["id"]}, price)
        loo_cache[e["id"]] = loo
        t = e["target"]
        te = {"id": e["id"],
              "target_slice_delta_effect_u": slice_delta(full, Q_A, Q_B, t) - slice_delta(loo, Q_A, Q_B, t),
              "month_a_slice_effect_u": slice_total(full, Q_A, t) - slice_total(loo, Q_A, t),
              "month_b_slice_effect_u": slice_total(full, Q_B, t) - slice_total(loo, Q_B, t),
              "total_delta_effect_u": slice_delta(full, Q_A, Q_B) - slice_delta(loo, Q_A, Q_B)}
        if e["kind"] == "add":
            te["injected_u"] = e["amount_u"]   # 명목 주입치 — 실현 효과와의 괴리가 시험 대상
        truth_events.append(te)
        marg_total += te["total_delta_effect_u"]

    interaction = (slice_delta(full, Q_A, Q_B) - slice_delta(base, Q_A, Q_B)) - marg_total

    # 중첩 정답: 타깃 교차쌍의 공유 슬라이스에서 이벤트별 참 기여와 기저 잔차
    overlaps = []
    mech_events = [e for e in events if e["declare"] != "decoy"]
    for i in range(len(mech_events)):
        for j in range(i + 1, len(mech_events)):
            e1, e2 = mech_events[i], mech_events[j]
            shared = targets_intersect(e1["target"], e2["target"])
            if shared is None:
                continue
            d_full = slice_delta(full, Q_A, Q_B, shared)
            s1 = d_full - slice_delta(loo_cache[e1["id"]], Q_A, Q_B, shared)
            s2 = d_full - slice_delta(loo_cache[e2["id"]], Q_A, Q_B, shared)
            overlaps.append({"pair": [e1["id"], e2["id"]], "shared_slice": shared,
                             "shared_slice_delta_full_u": d_full,
                             "true_split_u": {e1["id"]: s1, e2["id"]: s2},
                             "base_residual_u": d_full - s1 - s2})

    # 선언(오염된 신고치) — events.json
    ev_out = []
    for e, te in zip(events, truth_events):
        d = declare(e, te)
        ev_out.append({"id": e["id"], "name": e["name"], "period": list(e["period"]),
                       "affects": Q_B, "target": e["target"], **d})

    # 지저분함 다이얼
    dirty = cfg.get("dirty")
    out_rows = apply_dirty(full, dirty) if dirty else full

    # 저장
    d = SIM / name
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "ledger.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "channel", "category", "customer_type",
                                          "region", "sales_u", "online_orders"])
        w.writeheader()
        for r in out_rows:
            w.writerow({k: r[k] for k in w.fieldnames})
    (d / "events.json").write_text(json.dumps({"events": ev_out}, ensure_ascii=False, indent=1))

    months = sorted({r["month"] for r in full})
    truth = {"scenario": name, "seed": SEED, "question_months": [Q_A, Q_B],
             "dirty": bool(dirty),
             "note": ("이벤트 효과·monthly_totals_u는 dirty 적용 전 원장 기준 — "
                      "배포 원장 총계는 ledger_monthly_totals_u 참조" if dirty else ""),
             "ledger_monthly_totals_u": {m: sum(r["sales_u"] for r in out_rows
                                                if r["month"] == m) for m in months},
             "monthly_totals_u": {m: slice_total(full, m) for m in months},
             "base_monthly_totals_u": {m: slice_total(base, m) for m in months},
             "events": [{**te, "declared": ev_out[k]["declared_magnitude_u"],
                         "reference_scale": ev_out[k]["reference_scale_u"]}
                        for k, te in enumerate(truth_events)],
             "interaction_residual_u": interaction,
             "overlaps": overlaps}
    (d / "truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1))

    tot = truth["monthly_totals_u"]
    print(f"[{name:14s}] {Q_A} {tot[Q_A]*0.1:.1f}억 → {Q_B} {tot[Q_B]*0.1:.1f}억 "
          f"(Δ {(tot[Q_B]-tot[Q_A])*0.1:+.1f}억) 행 {len(out_rows)} "
          f"이벤트 {len(ev_out)} 중첩쌍 {len(overlaps)} 교호 {interaction}u")
    return truth


if __name__ == "__main__":
    for name, cfg in SCENARIOS.items():
        build_scenario(name, cfg)
