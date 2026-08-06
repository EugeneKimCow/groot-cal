"""한솔리테일 가상 원장 생성기 (수직 조각 v0).

exemplars-v0.md의 팩트 시트에 '정확히' 정합하는 일별 셀 집계 원장을 생성한다.
- 금액 단위: 내부 정수 u (1u = 0.1억원 = 1,000만원) — 부동소수점 오차 원천 차단
- 제약: 월별 채널/카테고리/채널×고객구분/오프라인 권역/7월 주별 합계가 팩트 시트와 정수 일치
- 방법: IPF(iterative proportional fitting) + 정수 반올림 후 사이클 보수(repair)
- grain: 일 × 채널 × 카테고리 × 고객구분 (× 권역: 오프라인만) — 주문 라인 원장은 후속
"""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)

CH = ["온라인", "오프라인", "B2B"]
CAT = ["식품", "생활용품", "뷰티", "가전"]
CUST = ["신규", "기존"]
REG = ["수도권", "영남", "호남", "충청"]

# ── 팩트 시트 목표치 (u = 0.1억) ─────────────────────────────────────────
TGT = {
    "2026-06": {
        "channel_cust": {("온라인", "신규"): 620, ("온라인", "기존"): 1180,
                         ("오프라인", "신규"): 240, ("오프라인", "기존"): 1260,
                         ("B2B", "신규"): 100, ("B2B", "기존"): 800},
        "category": {"식품": 1500, "생활용품": 1100, "뷰티": 700, "가전": 900},
        "region": {"수도권": 780, "영남": 420, "호남": 180, "충청": 120},
        "weekly": None,
    },
    "2026-07": {
        "channel_cust": {("온라인", "신규"): 380, ("온라인", "기존"): 1200,
                         ("오프라인", "신규"): 220, ("오프라인", "기존"): 1210,
                         ("B2B", "신규"): 80, ("B2B", "기존"): 770},
        "category": {"식품": 1420, "생활용품": 960, "뷰티": 780, "가전": 700},
        "region": {"수도권": 770, "영남": 410, "호남": 130, "충청": 120},
        "weekly": [920, 970, 780, 1190],  # W1(7/1-7) W2(8-14) W3(15-21) W4(22-31)
    },
}
ONLINE_PRICE_MANWON = 5.0  # 객단가 5.0만원 → 1u(1000만원) = 200건 (양 월 동일: 팩트 시트 §6)


def ipf(seed, row_targets, col_targets, iters=500):
    """2차원 IPF. seed[r][c] 양수 가중치 → 행/열 합이 목표에 수렴하는 실수 행렬."""
    R, C = len(row_targets), len(col_targets)
    m = [[float(seed[r][c]) for c in range(C)] for r in range(R)]
    for _ in range(iters):
        for r in range(R):
            s = sum(m[r])
            if s > 0:
                m[r] = [v * row_targets[r] / s for v in m[r]]
        for c in range(C):
            s = sum(m[r][c] for r in range(R))
            if s > 0:
                for r in range(R):
                    m[r][c] *= col_targets[c] / s
    return m


def round_to_marginals(m, row_targets, col_targets):
    """실수 행렬 → 정수 행렬. 행합을 최대잉여법으로 정확히 맞춘 뒤 열합을 사이클 보수."""
    R, C = len(row_targets), len(col_targets)
    im = []
    for r in range(R):  # 행별 최대잉여법
        floors = [int(m[r][c]) for c in range(C)]
        rem = row_targets[r] - sum(floors)
        order = sorted(range(C), key=lambda c: -(m[r][c] - floors[c]))
        for k in range(rem):
            floors[order[k % C]] += 1
        im.append(floors)
    # 열 보수: 초과 열 → 부족 열로 1u씩 이동 (행합 보존)
    for _ in range(10000):
        colsum = [sum(im[r][c] for r in range(R)) for c in range(C)]
        over = [c for c in range(C) if colsum[c] > col_targets[c]]
        under = [c for c in range(C) if colsum[c] < col_targets[c]]
        if not over:
            break
        c_o, c_u = over[0], under[0]
        r_pick = max(range(R), key=lambda r: im[r][c_o])
        im[r_pick][c_o] -= 1
        im[r_pick][c_u] += 1
    assert all(sum(im[r]) == row_targets[r] for r in range(R))
    assert all(sum(im[r][c] for r in range(R)) == col_targets[c] for c in range(C))
    assert all(v >= 0 for row in im for v in row), "음수 셀 발생 — seed 조정 필요"
    return im


def split_int(total, weights, rng=None):
    """정수 total을 weights 비례로 정수 분할 (최대잉여법, 합 보존)."""
    s = sum(weights)
    if s == 0 or total == 0:
        parts = [0] * len(weights)
        parts[0] = total
        return parts
    raw = [total * w / s for w in weights]
    floors = [int(x) for x in raw]
    rem = total - sum(floors)
    order = sorted(range(len(weights)), key=lambda i: -(raw[i] - floors[i]))
    for k in range(rem):
        floors[order[k % len(weights)]] += 1
    return floors


