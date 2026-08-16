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


def compile_shadow_plan(envelope_or_spec, sem, registry=None):
    """Compile the current narrow Query Spec without changing execution routing.

    The binding ledger makes unsupported or newly introduced clauses visible.  A
    plan is never returned when a clause would otherwise be silently discarded.
    """
    spec = envelope_or_spec.get("query_spec", envelope_or_spec)
    checked = validate_query_spec(spec, sem)
    if checked["status"] != "result":
        return checked

    ledger = _binding_ledger(spec)
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

    if family == "inspect_level":
        calls = (Call("n001", "evaluate_metric@v1", {
            "metric": metric_ref, "slice": focal_slice,
        }),)
        outputs = (Ref("n001"),)
        capability = "metric_level"
    elif family == "explain_change":
        comparison_period = spec["comparison"].get("period")
        comparison_slice = Slice.from_scope(comparison_period, spec["as_of"], scope)
        calls = (
            Call("n001", "evaluate_metric@v1", {
                "metric": metric_ref, "slice": comparison_slice,
            }),
            Call("n002", "evaluate_metric@v1", {
                "metric": metric_ref, "slice": focal_slice,
            }),
            Call("n003", "delta@v1", {
                "before": Ref("n001", "value"),
                "after": Ref("n002", "value"),
            }),
        )
        outputs = (Ref("n003"),)
        capability = "period_delta"
    else:
        return {
            "status": "out_of_domain",
            "violated": [{
                "check": "operator_available", "passed": False,
                "detail": f"unsupported operation family: {family}",
            }],
            "binding_ledger": [entry.to_dict() for entry in ledger],
        }

    plan = Plan(
        calls=calls,
        outputs=outputs,
        binding_ledger=ledger,
        limits=sem.get("question_defaults", {}).get("exploration_budget", {}),
        metadata={
            "capability": capability,
            "intent_family": family,
            "intent_fulfillment": (
                "partial_comparison_root" if family == "explain_change" else "complete"),
            "question": spec["question"],
            "requested_output": spec.get("requested_output", {}),
            "defaults_applied": spec.get("defaults_applied", []),
            "shadow_only": True,
        },
    )
    registry = registry or ShadowOperatorRegistry()
    plan_check = registry.validate_plan(plan, {metric_ref: metric})
    if plan_check["status"] != "result":
        return {**plan_check, "binding_ledger": [entry.to_dict() for entry in ledger]}
    return {"status": "result", "plan": plan, "plan_hash": plan.plan_hash(),
            "validation": plan_check}


def _binding_ledger(spec):
    family = (spec.get("intent") or {}).get("operation_family")
    comparison_consumers = (("compiler", "delta@v1")
                            if family == "explain_change" else ("compiler",))
    intent_note = ("Increment 1 compiles only the period-comparison root; "
                   "driver explanation remains outside shadow scope"
                   if family == "explain_change" else None)
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
