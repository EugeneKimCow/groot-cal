"""E-017 deterministic executor for shadow C4 Plans.

This module is deliberately not imported by ``engine``. It executes only the
closed shadow registry and uses the normalized E-013 metric evaluator as its
data/aggregation boundary.
"""
import json
from pathlib import Path

from analytical_ir import Ref, Slice
from catalog import load_metric_catalog
from metric_evaluator import evaluate_metric
from shadow_registry import ShadowOperatorRegistry


HERE = Path(__file__).parent


def execute_shadow_plan(plan, contexts=None, registry=None, scenario_path=None):
    contexts = contexts or load_metric_catalog()
    registry = registry or ShadowOperatorRegistry()
    context_map = {
        f"{row['sem']['metric']['id']}@v{row['sem']['metric']['version']}": row
        for row in contexts
    }
    checked = registry.validate_plan(
        plan, {ref: row["sem"]["metric"] for ref, row in context_map.items()})
    if checked["status"] != "result":
        return {"status": "out_of_domain", "violated": checked["violated"],
                "results": {}, "execution_record": None}

    limits = {"max_operator_calls": plan.limits.get("max_operator_calls", 10),
              "max_segments": plan.limits.get("max_segments", 40)}
    record = {
        "plan_hash": plan.plan_hash(), "registry": "shadow@v1", "calls": [],
        "budget": {**limits, "operator_calls": 0, "segments_examined": 0,
                   "on_exhaustion": "stop_and_report"},
        "provenance": [], "shadow_only": True,
    }
    results = {}
    scenario_path = Path(scenario_path) if scenario_path else HERE / "plan_vintage.json"

    for call in plan.calls:
        if record["budget"]["operator_calls"] + 1 > limits["max_operator_calls"]:
            results[call.call_id] = _budget_failure("max_operator_calls")
            record["calls"].append(_call_record(call, "budget_exhausted"))
            break
        try:
            inputs = {name: _resolve(value, results)
                      for name, value in call.inputs.items()}
        except (KeyError, TypeError, ValueError) as error:
            results[call.call_id] = _failure("ref_resolved", str(error))
            record["calls"].append(_call_record(call, "out_of_domain"))
            break

        record["budget"]["operator_calls"] += 1
        result = _invoke(call.operator_ref, inputs, context_map, record,
                         scenario_path)
        segments = len(result.get("segments", ()))
        if record["budget"]["segments_examined"] + segments > limits["max_segments"]:
            result = _budget_failure("max_segments")
        else:
            record["budget"]["segments_examined"] += segments
        result.setdefault("operator_ref", call.operator_ref)
        result.setdefault("provenance_ref", f"shadow:{call.call_id}")
        results[call.call_id] = result
        record["calls"].append(_call_record(call, result["status"]))
        if result["status"] != "result":
            break

    selected = {}
    for output in plan.outputs:
        key = f"{output.call_id}.{output.path}" if output.path else output.call_id
        try:
            selected[key] = _resolve(output, results)
        except (KeyError, TypeError, ValueError):
            continue
    if len(selected) == len(plan.outputs) and all(
            isinstance(value, dict) and value.get("status") == "result"
            for value in selected.values()):
        status = "result"
    else:
        terminal = [row.get("status") for row in results.values()
                    if row.get("status") != "result"]
        status = next((candidate for candidate in
                       ("budget_exhausted", "suspended", "out_of_domain")
                       if candidate in terminal), "out_of_domain")
    return {"status": status, "results": results, "outputs": selected,
            "execution_record": record, "validation": checked}


def _invoke(operator_ref, inputs, contexts, record, scenario_path):
    if operator_ref == "evaluate_metric@v1":
        return _evaluate(inputs, contexts, record)
    if operator_ref == "delta@v1":
        return {"status": "result", "output_type": "Delta",
                "value": inputs["after"] - inputs["before"], "segments": [],
                "label_ceiling": "data_confirmed"}
    if operator_ref == "contribution@v1":
        return _contribution(inputs["before"], inputs["after"])
    if operator_ref == "set_transition@v1":
        return _set_transition(inputs["before"], inputs["after"])
    if operator_ref == "rank@v1":
        return _rank(inputs)
    if operator_ref == "align_metrics@v1":
        return {"status": "result", "output_type": "MetricAlignment",
                "metrics": list(inputs["metrics"]), "segments": [],
                "label_ceiling": "data_confirmed"}
    if operator_ref == "drilldown@v1":
        return _drilldown(inputs, contexts, record)
    if operator_ref == "plan_gap@v1":
        return _plan_gap(inputs, contexts, record, scenario_path)
    return _failure("operator_registered", f"unregistered operator {operator_ref}")


