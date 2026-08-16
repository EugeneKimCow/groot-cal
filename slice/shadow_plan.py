"""Query Spec v1 to Analytical Plan v1 compiler used only in shadow tests."""
from analytical_ir import BindingLedgerEntry, Call, Plan, Ref, Slice
from query_spec import validate_query_spec
from shadow_registry import ShadowOperatorRegistry


TOP_LEVEL_CLAUSES = {
    "spec_version", "question", "subject", "intent", "scope",
    "focal_period", "comparison", "as_of", "requested_output",
    "defaults_applied",
}
NESTED_CLAUSES = {
    "subject": {"metric_id", "metric_version"},
    "intent": {"operation_family"},
    "comparison": {"kind", "period", "vintage_id"},
}


def compile_shadow_plan(envelope_or_spec, sem, registry=None,
                        include_event_scan=False):
    """Compile the current narrow Query Spec without changing execution routing.

    The binding ledger makes unsupported or newly introduced clauses visible.  A
    plan is never returned when a clause would otherwise be silently discarded.
    ``include_event_scan``은 commerce domain pack의 이벤트 대조 idiom을 명시적
    Call로 plan에 편입하는 caller 선택이다.
    """
    spec = envelope_or_spec.get("query_spec", envelope_or_spec)
    checked = validate_query_spec(spec, sem)
    if checked["status"] != "result":
        return checked

    ledger = _binding_ledger(spec, sem)
    unconsumed = [entry for entry in ledger if entry.state == "unconsumed"]
    if unconsumed:
        return {
            "status": "out_of_domain",
            "violated": [{
                "check": "intent_clause_consumed", "passed": False,
                "detail": f"unconsumed Query Spec clause: {entry.clause}",
            } for entry in unconsumed],
            "binding_ledger": [entry.to_dict() for entry in ledger],
        }

    family = spec["intent"]["operation_family"]
    if family == "compare_plan":
        return {
            "status": "out_of_domain",
            "violated": [{
                "check": "operator_available", "passed": False,
                "detail": "scenario comparison is outside Increment 1 shadow scope",
            }],
            "binding_ledger": [entry.to_dict() for entry in ledger],
        }

    metric = sem["metric"]
    metric_ref = f"{metric['id']}@v{metric['version']}"
    scope = spec["scope"]
    focal_slice = Slice.from_scope(spec["focal_period"], spec["as_of"], scope)

    public_results = None
    excluded_axes = ()
    if family == "inspect_level":
        calls = (Call("n001", "evaluate_metric@v1", {
            "metric": metric_ref, "slice": focal_slice,
        }),)
        outputs = (Ref("n001"),)
        capability = "metric_level"
    elif family == "explain_change":
        properties = metric.get("properties", {})
        if metric.get("type") != "distinct" \
                and not properties.get("additive_across_dims"):
            return {
                "status": "out_of_domain",
                "violated": [{"check": "change_operator_available",
                              "passed": False,
                              "detail": f"{metric.get('type')} 변화 연산자 미등록"}],
                "alternatives": ["rate 변화 분해 operator 등록"],
                "binding_ledger": [entry.to_dict() for entry in ledger],
            }
        comparison_period = spec["comparison"].get("period")
        comparison_slice = Slice.from_scope(comparison_period, spec["as_of"], scope)
        identities = metric.get("decomposition_identities") or []
        axis_pool = (identities[0]["dimensions"] if identities
                     else list(sem["dimensions"]))
        axes = [dim for dim in axis_pool if dim not in scope]
        excluded_axes = tuple(dim for dim in axis_pool if dim in scope)
        if not axes:
            return {
                "status": "out_of_domain",
                "violated": [{"check": "decomposition_axis_available",
                              "passed": False,
                              "detail": "scope가 모든 분해 축을 고정함"}],
                "binding_ledger": [entry.to_dict() for entry in ledger],
            }
        comparison_ref = ("set_transition@v1" if metric.get("type") == "distinct"
                          else "contribution@v1")
        key_prefix = "distinct" if metric.get("type") == "distinct" else "contrib"
        call_list, output_list, public_results = [], [], {}
        for index, axis in enumerate(axes, start=1):
            before_id = f"n{index:02d}a"
            after_id = f"n{index:02d}b"
            compare_id = f"n{index:02d}c"
            call_list.append(Call(before_id, "evaluate_metric@v1", {
                "metric": metric_ref, "slice": comparison_slice,
                "group_by": [axis]}))
            call_list.append(Call(after_id, "evaluate_metric@v1", {
                "metric": metric_ref, "slice": focal_slice,
                "group_by": [axis]}))
            call_list.append(Call(compare_id, comparison_ref, {
                "before": Ref(before_id), "after": Ref(after_id)}))
            output_list.append(Ref(compare_id))
            public_results[f"{key_prefix}:{axis}"] = compare_id
        if include_event_scan:
            call_list.append(Call("n090", "event_overlap_scan@v1", {
                "metric": metric_ref, "before_slice": comparison_slice,
                "after_slice": focal_slice}))
            output_list.append(Ref("n090"))
            public_results["events"] = "n090"
        calls = tuple(call_list)
        outputs = tuple(output_list)
        capability = "period_change"
    else:
        return {
            "status": "out_of_domain",
            "violated": [{
                "check": "operator_available", "passed": False,
                "detail": f"unsupported operation family: {family}",
            }],
            "binding_ledger": [entry.to_dict() for entry in ledger],
        }

    metadata = {
        "capability": capability,
        "intent_family": family,
        "intent_fulfillment": (
            "axis_contribution" if family == "explain_change" else "complete"),
        "question": spec["question"],
        "requested_output": spec.get("requested_output", {}),
        "defaults_applied": spec.get("defaults_applied", []),
        "shadow_only": True,
    }
    if public_results is not None:
        metadata["public_results"] = public_results
    if excluded_axes:
        metadata["excluded_axes"] = excluded_axes
    plan = Plan(
        calls=calls,
        outputs=outputs,
        binding_ledger=ledger,
        limits=sem.get("question_defaults", {}).get("exploration_budget", {}),
        metadata=metadata,
    )
    registry = registry or ShadowOperatorRegistry()
    plan_check = registry.validate_plan(plan, {metric_ref: metric})
    if plan_check["status"] != "result":
        return {**plan_check, "binding_ledger": [entry.to_dict() for entry in ledger]}
    return {"status": "result", "plan": plan, "plan_hash": plan.plan_hash(),
            "validation": plan_check}


