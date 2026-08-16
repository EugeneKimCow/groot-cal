"""Reproduce current planner intent-fidelity counterexamples.

This is characterization, not an acceptance test for desired behavior. A
successful run means the documented current observations remain reproducible.
"""
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "slice"))

from engine import run_question  # noqa: E402


def probe():
    rows = []

    envelope, bundle = run_question("7월 평균 재고는?")
    rows.append({
        "id": "average_inventory",
        "classification": "silent_substitution",
        "observed": {
            "status": envelope["status"],
            "metric_id": envelope["query_spec"]["subject"]["metric_id"],
            "operation_family": envelope["query_spec"]["intent"]["operation_family"],
            "value": bundle["results"]["level"].get("value"),
        },
    })

    envelope, bundle = run_question("7월 재고 회전율은?")
    rows.append({
        "id": "inventory_turnover",
        "classification": "silent_metric_misbinding",
        "observed": {
            "status": envelope["status"],
            "metric_id": envelope["query_spec"]["subject"]["metric_id"],
            "value": bundle["results"]["level"].get("value"),
        },
    })

    envelope, bundle = run_question("7월 오프라인 매출 감소를 지역별로 보여줘")
    result_keys = sorted(bundle["results"])
    rows.append({
        "id": "requested_region_breakdown",
        "classification": "silent_breakdown_loss",
        "observed": {
            "status": envelope["status"],
            "scope": envelope["query_spec"]["scope"],
            "has_region_result": any("region" in key for key in result_keys),
            "result_keys": result_keys,
        },
    })

    envelope, bundle = run_question("7월 매출 감소 상위 3개 제품군만 보여줘")
    rows.append({
        "id": "rank_limit_only",
        "classification": "silent_rank_limit_loss",
        "observed": {
            "status": envelope["status"],
            "query_spec_has_rank": "rank" in envelope["query_spec"],
            "query_spec_has_limit": "limit" in envelope["query_spec"],
            "result_count": len(bundle["results"]),
        },
    })

    envelope, _ = run_question("2025년 7월 매출은?")
    rows.append({
        "id": "explicit_year",
        "classification": "silent_time_loss",
        "observed": {
            "status": envelope["status"],
            "focal_period": envelope["query_spec"]["focal_period"],
        },
    })

    envelope, bundle = run_question("7월 손해율이 왜 변했나?")
    rows.append({
        "id": "rate_change",
        "classification": "safe_operator_refusal",
        "observed": {
            "status": envelope["status"],
            "result_status": bundle["results"]["change"]["status"],
        },
    })

    envelope, bundle = run_question("7월 매출과 영업이익을 비교해줘")
    rows.append({
        "id": "multi_metric",
        "classification": "safe_clarification",
        "observed": {"status": envelope["status"], "bundle": bundle},
    })
    return rows


def paraphrase_signatures():
    questions = [
        "7월 매출이 왜 변했나?",
        "7월 매출 변화 원인은?",
        "7월 매출 감소 동인은?",
        "7월 매출이 전월 대비 어떻게 달라졌어?",
        "7월 매출 변동을 제품군별 기여로 보여줘",
    ]
    signatures = []
    for question in questions:
        envelope, _ = run_question(question)
        spec = envelope.get("query_spec") or {}
        signatures.append({
            "question": question,
            "status": envelope["status"],
            "family": (spec.get("intent") or {}).get("operation_family"),
            "comparison": (spec.get("comparison") or {}).get("kind"),
        })
    return signatures


def verify(rows):
    by_id = {row["id"]: row for row in rows}
    assert by_id["average_inventory"]["observed"]["value"] == 190
    assert by_id["inventory_turnover"]["observed"]["metric_id"] == "operations.inventory_on_hand"
    assert by_id["requested_region_breakdown"]["observed"]["has_region_result"] is False
    assert by_id["rank_limit_only"]["observed"]["query_spec_has_rank"] is False
    assert by_id["explicit_year"]["observed"]["focal_period"] == "2026-07"
    assert by_id["rate_change"]["observed"]["result_status"] == "out_of_domain"
    assert by_id["multi_metric"]["observed"]["status"] == "clarify"


if __name__ == "__main__":
    observations = probe()
    verify(observations)
    print(json.dumps({"counterexamples": observations,
                      "paraphrases": paraphrase_signatures()},
                     ensure_ascii=False, indent=2))