def _evaluate(inputs, contexts, record):
    metric_ref = inputs["metric"]
    context = contexts.get(metric_ref)
    if context is None:
        return _failure("metric_registered", metric_ref)
    metric_slice = inputs["slice"]
    group_by = inputs.get("group_by") or []
    if len(group_by) > 1:
        return _failure("single_axis_evaluation",
                        f"one evaluation Call may group one axis: {group_by}")
    if not group_by:
        envelope = evaluate_metric(
            context["sem"]["metric"], context["sem"]["dimensions"],
            context["rows"], metric_slice, context["source_ref"])
        record["provenance"].append({
            "metric_ref": metric_ref, "slice": metric_slice.to_dict(),
            "provenance_ref": envelope.provenance_ref,
        })
        wire = envelope.to_dict()
        if envelope.status != "result":
            return wire
        return {
            "status": "result", "output_type": "MetricEvaluation",
            "metric_ref": metric_ref, "slice": metric_slice,
            "value": envelope.value["value"], "unit": envelope.value["unit"],
            "segments": [], "evidence": wire["evidence"],
            "label_ceiling": envelope.label_ceiling,
            "envelope": wire,
        }

    dimension = group_by[0]
    dimension_contract = context["sem"]["dimensions"].get(dimension)
    if dimension_contract is None:
        return _failure("dimension_registered", dimension)
    existing_scope = {name: list(values) for name, values in metric_slice.predicates}
    candidates = dimension_contract["values"]
    if dimension in existing_scope:
        candidates = [value for value in candidates
                      if value in existing_scope[dimension]]
    segments = []
    evidence = []
    for value in candidates:
        scope = {**existing_scope, dimension: [value]}
        segment_slice = Slice.from_scope(metric_slice.period, metric_slice.as_of, scope)
        envelope = evaluate_metric(
            context["sem"]["metric"], context["sem"]["dimensions"],
            context["rows"], segment_slice, context["source_ref"])
        if envelope.status != "result":
            return envelope.to_dict()
        segment = {"segment": value, "value": envelope.value["value"]}
        metric = context["sem"]["metric"]
        if metric["type"] == "distinct":
            entity_field = metric["bindings"]["entity_id_field"]
            segment["entities"] = sorted({
                row[entity_field] for row in context["rows"]
                if row.get("month") == metric_slice.period
                and row.get(dimension) == value
                and all(row.get(name) in values
                        for name, values in existing_scope.items())
            })
        segments.append(segment)
        evidence.append(envelope.provenance_ref)
    record["provenance"].append({
        "metric_ref": metric_ref, "slice": metric_slice.to_dict(),
        "group_by": dimension, "provenance_refs": evidence,
    })
    return {
        "status": "result", "output_type": "MetricEvaluation",
        "metric_ref": metric_ref, "slice": metric_slice,
        "group_by": dimension, "value": sum(row["value"] for row in segments),
        "unit": context["sem"]["metric"]["unit"], "segments": segments,
        "label_ceiling": "data_confirmed",
    }


def _contribution(before, after):
    if (before.get("metric_ref") != after.get("metric_ref")
            or before.get("group_by") != after.get("group_by")):
        return _failure("contribution_inputs_compatible",
                        "metric and group_by must match")
    before_rows = {row["segment"]: row["value"] for row in before["segments"]}
    after_rows = {row["segment"]: row["value"] for row in after["segments"]}
    segment_order = list(before_rows) + [name for name in after_rows
                                         if name not in before_rows]
    rows = []
    for segment in segment_order:
        old, new = before_rows.get(segment, 0), after_rows.get(segment, 0)
        rows.append({"segment": segment, "before": old, "after": new,
                     "delta": new - old})
    rows.sort(key=lambda row: -abs(row["delta"]))
    total = after["value"] - before["value"]
    closed = sum(row["delta"] for row in rows) == total
    if not closed:
        return _failure("contribution_identity", "segment deltas do not close")
    return {
        "status": "result", "output_type": "Attribution",
        "metric_ref": before["metric_ref"], "group_by": before.get("group_by"),
        "before_slice": before["slice"], "after_slice": after["slice"],
        "total": {"before": before["value"], "after": after["value"],
                  "delta": total},
        "value": total, "segments": rows,
        "checks": [{"check": "contribution_identity", "passed": True}],
        "source_evaluations": {"before": before, "after": after},
        "label_ceiling": "data_confirmed",
    }


def _set_transition(before, after):
    if (before.get("metric_ref") != after.get("metric_ref")
            or before.get("group_by") != after.get("group_by")):
        return _failure("set_transition_inputs_compatible",
                        "metric and functional dimension must match")
    if any("entities" not in row for row in before["segments"] + after["segments"]):
        return _failure("entity_sets_available", "distinct entity sets required")
    before_assignment = {entity: row["segment"] for row in before["segments"]
                         for entity in row["entities"]}
    after_assignment = {entity: row["segment"] for row in after["segments"]
                        for entity in row["entities"]}
    old_entities, new_entities = set(before_assignment), set(after_assignment)
    transitions = {
        "entrants": sorted(new_entities - old_entities),
        "exits": sorted(old_entities - new_entities),
        "migrations": sorted([
            {"entity": entity, "before": before_assignment[entity],
             "after": after_assignment[entity]}
            for entity in old_entities & new_entities
            if before_assignment[entity] != after_assignment[entity]
        ], key=lambda row: row["entity"]),
    }
    result = _contribution(before, after)
    if result["status"] == "result":
        result["operator_semantics"] = "set_transition"
        result["transitions"] = transitions
    return result