def _binding_ledger(spec, sem):
    family = (spec.get("intent") or {}).get("operation_family")
    if family == "explain_change":
        comparison_operator = ("set_transition@v1"
                               if sem["metric"].get("type") == "distinct"
                               else "contribution@v1")
        comparison_consumers = ("compiler", comparison_operator)
    else:
        comparison_consumers = ("compiler",)
    intent_note = None
    entries = [
        BindingLedgerEntry("spec_version", "consumed", spec.get("spec_version"),
                           ("compiler",)),
        BindingLedgerEntry("question", "preserved", spec.get("question"),
                           ("plan.metadata",)),
        BindingLedgerEntry("subject", "consumed", spec.get("subject"),
                           ("evaluate_metric@v1",)),
        BindingLedgerEntry("intent.operation_family", "consumed",
                           (spec.get("intent") or {}).get("operation_family"),
                           ("compiler",), intent_note),
        BindingLedgerEntry("scope", "consumed", spec.get("scope"), ("Slice",)),
        BindingLedgerEntry("focal_period", "consumed", spec.get("focal_period"),
                           ("Slice",)),
        BindingLedgerEntry("comparison", "consumed", spec.get("comparison"),
                           comparison_consumers),
        BindingLedgerEntry("as_of", "consumed", spec.get("as_of"), ("Slice",)),
        BindingLedgerEntry("requested_output", "preserved",
                           spec.get("requested_output", {}), ("plan.metadata",),
                           "presentation is downstream of Analytical Plan v1"),
        BindingLedgerEntry("defaults_applied", "preserved",
                           spec.get("defaults_applied", []), ("plan.metadata",)),
    ]

    for key in sorted(set(spec) - TOP_LEVEL_CLAUSES):
        entries.append(BindingLedgerEntry(key, "unconsumed", spec[key]))
    for parent, known in NESTED_CLAUSES.items():
        value = spec.get(parent)
        if isinstance(value, dict):
            for key in sorted(set(value) - known):
                entries.append(BindingLedgerEntry(
                    f"{parent}.{key}", "unconsumed", value[key]))
    return tuple(entries)
