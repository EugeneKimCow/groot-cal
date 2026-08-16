"""Query Spec v1을 구속력 있는 실행으로 변환하는 수직 조각 pipeline."""
import hashlib
import json
from pathlib import Path

from kernel import (contrib_decomp, event_overlap_scan, metric_level, plan_gap,
                    vrm_lite)
from query_spec import validate_query_spec
from runtime import ExecutionRuntime


def _spec_hash(spec):
    raw = json.dumps(spec, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _input_hash(ledger):
    raw = json.dumps(ledger, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def execute_query(spec_envelope, sem, ledger, events_path=None):
    """interpret()의 spec envelope을 실행하고 Evidence Bundle을 반환한다."""
    spec = spec_envelope["query_spec"]
    checked = validate_query_spec(spec, sem, ledger)
    if checked["status"] != "result":
        return {"spec": spec_envelope, "results": {"query_spec": checked},
                "execution_record": None, "assumption_ledger": [],
                "external_reference_check": None}

    scope = spec["scope"]
    focal = spec["focal_period"]
    comp = spec["comparison"]
    family = spec["intent"]["operation_family"]
    runtime = ExecutionRuntime(sem["question_defaults"]["exploration_budget"], family,
                               metric=sem["metric"])
    results = {}

    if family == "inspect_level":
        results["level"] = runtime.execute(
            "metric_level", 1, 1,
            lambda record: metric_level(sem, ledger, focal, record, within=scope))

    elif family == "compare_plan":
        results["plan_gap"] = runtime.execute(
            "plan_gap", 1, len(sem["dimensions"]["channel"]["values"]),
            lambda record: plan_gap(sem, ledger, focal, record,
                                    vintage_id=comp["vintage_id"], within=scope))

    elif family == "explain_change":
        month_a, month_b = comp["period"], focal
        axes = sem["metric"]["decomposition_identities"][0]["dimensions"]
        # 이미 한 값으로 고정된 축의 자기 분해는 정보가 없으므로 후보에서 제외한다.
        initial_axes = [d for d in axes if d not in scope]
        for dim in axes:
            if dim not in initial_axes:
                runtime.reject(f"contrib_decomp:{dim}", "query scope에서 이미 고정된 차원")
        for dim in initial_axes:
            results[f"contrib:{dim}"] = runtime.execute(
                f"contrib_decomp:{dim}", 1, len(sem["dimensions"][dim]["values"]),
                lambda record, dim=dim: contrib_decomp(
                    sem, ledger, dim, month_a, month_b, record, within=scope))

        ok_axes = [d for d in initial_axes
                   if results[f"contrib:{d}"]["status"] == "result"]
        if ok_axes:
            top_axis = max(ok_axes, key=lambda d: max(
                abs(s["delta_u"]) for s in results[f"contrib:{d}"]["segments"]))
            top_seg = results[f"contrib:{top_axis}"]["segments"][0]["segment"]
            drill_scope = {**scope, top_axis: top_seg}
            for other in initial_axes:
                if other == top_axis:
                    continue
                key = f"drill:{top_axis}={top_seg}×{other}"
                results[key] = runtime.execute(
                    f"contrib_decomp:{other}", 2,
                    len(sem["dimensions"][other]["values"]),
                    lambda record, other=other: contrib_decomp(
                        sem, ledger, other, month_a, month_b, record,
                        within=drill_scope))

        vrm_scope_ok = set(scope).issubset({"channel"}) and (
            "channel" not in scope or scope["channel"] == "온라인")
        if vrm_scope_ok:
            results["vrm:online"] = runtime.execute(
                "vrm_lite:online", 1, 0,
                lambda record: vrm_lite(sem, ledger, month_a, month_b, record))
        else:
            runtime.reject("vrm_lite:online", "온라인 전체 이외 scope에는 정의되지 않음")

        event_file = Path(events_path) if events_path else Path(__file__).parent / "events.json"
        expected_hypotheses = len(json.loads(event_file.read_text())["events"])
        results["events"] = runtime.execute(
            "event_overlap_scan", 1, 0,
            lambda record: event_overlap_scan(
                sem, ledger, month_a, month_b, record,
                events_path=events_path, within=scope),
            expected_hypotheses=expected_hypotheses)
    else:
        results["intent"] = {"status": "out_of_domain",
                             "violated": [{"check": "operation_family",
                                           "passed": False, "detail": family}]}

    record = runtime.record
    record["query_spec_hash"] = _spec_hash(spec)
    record["provenance"] = {
        "metric_ref": f"{sem['metric']['id']}@v{sem['metric']['version']}",
        "semantic_model_ref": f"semantic.json#{sem['metric']['id']}@v{sem['metric']['version']}",
        "input_snapshot_ref": f"sha256:{_input_hash(ledger)}",
        "as_of": spec["as_of"],
    }
    return {
        "spec": spec_envelope,
        "results": results,
        "execution_record": record,
        "assumption_ledger": [{
            "assumption": "세그먼트 구성의 기간 간 안정성(개방 코호트)",
            "status": "unchecked", "evidence_ref": "not_computable_v0",
            "note": "segment_churn_rate 진단 미구현 — v1 과제",
        }],
        "external_reference_check": None,
    }