def _rank(inputs):
    source = inputs["input"]
    rows = list(source.get("segments") or [])
    if not rows:
        return _failure("rank_input", "attribution segments required")
    reverse = inputs["order"] == "descending"
    key = (lambda row: abs(row["delta"])) if inputs["measure"] == "contribution" \
        else (lambda row: row.get("value", row.get("delta")))
    ranked = sorted(rows, key=key, reverse=reverse)[:inputs["limit"]]
    return {"status": "result", "output_type": "RankedSelection",
            "segments": ranked, "selection": ranked[0], "source": source,
            "label_ceiling": source.get("label_ceiling")}


def _drilldown(inputs, contexts, record):
    selection = inputs["selection"]
    source = selection.get("source")
    selected = selection.get("selection")
    if not source or not selected:
        return _failure("drilldown_input", "ranked source and selection required")
    before = source["source_evaluations"]["before"]
    after = source["source_evaluations"]["after"]
    parent_dimension = source["group_by"]
    parent_value = selected["segment"]

    def child_inputs(evaluation):
        scope = {name: list(values) for name, values in evaluation["slice"].predicates}
        scope[parent_dimension] = [parent_value]
        return {"metric": evaluation["metric_ref"],
                "slice": Slice.from_scope(
                    evaluation["slice"].period, evaluation["slice"].as_of, scope),
                "group_by": [inputs["group_by"]]}

    child_before = _evaluate(child_inputs(before), contexts, record)
    if child_before["status"] != "result":
        return child_before
    child_after = _evaluate(child_inputs(after), contexts, record)
    if child_after["status"] != "result":
        return child_after
    result = _contribution(child_before, child_after)
    if result["status"] == "result":
        result["parent_scope"] = {parent_dimension: parent_value}
    return result


def _plan_gap(inputs, contexts, record, scenario_path):
    metric_ref = inputs["metric"]
    context = contexts.get(metric_ref)
    if context is None:
        return _failure("metric_registered", metric_ref)
    store = json.loads(scenario_path.read_text())["vintages"]
    metric_slice = inputs["slice"]
    vintage = next((row for row in store
                    if row["vintage_id"] == inputs["vintage_id"]
                    and row["plan_month"] == metric_slice.period), None)
    if vintage is None:
        return _failure("scenario_registered", inputs["vintage_id"])
    if "channel" not in context["sem"]["dimensions"]:
        return _failure("scenario_dimension_registered", "channel")
    actual = _evaluate({"metric": metric_ref, "slice": metric_slice,
                        "group_by": ["channel"]}, contexts, record)
    if actual["status"] != "result":
        return actual
    actual_by_channel = {row["segment"]: row["value"]
                         for row in actual["segments"]}
    scope = {name: set(values) for name, values in metric_slice.predicates}
    channels = [name for name in vintage["channel_u"]
                if "channel" not in scope or name in scope["channel"]]
    segments = []
    for channel in channels:
        plan = vintage["channel_u"][channel]
        got = actual_by_channel.get(channel, 0)
        segments.append({"segment": channel, "plan": plan, "actual": got,
                         "delta": got - plan})
    plan_total = sum(row["plan"] for row in segments)
    actual_total = sum(row["actual"] for row in segments)
    return {"status": "result", "output_type": "Attribution",
            "metric_ref": metric_ref, "scenario_ref": inputs["vintage_id"],
            "total": {"plan": plan_total, "actual": actual_total,
                      "delta": actual_total - plan_total},
            "value": actual_total - plan_total, "segments": segments,
            "label_ceiling": "data_confirmed"}


def _resolve(value, results):
    if isinstance(value, Ref):
        current = results[value.call_id]
        for part in value.path.split(".") if value.path else ():
            current = current[int(part)] if isinstance(current, list) else current[part]
        return current
    if isinstance(value, tuple):
        return tuple(_resolve(item, results) for item in value)
    if isinstance(value, list):
        return [_resolve(item, results) for item in value]
    return value


def _failure(check, detail):
    return {"status": "out_of_domain", "output_type": "Failure",
            "violated": [{"check": check, "passed": False, "detail": detail}],
            "segments": []}


def _budget_failure(kind):
    return {"status": "budget_exhausted", "output_type": "Failure",
            "violated": [{"check": "exploration_budget", "passed": False,
                          "detail": kind}], "segments": []}


def _call_record(call, status):
    return {"call_id": call.call_id, "operator_ref": call.operator_ref,
            "status": status}