def month_days(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    d0 = date(y, m, 1)
    days = []
    while d0.month == m:
        days.append(d0)
        d0 += timedelta(days=1)
    return days


def build_month(ym, rng):
    tgt = TGT[ym]
    rows_cc = [(ch, cu) for ch in CH for cu in CUST]  # 6 행
    row_t = [tgt["channel_cust"][rc] for rc in rows_cc]
    col_t = [tgt["category"][c] for c in CAT]

    # 도메인 취향 시드: B2B는 가전 편중(K사), 뷰티는 온라인·신규 편중(E5), 오프기존은 식품
    seed = {("온라인", "신규"): [2, 2, 3, 2], ("온라인", "기존"): [3, 2, 2, 2],
            ("오프라인", "신규"): [3, 2, 2, 1], ("오프라인", "기존"): [4, 3, 1.5, 1.5],
            ("B2B", "신규"): [1, 1, 0.3, 2], ("B2B", "기존"): [2, 2, 0.5, 4]}
    m = ipf([seed[rc] for rc in rows_cc], row_t, col_t)
    cell = round_to_marginals(m, row_t, col_t)  # cell[행=(ch,cust)][열=cat]

    days = month_days(ym)
    ledger = []  # (date, ch, cat, cust, region|"", u)

    if tgt["weekly"]:  # 7월: 셀 × 주 IPF (행=24셀, 열=4주)
        week_of = lambda d: min((d.day - 1) // 7, 3) if d.day <= 21 else 3
        week_days = [[d for d in days if week_of(d) == w] for w in range(4)]
        flat = [(rc, c) for ri, rc in enumerate(rows_cc) for c in range(len(CAT))]
        row_t2 = [cell[rows_cc.index(rc)][c] for rc, c in flat]
        # 이벤트 반영 시드: W3에 온라인×(가전|생활) 0.55, B2B기존×가전 0.25 (K사 이월)
        seed2 = []
        for rc, c in flat:
            w = [7, 7, 7, 10]
            if rc[0] == "온라인" and CAT[c] in ("가전", "생활용품"):
                w[2] *= 0.55
            if rc == ("B2B", "기존") and CAT[c] == "가전":
                w[2] *= 0.25
            seed2.append(w)
        m2 = ipf(seed2, row_t2, tgt["weekly"])
        cw = round_to_marginals(m2, row_t2, tgt["weekly"])
        for i, (rc, c) in enumerate(flat):
            for w in range(4):
                amt = cw[i][w]
                dws = [1 + 0.15 * rng.random() for _ in week_days[w]]
                for d, a in zip(week_days[w], split_int(amt, dws, rng)):
                    if a:
                        ledger.append([d, rc[0], CAT[c], rc[1], "", a])
    else:  # 6월: 일 단위 직접 분할
        for ri, rc in enumerate(rows_cc):
            for c in range(len(CAT)):
                amt = cell[ri][c]
                dws = [1 + 0.15 * rng.random() for _ in days]
                for d, a in zip(days, split_int(amt, dws, rng)):
                    if a:
                        ledger.append([d, rc[0], CAT[c], rc[1], "", a])

    # 오프라인 권역 배정: 행=오프라인 원장행, 열=권역 IPF
    off_idx = [i for i, r in enumerate(ledger) if r[1] == "오프라인"]
    row_t3 = [ledger[i][5] for i in off_idx]
    reg_seed = {"수도권": 6.5, "영남": 3.5, "호남": 1.5 if ym == "2026-06" else 1.05, "충청": 1.0}
    m3 = ipf([[reg_seed[g] * (1 + 0.1 * rng.random()) for g in REG] for _ in off_idx],
             row_t3, [tgt["region"][g] for g in REG])
    rg = round_to_marginals(m3, row_t3, [tgt["region"][g] for g in REG])
    new_rows = []
    for k, i in enumerate(off_idx):
        base = ledger[i]
        for gi, g in enumerate(REG):
            if rg[k][gi]:
                new_rows.append([base[0], base[1], base[2], base[3], g, rg[k][gi]])
    ledger = [r for r in ledger if r[1] != "오프라인"] + new_rows
    return ledger


def main():
    rng = random.Random(20260806)
    all_rows = build_month("2026-06", rng) + build_month("2026-07", rng)
    all_rows.sort(key=lambda r: (r[0], CH.index(r[1]), CAT.index(r[2]), r[3], r[4]))
    with open(OUT / "ledger.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "channel", "category", "customer_type", "region",
                    "sales_u", "online_orders"])
        for r in all_rows:
            orders = r[5] * 200 if r[1] == "온라인" else ""  # 1u = 200건 (객단가 5.0만원)
            w.writerow([r[0].isoformat(), r[1], r[2], r[3], r[4], r[5], orders])
    # 자체 검산
    def agg(pred):
        return sum(r[5] for r in all_rows if pred(r))
    report = {}
    for ym in ("2026-06", "2026-07"):
        month = lambda r: r[0].isoformat()[:7] == ym
        report[ym] = {
            "total": agg(month),
            "channel": {c: agg(lambda r, c=c: month(r) and r[1] == c) for c in CH},
            "category": {c: agg(lambda r, c=c: month(r) and r[2] == c) for c in CAT},
            "channel_cust": {f"{ch}-{cu}": agg(lambda r, ch=ch, cu=cu: month(r) and r[1] == ch and r[3] == cu)
                             for ch in CH for cu in CUST},
            "region": {g: agg(lambda r, g=g: month(r) and r[4] == g) for g in REG},
        }
    w_of = lambda d: min((int(d[8:10]) - 1) // 7, 3)
    report["2026-07"]["weekly"] = [
        sum(r[5] for r in all_rows if r[0].isoformat()[:7] == "2026-07" and w_of(r[0].isoformat()) == w)
        for w in range(4)]
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"rows={len(all_rows)}  → {OUT/'ledger.csv'}")


if __name__ == "__main__":
    main()
