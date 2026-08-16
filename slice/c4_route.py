"""E-018/E-019 — inspect_level·explain_change 질의의 가역 C4 라우팅.

기본 selector는 현행 경로를 그대로 보존한다. 이 모듈은 명시적으로 선택된 호출만
Query Spec을 C4 Plan으로 컴파일·실행하고, 결과를 canonical Result Envelope wire로
public bundle 경계에 노출한다. 라우팅 밖 Plan은 침묵 fallback 없이 거부한다.
실행 기록은 legacy operator 철자를 사칭하지 않고 Plan·binding identity를 보존한다.

E-019의 선언된 경계 축소: 현행 commerce explain_change의 숨은 전략 산출물
(`drill:*` 지배축 자동 드릴다운, `vrm:online`)은 라우팅된 경계에 없다. 연구
결론(synthesis §10)이 core dispatch에서 제거하기로 한 항목이며, 중첩 드릴다운은
명시적 intent(drilldown@v1)로만 돌아온다. 이벤트 대조는 숨은 분기 대신 명시적
`event_overlap_scan@v1` Call로 plan에 편입된다.
"""
import dataclasses

from pipeline import COMMERCE_ASSUMPTION_LEDGER, _input_hash, _spec_hash
from query_spec import validate_query_spec
from shadow_executor import execute_shadow_plan
from shadow_plan import compile_shadow_plan


ROUTED_FAMILIES = ("inspect_level", "explain_change")

# C4 비교 연산 결과의 선언 능력: 산술·사실은 확인, 해석 문장은 시사 상한.
# (보고 계약의 시사 상한 교리 — commerce kernel의 3중 ceiling 선언과 동치)
CHANGE_LABEL_CEILING = ("data_confirmed", "data_suggestive")


def refuse_unrouted(spec_envelope, family):
    """라우팅 밖 operation family의 명시적 거부. 현행 경로 실행은 caller 선택."""
    return {
        "spec": spec_envelope,
        "results": {"route": {
            "status": "out_of_domain",
            "violated": [{
                "check": "route_capability", "passed": False,
                "detail": (f"c4 경로는 {'·'.join(ROUTED_FAMILIES)}만 실행: "
                           f"{family}. 현행 경로 실행은 route='c4_or_current'로 "
                           "명시 선택"),
            }],
        }},
        "execution_record": None, "assumption_ledger": [],
        "external_reference_check": None,
    }


def execute_routed_query(spec_envelope, context, contexts=None):
    """라우팅된 family의 Query Spec을 C4 경로로 실행해 public bundle로 반환한다.

    입력 가용성을 포함한 semantic validation은 현행 경로와 같은 지점(query_spec)
    에서 실패해 실패 위치의 공개 경계가 보존된다.
    """
    spec = spec_envelope["query_spec"]
    sem = context["sem"]
    family = spec["intent"]["operation_family"]
    checked = validate_query_spec(spec, sem, context["rows"])
    if checked["status"] != "result":
        return _failed_bundle(spec_envelope, checked)

    metric = sem["metric"]
    if family == "explain_change" and metric.get("type") != "distinct" \
            and not metric.get("properties", {}).get("additive_across_dims"):
        # 현행 typed 경로와 동일한 public payload로 결과 키 경계에서 거부한다.
        return {
            "spec": spec_envelope,
            "results": {"change": {
                "status": "out_of_domain",
                "violated": [{"check": "change_operator_available",
                              "passed": False,
                              "detail": f"{metric.get('type')} 변화 연산자 미등록"}],
                "alternatives": ["rate 변화 분해 operator 등록"],
            }},
            "execution_record": _empty_record(spec, sem, context),
            "assumption_ledger": _assumption_ledger(context),
            "external_reference_check": None,
        }

    include_events = (family == "explain_change"
                      and context["execution_profile"] == "commerce_extensions")
    compiled = compile_shadow_plan(spec_envelope, sem,
                                   include_event_scan=include_events)
    if compiled["status"] != "result":
        return _failed_bundle(spec_envelope, compiled)

    plan = compiled["plan"]
    plan = dataclasses.replace(plan, metadata={
        **plan.metadata, "shadow_only": False, "route": "c4"})

    executed = execute_shadow_plan(plan, contexts=contexts)
    if plan.metadata["capability"] == "metric_level":
        results = {"level": _public_level_result(executed, plan)}
    else:
        results = _public_change_results(executed, plan)
    return {
        "spec": spec_envelope,
        "results": results,
        "execution_record": _public_execution_record(
            executed, plan, spec, sem, context),
        "assumption_ledger": _assumption_ledger(context),
        "external_reference_check": None,
    }


def _assumption_ledger(context):
    # domain pack이 선언한 미검증 가정은 실행 경로와 무관하게 보존한다. 누락은
    # 보고서의 선언된 불확실성을 조용히 약화시키는 방향의 오류다.
    if context["execution_profile"] == "commerce_extensions":
        return [dict(entry) for entry in COMMERCE_ASSUMPTION_LEDGER]
    return []


