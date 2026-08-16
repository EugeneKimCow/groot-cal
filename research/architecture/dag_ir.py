"""E-004 research prototype: generic calls plus typed result references.

The prototype deliberately reuses the current contribution kernel. It tests
whether requested and nested drilldowns need a new diagnostic subsystem or
only an executable plan with dependencies and deterministic selectors.
"""
from dataclasses import dataclass


class PlanError(ValueError):
    pass


@dataclass(frozen=True)
class Call:
    node_id: str
    operator: str
    inputs: dict
    when: dict | None = None


@dataclass(frozen=True)
class Plan:
    calls: tuple
    outputs: tuple


def _dig(value, path):
    for part in path.split(".") if path else []:
        if isinstance(value, list):
            value = value[int(part)]
        else:
            value = value[part]
    return value


def _resolve(value, results):
    if isinstance(value, dict) and set(value) == {"ref", "path"}:
        ref = value["ref"]
        if ref not in results:
            raise PlanError(f"unresolved or forward reference: {ref}")
        return _dig(results[ref], value["path"])
    if isinstance(value, dict):
        return {key: _resolve(item, results) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, results) for item in value]
    return value


def execute_plan(plan, operators):
    results = {}
    seen = set()
    for call in plan.calls:
        if call.node_id in seen:
            raise PlanError(f"duplicate node id: {call.node_id}")
        seen.add(call.node_id)
        operator = operators.get(call.operator)
        if operator is None:
            raise PlanError(f"unregistered operator: {call.operator}")
        if call.when is not None:
            condition = _resolve(call.when, results)
            if not isinstance(condition, bool):
                raise PlanError(f"guard must resolve to bool: {call.node_id}")
            if not condition:
                results[call.node_id] = {"status": "skipped",
                                         "reason": "typed guard evaluated false"}
                continue
        inputs = _resolve(call.inputs, results)
        results[call.node_id] = operator(**inputs)
    missing = set(plan.outputs) - set(results)
    if missing:
        raise PlanError(f"missing outputs: {sorted(missing)}")
    return {node_id: results[node_id] for node_id in plan.outputs}, results


def select_max_abs(rows, field):
    if not rows:
        raise PlanError("cannot select from empty rows")
    selected = max(rows, key=lambda row: abs(row[field]))
    return {"status": "result", "output_type": "Selection",
            "value": selected["segment"], "row": selected,
            "selection": {"kind": "max_abs", "field": field}}


def greater_than(value, threshold):
    return {"status": "result", "output_type": "Predicate",
            "value": value > threshold, "observed": value,
            "threshold": threshold}
