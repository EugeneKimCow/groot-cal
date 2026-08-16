"""E-003 research prototype: one metric-evaluation node.

This module is intentionally isolated from the production slice. It tests
whether aggregation algebra, rather than nominal metric type, is sufficient to
evaluate one bound period and scope.
"""
from dataclasses import dataclass


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class Slice:
    period: str
    predicates: tuple = ()

    def matches(self, row):
        if row.get("month") != self.period:
            return False
        return all(row.get(field) in values for field, values in self.predicates)


@dataclass(frozen=True)
class EvaluateMetric:
    node_id: str
    metric_ref: str
    slice: Slice


def _bound_fields(metric):
    bindings = metric.get("bindings") or {}
    fields = list(bindings.values())
    if len(fields) != len(set(fields)):
        raise ContractError("duplicate field bindings are ambiguous")
    return bindings


def _select(rows, data_slice):
    selected = [row for row in rows if data_slice.matches(row)]
    if not selected:
        raise ContractError(f"no rows for {data_slice.period}")
    return selected


def evaluate_metric(node, metric, rows):
    """Evaluate from declared aggregation algebra; never branch on metric type."""
    bindings = _bound_fields(metric)
    selected = _select(rows, node.slice)
    rule = (metric.get("properties") or {}).get("aggregation_rule")

    if rule == "sum" or rule == "semi_additive:last":
        field = bindings.get("value_field")
        if not field:
            raise ContractError(f"{rule} requires value_field")
        value = sum(row[field] for row in selected)
        expression = {"op": "sum", "field": field}
        if rule == "semi_additive:last":
            time_semantics = metric.get("properties", {}).get("time_semantics")
            if time_semantics != "period_end":
                raise ContractError("semi_additive:last requires period_end semantics")
            expression["time_selection"] = "period_end"
        components = {"sum": value}
    elif rule == "denominator_weighted_mean":
        numerator_field = bindings.get("numerator_field")
        denominator_field = bindings.get("denominator_field")
        if not numerator_field or not denominator_field:
            raise ContractError("ratio_of_sums requires numerator and denominator")
        numerator = sum(row[numerator_field] for row in selected)
        denominator = sum(row[denominator_field] for row in selected)
        if denominator == 0:
            raise ContractError("ratio_of_sums denominator is zero")
        value = numerator / denominator
        expression = {
            "op": "ratio",
            "numerator": {"op": "sum", "field": numerator_field},
            "denominator": {"op": "sum", "field": denominator_field},
        }
        components = {"numerator": numerator, "denominator": denominator}
    elif rule == "non_aggregable" and bindings.get("entity_id_field"):
        field = bindings["entity_id_field"]
        if any(row.get(field) is None for row in selected):
            raise ContractError("cardinality requires non-null entity ids")
        value = len({row[field] for row in selected})
        expression = {"op": "cardinality", "field": field}
        components = {"cardinality": value}
    else:
        raise ContractError(f"unsupported aggregation algebra: {rule}")

    return {
        "status": "result",
        "output_type": "MetricValue",
        "node_id": node.node_id,
        "metric_ref": node.metric_ref,
        "slice": {"period": node.slice.period,
                  "predicates": [[field, list(values)]
                                 for field, values in node.slice.predicates]},
        "expression": expression,
        "value": value,
        "unit": metric["unit"],
        "components": components,
    }


def scope(**predicates):
    return tuple(sorted(
        (key, tuple(value if isinstance(value, list) else [value]))
        for key, value in predicates.items()))
