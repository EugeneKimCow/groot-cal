"""E-018 — inspect_level 질의의 가역 C4 라우팅.

기본 selector는 현행 경로를 그대로 보존한다. 이 모듈은 명시적으로 선택된 호출만
Query Spec을 C4 Plan으로 컴파일·실행하고, 결과를 canonical Result Envelope wire로
public bundle 경계에 노출한다. metric-level이 아닌 Plan은 침묵 fallback 없이
거부한다. 실행 기록은 legacy operator 이름을 사칭하지 않고 Plan·binding identity를
보존한다.
"""
import dataclasses

from pipeline import COMMERCE_ASSUMPTION_LEDGER, _input_hash, _spec_hash
from query_spec import validate_query_spec
from shadow_executor import execute_shadow_plan
from shadow_plan import compile_shadow_plan


ROUTED_CAPABILITY = "metric_level"


def refuse_non_level(spec_envelope, family):
    """라우팅 밖 operation family의 명시적 거부. 현행 경로 실행은 caller 선택."""
    return {
        "spec": spec_envelope,
        "results": {"route": {
            "status": "out_of_domain",
            "violated": [{
                "check": "route_capability", "passed": False,
                "detail": (f"c4_level 경로는 inspect_level만 실행: {family}. "
                           "현행 경로 실행은 route='c4_level_or_current'로 명시 선택"),
            }],
        }},
        "execution_record": None, "assumption_ledger": [],
        "external_reference_check": None,
    }


def execute_level_query(spec_envelope, context, contexts=None):
    """inspect_level Query Spec을 C4 경로로 실행해 public bundle로 반환한다.

    입력 가용성을 포함한 semantic validation은 현행 경로와 같은 지점(query_spec)
    에서 실패해 실패 위치의 공개 경계가 보존된다.
    """
    spec = spec_envelope["query_spec"]
    sem = context["sem"]
    checked = validate_query_spec(spec, sem, context["rows"])
    if checked["status"] != "result":
        return _failed_bundle(spec_envelope, checked)

    compiled = compile_shadow_plan(spec_envelope, sem)
    if compiled["status"] != "result":
        return _failed_bundle(spec_envelope, compiled)

    plan = compiled["plan"]
    if plan.metadata.get("capability") != ROUTED_CAPABILITY:
        return refuse_non_level(spec_envelope, plan.metadata.get("intent_family"))
    plan = dataclasses.replace(plan, metadata={
        **plan.metadata, "shadow_only": False, "route": "c4_level"})

    executed = execute_shadow_plan(plan, contexts=contexts)
    return {
        "spec": spec_envelope,
        "results": {"level": _public_level_result(executed, plan)},
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


def _public_execution_record(executed, plan, spec, sem, context):
    record = dict(executed["execution_record"])
    limits = dict(plan.limits)
    budget = dict(record["budget"])
    budget.setdefault("max_depth", limits.get("max_depth", 0))
    budget.setdefault("max_hypotheses", limits.get("max_hypotheses", 0))
    budget["consumed_depth"] = 1 if budget["operator_calls"] else 0
    budget["hypotheses_examined"] = 0
    record["budget"] = budget
    record["operators_considered"] = {
        "selected": [{"operator": call.operator_ref, "depth": 1}
                     for call in plan.calls[:budget["operator_calls"]]],
        "runtime_rejected": [],
    }
    record["call_provenance"] = record.pop("provenance")
    record["provenance"] = {
        "metric_ref": f"{sem['metric']['id']}@v{sem['metric']['version']}",
        "semantic_model_ref": context["source_ref"],
        "input_snapshot_ref": f"sha256:{_input_hash(context['rows'])}",
        "as_of": spec["as_of"],
    }
    record["query_spec_hash"] = _spec_hash(spec)
    record["binding_ledger"] = [entry.to_dict() for entry in plan.binding_ledger]
    record.pop("shadow_only", None)
    record["route"] = "c4_level"
    return record