def _failed_bundle(spec_envelope, checked):
    return {"spec": spec_envelope, "results": {"query_spec": checked},
            "execution_record": None, "assumption_ledger": [],
            "external_reference_check": None}


def _public_level_result(executed, plan):
    call_id = plan.calls[0].call_id
    result = executed["results"].get(call_id)
    if result is None:
        return {"status": "out_of_domain",
                "violated": [{"check": "plan_output_present", "passed": False,
                              "detail": f"실행 결과 없음: {call_id}"}]}
    if result.get("status") == "result":
        return result["envelope"]
    # evaluate_metric의 canonical 실패 wire 또는 executor의 정규화 실패 dict.
    return result


def _public_change_results(executed, plan):
    results = {}
    for key, call_id in plan.metadata["public_results"].items():
        result = executed["results"].get(call_id)
        if result is None:
            results[key] = {
                "status": "out_of_domain",
                "violated": [{"check": "upstream_execution_stopped",
                              "passed": False,
                              "detail": f"선행 Call 실패로 미실행: {call_id}"}]}
        elif key == "events":
            # legacy kernel 증거 행 passthrough — canonical 사칭 없음.
            results[key] = {name: value for name, value in result.items()
                            if name != "slice"}
        elif result.get("status") != "result":
            results[key] = {name: value for name, value in result.items()
                            if name != "slice"}
        else:
            results[key] = _attribution_wire(result)
    return results


def _attribution_wire(result):
    total = dict(result["total"])
    before = total.get("before")
    if total.get("pct_change") is None and before:
        total["pct_change"] = round(total["delta"] / before * 100, 1)
    value = {
        "metric_ref": result.get("metric_ref"),
        "group_by": result.get("group_by"),
        "unit": result["source_evaluations"]["after"]["unit"],
        "total": total,
        "segments": [{"segment": row["segment"], "before": row["before"],
                      "after": row["after"], "delta": row["delta"]}
                     for row in result["segments"]],
        "checks": result.get("checks", []),
    }
    if "transitions" in result:
        value["transitions"] = result["transitions"]
        value["operator_semantics"] = result.get("operator_semantics")
    operator_ref = ("set_transition@v1" if "transitions" in result
                    else "contribution@v1")
    return {
        "envelope_version": "1", "status": "result",
        "result_type": "Attribution", "value": value,
        "evidence": {
            "operator_ref": operator_ref,
            "provenance_ref": result.get("provenance_ref"),
            "label_ceiling": list(CHANGE_LABEL_CEILING),
        },
    }


def _empty_record(spec, sem, context, limits=None):
    limits = limits or sem.get("question_defaults", {}).get(
        "exploration_budget", {})
    return {
        "route": "c4", "registry": "shadow@v1", "calls": [],
        "operators_considered": {"selected": [], "runtime_rejected": []},
        "budget": {
            "max_depth": limits.get("max_depth", 0),
            "max_segments": limits.get("max_segments", 0),
            "max_hypotheses": limits.get("max_hypotheses", 0),
            "max_operator_calls": limits.get("max_operator_calls", 0),
            "consumed_depth": 0, "segments_examined": 0,
            "hypotheses_examined": 0, "operator_calls": 0,
            "on_exhaustion": "stop_and_report",
        },
        "call_provenance": [],
        "provenance": _public_provenance(spec, sem, context),
        "query_spec_hash": _spec_hash(spec),
        "binding_ledger": [],
    }


def _public_provenance(spec, sem, context):
    return {
        "metric_ref": f"{sem['metric']['id']}@v{sem['metric']['version']}",
        "semantic_model_ref": context["source_ref"],
        "input_snapshot_ref": f"sha256:{_input_hash(context['rows'])}",
        "as_of": spec["as_of"],
    }


def _public_execution_record(executed, plan, spec, sem, context):
    record = dict(executed["execution_record"])
    limits = dict(plan.limits)
    budget = dict(record["budget"])
    budget.setdefault("max_depth", limits.get("max_depth", 0))
    budget.setdefault("max_hypotheses", limits.get("max_hypotheses", 0))
    budget["consumed_depth"] = 1 if budget["operator_calls"] else 0
    budget["hypotheses_examined"] = sum(
        len(result.get("events") or ())
        for result in executed["results"].values()
        if isinstance(result, dict))
    record["budget"] = budget
    executed_calls = {row["call_id"] for row in record["calls"]}
    record["operators_considered"] = {
        "selected": [{"operator": call.operator_ref, "depth": 1}
                     for call in plan.calls if call.call_id in executed_calls],
        "runtime_rejected": [
            {"operator": f"contribution@v1:{dim}",
             "reason": "query scope에서 이미 고정된 차원"}
            for dim in plan.metadata.get("excluded_axes", ())],
    }
    record["call_provenance"] = record.pop("provenance")
    record["provenance"] = _public_provenance(spec, sem, context)
    record["query_spec_hash"] = _spec_hash(spec)
    record["binding_ledger"] = [entry.to_dict() for entry in plan.binding_ledger]
    record.pop("shadow_only", None)
    record["route"] = "c4"
    return record
