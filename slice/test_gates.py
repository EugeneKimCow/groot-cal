"""커널 게이트 적대 프로브 — sign_policy · slice_measurement (2026-08-12).

양방향 검증:
  A. 무발화 — 청정 원장 4종(원본·fall·rise·flat)에서 게이트가 오발화하지 않고
     실측값이 게이트 도입 전과 동일한가 (원본은 기존 bundle.json과 대조).
  B. 발화 — fall_dirty 전체와, 청정 원장에 오염 1행씩을 주입한 합성 변이에서
     정확히 해당 슬라이스만 보류되는가 (타깃 밖 차원 오염은 무영향이어야 함).

사용: python3 test_gates.py   (전부 통과 시 종료 코드 0)
"""
import copy
import json
import sys
from pathlib import Path

from kernel import (load_semantic, load_ledger, contrib_decomp, vrm_lite,
                    event_overlap_scan, check_sign_policy)

HERE = Path(__file__).parent
Q_A, Q_B = "2026-06", "2026-07"
FAILS = []


def check(name, cond, detail=""):
    print(f"  {'✓' if cond else '✗'} {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def rec():
    return {"calls": [], "budget": {"max_depth": 2, "consumed_depth": 0,
                                    "segments_examined": 0}}


def scan(sem, ledger, events_path):
    return event_overlap_scan(sem, ledger, Q_A, Q_B, rec(), events_path=events_path)


def main():
    sem = load_semantic()

    # ── A1. 원본 원장: 전 이벤트 실측 유지 + 기존 번들과 값 일치 ─────────
    print("[A1] 원본 원장 — 무발화·값 보존")
    led0 = load_ledger()
    ev0 = scan(sem, led0, HERE / "events.json")
    old = json.loads((HERE / "out" / "bundle.json").read_text())["results"]["events"]["events"]
    old_by_id = {e["id"]: e["measured_slice_delta_u"] for e in old}
    for e in ev0["events"]:
        check(f"{e['id']} 실측 status=result", e["measurement_status"] == "result")
        check(f"{e['id']} 실측값 보존", e["measured_slice_delta_u"] == old_by_id[e["id"]],
              f"{e['measured_slice_delta_u']} vs {old_by_id[e['id']]}")
    check("overlap 실측 유지", all(o["measurement_status"] == "result"
                                   for o in ev0["overlap_flags"]))
    check("sign_policy 통과", check_sign_policy(sem, led0, {Q_A, Q_B})["passed"])

    # ── A2. 청정 시뮬 3종: 무발화 ────────────────────────────────────────
    for sc in ("fall", "rise", "flat"):
        print(f"[A2] sim/{sc} — 무발화")
        led = load_ledger(HERE / "sim" / sc / "ledger.csv")
        ev = scan(sem, led, HERE / "sim" / sc / "events.json")
        check(f"{sc} 전 이벤트 실측", all(e["measurement_status"] == "result"
                                          for e in ev["events"]))
        for dim in ("channel", "category", "customer_type"):
            r = contrib_decomp(sem, led, dim, Q_A, Q_B, rec())
            check(f"{sc} contrib:{dim} result", r["status"] == "result",
                  str(r.get("violated")))
        check(f"{sc} vrm result", vrm_lite(sem, led, Q_A, Q_B, rec())["status"] == "result")

    # ── B1. fall_dirty: 전면 발화 ───────────────────────────────────────
    print("[B1] sim/fall_dirty — 발화")
    ledd = load_ledger(HERE / "sim" / "fall_dirty" / "ledger.csv")
    sgn = check_sign_policy(sem, ledd, {Q_A, Q_B})
    check("sign_policy 발화", not sgn["passed"], sgn["detail"])
    # 게이트는 estimand 기간(6~7월)만 검사 — 전체 원장 73개 중 기간 내 부분집합
    exp_neg = sum(1 for r in ledd if r["month"] in (Q_A, Q_B) and r["sales_u"] < 0)
    check(f"음수 행 실측 {exp_neg}개(기간 내)", sgn["negative_rows"] == exp_neg,
          str(sgn["negative_rows"]))
    r = contrib_decomp(sem, ledd, "channel", Q_A, Q_B, rec())
    check("contrib 거부에 sign_policy 포함", r["status"] == "out_of_domain"
          and any(c["check"] == "sign_policy" for c in r["violated"]))
    evd = scan(sem, ledd, HERE / "sim" / "fall_dirty" / "events.json")
    for e in evd["events"]:
        check(f"dirty {e['id']} 실측 보류·선언 보존",
              e["measurement_status"] == "suspended"
              and e["measured_slice_delta_u"] is None
              and (e["declared_magnitude_u"] is not None or e["id"] not in ("E3", "E4")))
    check("dirty overlap 실측 보류", all(o["measurement_status"] == "suspended"
                                         and o["shared_slice_totals_u"] is None
                                         for o in evd["overlap_flags"]))
    check("dirty vrm 거부/보류", vrm_lite(sem, ledd, Q_A, Q_B, rec())["status"] != "result")

    # ── B2. 합성 변이 1행 — 정확히 해당 슬라이스만 보류 ──────────────────
    print("[B2] 합성 변이 — 국소 발화")

    def mutate(pred, **kv):
        led = copy.deepcopy(led0)
        for row in led:
            if row["month"] == Q_B and pred(row):
                row.update(kv)
                return led
        raise RuntimeError("변이 대상 행 없음")

    # (a) 온라인×신규 행 1개를 미선언 채널로 → E1 보류, E5(카테고리만)는 유지.
    # 주의: 온라인×기존 행을 변이하면 customer_type=기존이 E1 슬라이스 밖을 확정하므로
    # '제외'가 정답이다(알려진 차원의 배제가 불명보다 우선) — 신규 행으로 변이해야 발화.
    led = mutate(lambda r: r["channel"] == "온라인" and r["customer_type"] == "신규",
                 channel="마켓플레이스")
    ev = scan(sem, led, HERE / "events.json")
    st = {e["id"]: e["measurement_status"] for e in ev["events"]}
    check("(a) 채널 타깃 E1 보류", st["E1"] == "suspended")
    check("(a) 카테고리 전용 E5 유지 — 타깃 밖 차원 오염 무영향", st["E5"] == "result")

    # (a') 온라인×기존 행의 채널 오염 → E1은 '제외' 유지 (배제 우선 의미론 고정)
    led = mutate(lambda r: r["channel"] == "온라인" and r["customer_type"] == "기존",
                 channel="마켓플레이스")
    st = {e["id"]: e["measurement_status"] for e in scan(sem, led, HERE / "events.json")["events"]}
    check("(a') 기존 고객 행 오염은 E1 무영향(배제 우선)", st["E1"] == "result")

    # (b) 오프라인 행 1개 region NULL → E3만 보류
    led = mutate(lambda r: r["channel"] == "오프라인", region=None)
    st = {e["id"]: e["measurement_status"] for e in scan(sem, led, HERE / "events.json")["events"]}
    check("(b) E3 보류", st["E3"] == "suspended")
    check("(b) E1 유지", st["E1"] == "result")

    # (c) 온라인×신규 행 1개 음수화 → E1 보류(부호), E3 유지, contrib 거부
    led = mutate(lambda r: r["channel"] == "온라인" and r["customer_type"] == "신규"
                 and r["sales_u"] > 0)
    for row in led:
        if row["month"] == Q_B and row["channel"] == "온라인" \
           and row["customer_type"] == "신규" and row["sales_u"] > 0:
            row["sales_u"] = -row["sales_u"]
            break
    st = {e["id"]: e["measurement_status"] for e in scan(sem, led, HERE / "events.json")["events"]}
    check("(c) E1 보류(부호)", st["E1"] == "suspended")
    check("(c) E3 유지", st["E3"] == "result")
    check("(c) contrib 거부(sign)", any(
        c["check"] == "sign_policy"
        for c in contrib_decomp(sem, led, "channel", Q_A, Q_B, rec()).get("violated", [])))

    # (d) 부호 규범 미선언 → 검사 자체가 실패
    sem2 = copy.deepcopy(sem)
    del sem2["metric"]["properties"]["sign"]
    check("(d) 규범 미선언 = 실패", not check_sign_policy(sem2, led0, {Q_A, Q_B})["passed"])

    # (e) customer_type NULL 1행 → E1 보류, E2(채널×카테고리) 유지
    led = mutate(lambda r: r["channel"] == "온라인", customer_type=None)
    st = {e["id"]: e["measurement_status"] for e in scan(sem, led, HERE / "events.json")["events"]}
    check("(e) E1 보류", st["E1"] == "suspended")
    check("(e) E2 유지", st["E2"] == "result")

    print(f"\n{'전부 통과' if not FAILS else '실패 ' + str(len(FAILS)) + '건: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
