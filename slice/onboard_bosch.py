"""E-027 계측 온보딩 — Bosch 불량률·검사수 (익명 단위 구간 window).

원천은 bosch.duckdb의 part_summary_train(부품 grain)이며, 등록하는 것은
(구간 × 라인 경로) 집계 grain이다 — rate의 Σ분자/Σ분모와 count의 Σ는 집계
grain에서도 정확하다(가법성). 시간축은 달력이 아닌 익명 단위이므로 E-027의
unit_bucket window(width=100)로 등록한다. 산출 fixture는 집계 통계 119행이라
원본 재배포 금지에 저촉되지 않고, 기본 catalog(오프라인)에서도 동작한다.

실행: ../.venv/bin/python3 onboard_bosch.py
"""
import json
from pathlib import Path

import duckdb

from demo import demo_question

HERE = Path(__file__).parent
DB = HERE.parent / "data" / "bosch-production-line-performance" / "bosch.duckdb"
BUCKET_WIDTH = 100

RATE_FIXTURE = HERE / "onboarded" / "bosch_failure_rate.json"
COUNT_FIXTURE = HERE / "onboarded" / "bosch_inspected.json"


def build_rows():
    connection = duckdb.connect(str(DB), read_only=True)
    try:
        raw = connection.execute(f"""
            SELECT CAST(FLOOR(start_time / {BUCKET_WIDTH}) * {BUCKET_WIDTH}
                        AS INTEGER) AS bucket_start,
                   lines_visited,
                   CAST(SUM(response) AS INTEGER) AS failed,
                   COUNT(*) AS inspected
            FROM part_summary_train
            WHERE start_time IS NOT NULL
            GROUP BY 1, 2 ORDER BY 1, 2
        """).fetchall()
    finally:
        connection.close()
    rows = []
    for bucket_start, lines_visited, failed, inspected in raw:
        rows.append({
            "t": bucket_start,
            "path": "-".join(f"L{line}" for line in lines_visited),
            "failed": failed,
            "inspected": inspected,
        })
    return rows


def contracts(paths):
    # ── 사람의 선언 (지식 획득 비용) ─────────────────────────────────
    shared_dimensions = {
        "path": {"type": "nominal", "values": paths, "mece": True}}
    # 판단: 라인 경로는 부품의 파티션(부품당 경로 1개) → MECE
    rate = {
        "metric": {
            "id": "quality.failure_rate", "name": "불량률",
            "aliases": ["불량률"],
            "type": "rate", "version": 1, "unit": "ratio",
            "properties": {
                "additive_across_dims": False,       # 판단: 비율은 비가법
                "additive_across_time": False,
                "aggregation_rule": "denominator_weighted_mean",
                "has_denominator": True,
                "sign": "nonnegative",
                "available_windows": ["unit_bucket"],  # 판단: 달력 없음
                "unit_bucket": {"width": BUCKET_WIDTH},
            },
            "bindings": {"numerator_field": "failed",
                         "denominator_field": "inspected",
                         "time_field": "t"},
            "generation": {
                "source": "bosch.duckdb part_summary_train (집계 grain)",
                "grain": f"익명 시간 {BUCKET_WIDTH}단위 버킷 × 라인 경로"},
        },
        "dimensions": shared_dimensions,
    }
    count = {
        "metric": {
            "id": "quality.inspected_parts", "name": "검사 부품 수",
            "aliases": ["검사 부품 수", "검사수", "검사 수"],
            "type": "count", "version": 1, "unit": "개",
            "properties": {
                "additive_across_dims": True,
                "additive_across_time": True,
                "aggregation_rule": "sum",
                "sign": "nonnegative",
                "available_windows": ["unit_bucket"],
                "unit_bucket": {"width": BUCKET_WIDTH},
            },
            "bindings": {"value_field": "inspected", "time_field": "t"},
            "generation": {
                "source": "bosch.duckdb part_summary_train (집계 grain)",
                "grain": f"익명 시간 {BUCKET_WIDTH}단위 버킷 × 라인 경로"},
        },
        "dimensions": shared_dimensions,
    }
    return rate, count


def register(fixture_path):
    entry = {"fixture_path": f"onboarded/{fixture_path.name}",
             "execution_profile": "typed_core"}
    for catalog_path in ("metric_catalog.json", "metric_catalog.duckdb.json"):
        catalog = json.loads((HERE / catalog_path).read_text())
        if not any(item.get("fixture_path") == entry["fixture_path"]
                   for item in catalog["entries"]):
            catalog["entries"].append(entry)
        (HERE / catalog_path).write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2))


def main():
    rows = build_rows()
    paths = sorted({row["path"] for row in rows})
    print(f"[기계] 집계 rows {len(rows)}건 · 경로 {len(paths)}종 · "
          f"버킷 폭 {BUCKET_WIDTH}")
    rate, count = contracts(paths)
    for sem, fixture_path in ((rate, RATE_FIXTURE), (count, COUNT_FIXTURE)):
        fixture_path.write_text(json.dumps(
            {"metric": sem["metric"], "dimensions": sem["dimensions"],
             "rows": rows}, ensure_ascii=False, indent=1))
        register(fixture_path)
        print(f"[킷] {sem['metric']['name']} → {fixture_path.name} 등록")

    # ── 완료 판정: 게이트 통과 ───────────────────────────────────────
    from catalog import load_metric_catalog
    contexts = load_metric_catalog()
    checks = [
        ("U0300 구간 불량률은?", "executed", "result"),
        ("U0700 검사 부품 수는?", "executed", "result"),
        ("U0300 대비 U0400 검사수가 왜 변했나?", "executed", "result"),
        ("U0300 대비 U0400 불량률이 왜 변했나?", "intent", "out_of_domain"),
        ("3월 불량률은?", "executed", "out_of_domain"),
    ]
    all_ok = True
    for question, stage, status in checks:
        outcome = demo_question(question, contexts)
        got_stage = outcome["stage"]
        got_status = (outcome["execution"]["status"]
                      if got_stage == "executed"
                      else outcome["compiled"]["status"])
        ok = got_stage == stage and got_status == status
        all_ok &= ok
        detail = ""
        if got_stage == "executed" and got_status == "result":
            selected = next(iter(outcome["execution"]["outputs"].values()))
            detail = f" → {selected.get('value', (selected.get('total') or {}).get('delta'))}"
        print(f"{'✓' if ok else '✗'} {question}  "
              f"[{got_stage}/{got_status}]{detail}")
    print("온보딩 판정:", "게이트 통과" if all_ok else "미통과 — 선언 보완 필요")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
