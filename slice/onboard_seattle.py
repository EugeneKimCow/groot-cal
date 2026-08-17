"""E-026 계측 온보딩 — Seattle 일별 날씨 관측 (실데이터 dry run).

출처: vega-datasets seattle-weather.csv (BSD-3, 실제 관측 데이터).
이 스크립트 자체가 온보딩 대장이다: 기계가 파생한 것은 profile이 출력하고,
사람이 선언한 것은 아래 키워드 인자와 그 주석이다. 완료 판정은 문서가 아니라
게이트 통과(demo 질의 4종)다.

실행: ../.venv/bin/python3 onboard_seattle.py
"""
from pathlib import Path

from demo import demo_question
from onboard import (build_fixture, context_from_fixture,
                     load_fixture_into_duckdb, profile_csv, scaffold_contract)

HERE = Path(__file__).parent
CSV = HERE / "data_external" / "seattle-weather.csv"
FIXTURE = HERE / "onboarded" / "seattle_weather.json"
DB = HERE / "store" / "groot.duckdb"


def main():
    profile = profile_csv(CSV)
    print(f"[기계] 행 {profile['row_count']} · 기간 {profile['date_span']}")

    # ── 사람의 선언 (지식 획득 비용의 전량) ──────────────────────────
    sem = scaffold_contract(
        profile,
        metric_id="weather.precipitation",
        name="강수량",                      # 선언: 지표 정체성
        aliases=["강수량", "강수"],          # 선언: 질의 어휘
        metric_type="amount",               # 판단: 일 강수량은 가법 flow
        unit="mm",                          # 선언: 원천 문서 없이 데이터만으로는 알 수 없음
        value_field="precipitation",        # 판단: 수치 후보 4개 중 지표 의미와 일치하는 열
        sign="nonnegative",                 # 판단: 강수량은 음수 불가 (물리적 정의역)
        date_field="date",
        dimension_fields=("weather",),      # 판단: 저카디널리티 5값 → 분해 축
        mece_fields=("weather",),           # 판단: 하루 1행·1라벨 → 날짜 파티션
        available_windows=("month", "iso_week"),  # 판단: 일별 grain → 두 window 등록
    )
    fixture = build_fixture(CSV, sem, FIXTURE)
    print(f"[킷] 계약+정규화 rows → {FIXTURE.name} ({len(fixture['rows'])}행)")
    try:
        count = load_fixture_into_duckdb(fixture, "seattle_weather", DB)
        print(f"[킷] DuckDB 적재 → seattle_weather ({count}행)")
    except ModuleNotFoundError:
        print("[킷] duckdb 미설치 — 저장소 적재 생략(.venv로 실행 시 적재)")

    # ── 완료 판정: 게이트 통과 ───────────────────────────────────────
    from catalog import load_metric_catalog
    contexts = load_metric_catalog() + [context_from_fixture(FIXTURE)]
    checks = [
        ("2015년 3월 강수량은?", "executed", "result"),
        ("2015년 2월 대비 3월 강수량이 왜 변했나?", "executed", "result"),
        ("2015-W10 강수량은?", "executed", "result"),
        ("2015-W53 강수량은?", "executed", "suspended"),  # 부분 주 (4/7일)
    ]
    all_ok = True
    for question, stage, status in checks:
        outcome = demo_question(question, contexts)
        got_stage = outcome["stage"]
        got_status = (outcome["execution"]["status"]
                      if got_stage == "executed" else outcome["compiled"]["status"])
        ok = got_stage == stage and got_status == status
        all_ok &= ok
        detail = ""
        if got_stage == "executed" and got_status == "result":
            selected = next(iter(outcome["execution"]["outputs"].values()))
            value = selected.get("value",
                                 (selected.get("total") or {}).get("delta"))
            detail = f" → {value}{'' if value is None else ' mm'}"
        print(f"{'✓' if ok else '✗'} {question}  [{got_stage}/{got_status}]{detail}")
    print("온보딩 판정:", "게이트 통과" if all_ok else "미통과 — 선언 보완 필요")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
