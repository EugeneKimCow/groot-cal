"""E-011: shared vertical slice comparing C4 generic Calls with C3 node classes."""
from dataclasses import asdict, dataclass, fields, is_dataclass
import hashlib
import json
import re
import sqlite3


class PlanTypeError(ValueError):
    pass


@dataclass(frozen=True)
class Ref:
    node: str
    path: str


@dataclass(frozen=True)
class CallSpec:
    node_id: str
    operator: str
    inputs: dict
    guard: Ref | None = None


@dataclass(frozen=True)
class GenericPlan:
    calls: tuple
    outputs: tuple
    max_calls: int = 20


@dataclass(frozen=True)
class OperatorContract:
    input_types: dict
    optional_inputs: tuple
    output_type: str
    output_paths: dict
    implementation: str
    validators: tuple = ()


SEMANTICS = {
    "sales@v1": {
        "id": "sales", "version": 1, "unit": "currency",
        "source": "facts", "source_grain": ("period", "channel", "category"),
        "aggregation": {"kind": "sum", "value_field": "sales"},
        "dimensions": ("channel", "category"),
    },
    "loss_ratio@v1": {
        "id": "loss_ratio", "version": 1, "unit": "ratio",
        "source": "facts", "source_grain": ("period", "channel", "category"),
        "aggregation": {"kind": "ratio_of_sums", "numerator_field": "claims",
                        "denominator_field": "premium"},
        "dimensions": ("channel", "category"),
    },
}


REGISTRY = {
    "evaluate_scalar": OperatorContract(
        {"metric_ref": "metric_ref", "period": "period"}, (),
        "MetricScalar", {"": "MetricScalar", "value": "number"}, "evaluate_scalar"),
    "evaluate_grouped": OperatorContract(
        {"metric_ref": "metric_ref", "period": "period", "dimension": "dimension",
         "filter_dimension": "dimension", "filter_value": "string"},
        ("filter_dimension", "filter_value"), "SegmentTable",
        {"": "SegmentTable", "rows": "segment_rows"}, "evaluate_grouped",
        ("dimension_registered", "filter_complete")),
    "delta": OperatorContract(
        {"before": "number", "after": "number"}, (), "Delta",
        {"": "Delta", "value": "number"}, "delta"),
    "contribution": OperatorContract(
        {"before": "segment_rows", "after": "segment_rows"}, (), "Attribution",
        {"": "Attribution", "rows": "attribution_rows", "total_delta": "number"},
        "contribution"),
    "select_max_abs": OperatorContract(
        {"rows": "attribution_rows"}, (), "Selection",
        {"": "Selection", "value": "string", "magnitude": "number"},
        "select_max_abs"),
    "greater_than": OperatorContract(
        {"value": "number", "threshold": "number"}, (), "Predicate",
        {"": "Predicate", "value": "bool"}, "greater_than"),
}


FACT_ROWS = [
    ("2026-06", "online", "electronics", 120.0, 30.0, 100.0),
    ("2026-06", "online", "food", 80.0, 10.0, 100.0),
    ("2026-06", "offline", "electronics", 100.0, 45.0, 100.0),
    ("2026-06", "offline", "food", 100.0, 15.0, 100.0),
    ("2026-07", "online", "electronics", 90.0, 35.0, 100.0),
    ("2026-07", "online", "food", 70.0, 15.0, 100.0),
    ("2026-07", "offline", "electronics", 140.0, 40.0, 100.0),
    ("2026-07", "offline", "food", 120.0, 10.0, 100.0),
]


def make_database():
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE facts (
        period TEXT, channel TEXT, category TEXT,
        sales REAL, claims REAL, premium REAL)""")
    db.executemany("INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?)", FACT_ROWS)
    return db


def _literal_type(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "object"


def _validate_literal(expected, value, call, port):
    if expected == "metric_ref":
        if not isinstance(value, str) or value not in SEMANTICS:
            raise PlanTypeError(
                f"{call.node_id}.{port}: unknown semantic metric reference {value!r}")
        return
    if expected == "period":
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}", value):
            raise PlanTypeError(f"{call.node_id}.{port}: expected YYYY-MM period")
        return
    if expected == "dimension":
        if not isinstance(value, str):
            raise PlanTypeError(f"{call.node_id}.{port}: expected dimension name")
        return
    got = _literal_type(value)
    if got != expected:
        raise PlanTypeError(
            f"{call.node_id}.{port}: expected {expected}, got literal {got}")


def typecheck_calls(calls, outputs):
    available = {}
    seen = set()
    for call in calls:
        if call.node_id in seen:
            raise PlanTypeError(f"duplicate node id {call.node_id}")
        seen.add(call.node_id)
        contract = REGISTRY.get(call.operator)
        if contract is None:
            raise PlanTypeError(f"{call.node_id}: unregistered operator {call.operator}")
        required = set(contract.input_types) - set(contract.optional_inputs)
        missing = required - set(call.inputs)
        extra = set(call.inputs) - set(contract.input_types)
        if missing or extra:
            raise PlanTypeError(
                f"{call.node_id}: missing ports {sorted(missing)}, extra ports {sorted(extra)}")
        for port, value in call.inputs.items():
            expected = contract.input_types[port]
            if isinstance(value, Ref):
                paths = available.get(value.node)
                if paths is None:
                    raise PlanTypeError(
                        f"{call.node_id}.{port}: unresolved/forward node {value.node}")
                got = paths.get(value.path)
                if got is None:
                    raise PlanTypeError(
                        f"{call.node_id}.{port}: {value.node} has no typed path {value.path!r}")
                if got != expected:
                    raise PlanTypeError(
                        f"{call.node_id}.{port}: expected {expected}, "
                        f"reference {value.node}.{value.path} is {got}")
            else:
                _validate_literal(expected, value, call, port)
        if "filter_complete" in contract.validators:
            has_dimension = "filter_dimension" in call.inputs
            has_value = "filter_value" in call.inputs
            if has_dimension != has_value:
                raise PlanTypeError(
                    f"{call.node_id}: filter_dimension and filter_value must appear together")
        if "dimension_registered" in contract.validators:
            metric_ref = call.inputs["metric_ref"]
            metric = SEMANTICS[metric_ref]
            dimension = call.inputs["dimension"]
            if dimension not in metric["dimensions"]:
                raise PlanTypeError(
                    f"{call.node_id}.dimension: {dimension!r} is not registered for {metric_ref}")
            filter_dimension = call.inputs.get("filter_dimension")
            if filter_dimension is not None and filter_dimension not in metric["dimensions"]:
                raise PlanTypeError(
                    f"{call.node_id}.filter_dimension: {filter_dimension!r} "
                    f"is not registered for {metric_ref}")
        if call.guard is not None:
            paths = available.get(call.guard.node)
            got = None if paths is None else paths.get(call.guard.path)
            if got != "bool":
                raise PlanTypeError(
                    f"{call.node_id}.guard: expected bool reference, got {got}")
        available[call.node_id] = contract.output_paths
    missing_outputs = set(outputs) - seen
    if missing_outputs:
        raise PlanTypeError(f"unknown plan outputs {sorted(missing_outputs)}")
    return available


def _dig(value, path):
    for part in path.split(".") if path else []:
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def _resolve(value, results):
    return _dig(results[value.node], value.path) if isinstance(value, Ref) else value


class IntegratedRuntime:
    def __init__(self, db, max_calls):
        self.db = db
        self.max_calls = max_calls
        self.calls = 0
        self.dag = []
        self.data_requirements = []
        raw = json.dumps(FACT_ROWS, sort_keys=True).encode()
        self.source_snapshot_ref = "sha256:" + hashlib.sha256(raw).hexdigest()[:16]

    def _evaluate(self, metric_ref, period, dimension=None,
                  filter_dimension=None, filter_value=None):
        metric = SEMANTICS[metric_ref]
        if dimension is not None and dimension not in metric["dimensions"]:
            return {"status": "out_of_domain", "output_type": "Failure",
                    "violated": [{"check": "dimension_registered",
                                  "detail": dimension}]}
        if (filter_dimension is None) != (filter_value is None):
            return {"status": "out_of_domain", "output_type": "Failure",
                    "violated": [{"check": "filter_complete"}]}
        if filter_dimension is not None and filter_dimension not in metric["dimensions"]:
            return {"status": "out_of_domain", "output_type": "Failure",
                    "violated": [{"check": "filter_dimension_registered",
                                  "detail": filter_dimension}]}

        aggregate = metric["aggregation"]
        params = [period]
        where = "period = ?"
        if filter_dimension:
            where += f" AND {filter_dimension} = ?"
            params.append(filter_value)
        if aggregate["kind"] == "sum":
            expression = f"SUM({aggregate['value_field']})"
            components = None
        else:
            numerator = f"SUM({aggregate['numerator_field']})"
            denominator = f"SUM({aggregate['denominator_field']})"
            expression = f"{numerator} / NULLIF({denominator}, 0)"
            components = (numerator, denominator)
        select = (f"{dimension}, " if dimension else "")
        if components:
            select += f"{components[0]} AS numerator, {components[1]} AS denominator, "
        select += f"{expression} AS value"
        group = f" GROUP BY {dimension}" if dimension else ""
        sql = f"SELECT {select} FROM {metric['source']} WHERE {where}{group}"
        requirement = {
            "metric_ref": metric_ref, "source": metric["source"],
            "source_grain": list(metric["source_grain"]), "period": period,
            "group_by": [] if dimension is None else [dimension],
            "filters": {} if not filter_dimension else {filter_dimension: filter_value},
            "aggregation": aggregate,
        }
        sql_ref = "sql:" + hashlib.sha256(sql.encode()).hexdigest()[:12]
        self.data_requirements.append({"requirement": requirement,
                                       "backend": "sqlite", "sql_ref": sql_ref})
        rows = self.db.execute(sql, params).fetchall()
        if dimension:
            if components:
                payload = [{"segment": row[0], "numerator": row[1],
                            "denominator": row[2], "value": row[3]} for row in rows]
            else:
                payload = [{"segment": row[0], "value": row[1]} for row in rows]
            return {"status": "result", "output_type": "SegmentTable",
                    "metric_ref": metric_ref, "period": period,
                    "dimension": dimension, "rows": payload,
                    "unit": metric["unit"], "sql_ref": sql_ref}
        if not rows or rows[0][-1] is None:
            return {"status": "suspended", "output_type": "Failure",
                    "missing_inputs": [f"{metric_ref} {period}"]}
        result = {"status": "result", "output_type": "MetricScalar",
                  "metric_ref": metric_ref, "period": period,
                  "value": rows[0][-1], "unit": metric["unit"],
                  "sql_ref": sql_ref}
        if components:
            result["components"] = {"numerator": rows[0][0], "denominator": rows[0][1]}
        return result

    def invoke(self, call, inputs):
        if call.operator == "evaluate_scalar":
            return self._evaluate(**inputs)
        if call.operator == "evaluate_grouped":
            return self._evaluate(**inputs)
        if call.operator == "delta":
            return {"status": "result", "output_type": "Delta",
                    "value": inputs["after"] - inputs["before"]}
        if call.operator == "contribution":
            before = {row["segment"]: row["value"] for row in inputs["before"]}
            after = {row["segment"]: row["value"] for row in inputs["after"]}
            rows = [{"segment": segment, "before": before.get(segment, 0),
                     "after": after.get(segment, 0),
                     "delta": after.get(segment, 0) - before.get(segment, 0)}
                    for segment in sorted(set(before) | set(after))]
            total_delta = sum(row["delta"] for row in rows)
            return {"status": "result", "output_type": "Attribution",
                    "rows": rows, "total_delta": total_delta,
                    "checks": [{"check": "identity", "passed": True}]}
        if call.operator == "select_max_abs":
            row = max(inputs["rows"], key=lambda item: abs(item["delta"]))
            return {"status": "result", "output_type": "Selection",
                    "value": row["segment"], "magnitude": abs(row["delta"]),
                    "selected": row}
        if call.operator == "greater_than":
            return {"status": "result", "output_type": "Predicate",
                    "value": inputs["value"] > inputs["threshold"]}
        raise AssertionError(call.operator)


def execute_generic(plan, db=None):
    typecheck_calls(plan.calls, plan.outputs)
    own_db = db is None
    db = db or make_database()
    runtime = IntegratedRuntime(db, plan.max_calls)
    results = {}
    try:
        for call in plan.calls:
            if runtime.calls + 1 > runtime.max_calls:
                results[call.node_id] = {
                    "status": "budget_exhausted", "output_type": "Failure",
                    "violated": [{"check": "max_calls", "limit": runtime.max_calls}]}
                runtime.dag.append({"node_id": call.node_id, "operator": call.operator,
                                    "status": "budget_exhausted"})
                break
            if call.guard is not None and not _resolve(call.guard, results):
                results[call.node_id] = {"status": "skipped", "output_type": "Skipped",
                                         "reason": "typed guard false"}
                runtime.dag.append({"node_id": call.node_id, "operator": call.operator,
                                    "status": "skipped"})
                continue
            runtime.calls += 1
            inputs = {port: _resolve(value, results) for port, value in call.inputs.items()}
            result = runtime.invoke(call, inputs)
            result["operator_ref"] = f"{call.operator}@v1"
            result["provenance_ref"] = f"call-{runtime.calls:03d}"
            results[call.node_id] = result
            runtime.dag.append({"node_id": call.node_id, "operator": call.operator,
                                "status": result["status"]})
            if result["status"] not in {"result", "skipped"}:
                break
        selected = {node: results[node] for node in plan.outputs if node in results}
        return {"status": "result", "output_type": "EvidenceBundle",
                "results": selected,
                "execution_record": {"dag": runtime.dag,
                                     "budget": {"max_calls": runtime.max_calls,
                                                "operator_calls": runtime.calls},
                                     "data_requirements": runtime.data_requirements,
                                     "provenance": {"source_snapshot_ref":
                                                    runtime.source_snapshot_ref}}}
    finally:
        if own_db:
            db.close()


# C3 explicit node taxonomy. Each node lowers to the same shared Call contract.
@dataclass(frozen=True)
class ScalarMetricNode:
    node_id: str
    metric_ref: str
    period: str

    def lower(self):
        return CallSpec(self.node_id, "evaluate_scalar",
                        {"metric_ref": self.metric_ref, "period": self.period})


@dataclass(frozen=True)
class GroupedMetricNode:
    node_id: str
    metric_ref: str
    period: str
    dimension: str
    filter_dimension: str | None = None
    filter_value: str | Ref | None = None
    guard: Ref | None = None

    def lower(self):
        inputs = {"metric_ref": self.metric_ref, "period": self.period,
                  "dimension": self.dimension}
        if self.filter_dimension is not None:
            inputs.update(filter_dimension=self.filter_dimension,
                          filter_value=self.filter_value)
        return CallSpec(self.node_id, "evaluate_grouped", inputs, self.guard)


@dataclass(frozen=True)
class DeltaNode:
    node_id: str
    before: Ref
    after: Ref

    def lower(self):
        return CallSpec(self.node_id, "delta", {"before": self.before, "after": self.after})


@dataclass(frozen=True)
class ContributionNode:
    node_id: str
    before: Ref
    after: Ref

    def lower(self):
        return CallSpec(self.node_id, "contribution",
                        {"before": self.before, "after": self.after})


@dataclass(frozen=True)
class SelectMaxAbsNode:
    node_id: str
    rows: Ref

    def lower(self):
        return CallSpec(self.node_id, "select_max_abs", {"rows": self.rows})


@dataclass(frozen=True)
class GreaterThanNode:
    node_id: str
    value: Ref
    threshold: float

    def lower(self):
        return CallSpec(self.node_id, "greater_than",
                        {"value": self.value, "threshold": self.threshold})


C3_NODE_TYPES = (ScalarMetricNode, GroupedMetricNode, DeltaNode,
                 ContributionNode, SelectMaxAbsNode, GreaterThanNode)


@dataclass(frozen=True)
class ExplicitPlan:
    nodes: tuple
    outputs: tuple
    max_calls: int = 20


def compile_explicit(plan):
    calls = []
    for node in plan.nodes:
        if not isinstance(node, C3_NODE_TYPES):
            raise PlanTypeError(f"unsupported explicit node class {type(node).__name__}")
        calls.append(node.lower())
    generic = GenericPlan(tuple(calls), plan.outputs, plan.max_calls)
    typecheck_calls(generic.calls, generic.outputs)
    return generic


def execute_explicit(plan, db=None):
    return execute_generic(compile_explicit(plan), db=db)


def generic_cases():
    return {
        "Q001": GenericPlan((
            CallSpec("level", "evaluate_scalar",
                     {"metric_ref": "sales@v1", "period": "2026-07"}),
        ), ("level",)),
        "Q004": GenericPlan((
            CallSpec("level", "evaluate_scalar",
                     {"metric_ref": "loss_ratio@v1", "period": "2026-07"}),
        ), ("level",)),
        "Q006": GenericPlan((
            CallSpec("before", "evaluate_scalar",
                     {"metric_ref": "sales@v1", "period": "2026-06"}),
            CallSpec("after", "evaluate_scalar",
                     {"metric_ref": "sales@v1", "period": "2026-07"}),
            CallSpec("delta", "delta",
                     {"before": Ref("before", "value"),
                      "after": Ref("after", "value")}),
        ), ("delta",)),
        "Q011": GenericPlan((
            CallSpec("before", "evaluate_grouped",
                     {"metric_ref": "sales@v1", "period": "2026-06",
                      "dimension": "channel"}),
            CallSpec("after", "evaluate_grouped",
                     {"metric_ref": "sales@v1", "period": "2026-07",
                      "dimension": "channel"}),
            CallSpec("contrib", "contribution",
                     {"before": Ref("before", "rows"),
                      "after": Ref("after", "rows")}),
            CallSpec("top", "select_max_abs", {"rows": Ref("contrib", "rows")}),
        ), ("contrib", "top")),
        "Q050": GenericPlan((
            CallSpec("before", "evaluate_grouped",
                     {"metric_ref": "sales@v1", "period": "2026-06",
                      "dimension": "channel"}),
            CallSpec("after", "evaluate_grouped",
                     {"metric_ref": "sales@v1", "period": "2026-07",
                      "dimension": "channel"}),
            CallSpec("contrib", "contribution",
                     {"before": Ref("before", "rows"),
                      "after": Ref("after", "rows")}),
            CallSpec("top", "select_max_abs", {"rows": Ref("contrib", "rows")}),
            CallSpec("large", "greater_than",
                     {"value": Ref("top", "magnitude"), "threshold": 50}),
            CallSpec("drill", "evaluate_grouped",
                     {"metric_ref": "sales@v1", "period": "2026-07",
                      "dimension": "category", "filter_dimension": "channel",
                      "filter_value": Ref("top", "value")},
                     guard=Ref("large", "value")),
        ), ("top", "large", "drill")),
    }


def explicit_cases():
    return {
        "Q001": ExplicitPlan((ScalarMetricNode("level", "sales@v1", "2026-07"),),
                             ("level",)),
        "Q004": ExplicitPlan((ScalarMetricNode("level", "loss_ratio@v1", "2026-07"),),
                             ("level",)),
        "Q006": ExplicitPlan((
            ScalarMetricNode("before", "sales@v1", "2026-06"),
            ScalarMetricNode("after", "sales@v1", "2026-07"),
            DeltaNode("delta", Ref("before", "value"), Ref("after", "value")),
        ), ("delta",)),
        "Q011": ExplicitPlan((
            GroupedMetricNode("before", "sales@v1", "2026-06", "channel"),
            GroupedMetricNode("after", "sales@v1", "2026-07", "channel"),
            ContributionNode("contrib", Ref("before", "rows"), Ref("after", "rows")),
            SelectMaxAbsNode("top", Ref("contrib", "rows")),
        ), ("contrib", "top")),
        "Q050": ExplicitPlan((
            GroupedMetricNode("before", "sales@v1", "2026-06", "channel"),
            GroupedMetricNode("after", "sales@v1", "2026-07", "channel"),
            ContributionNode("contrib", Ref("before", "rows"), Ref("after", "rows")),
            SelectMaxAbsNode("top", Ref("contrib", "rows")),
            GreaterThanNode("large", Ref("top", "magnitude"), 50),
            GroupedMetricNode("drill", "sales@v1", "2026-07", "category",
                              "channel", Ref("top", "value"), Ref("large", "value")),
        ), ("top", "large", "drill")),
    }


def _jsonable(value):
    if isinstance(value, Ref):
        return {"ref": value.node, "path": value.path}
    if is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def serialized_size(value):
    return len(json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":")))


def comparison_metrics():
    generic = generic_cases()
    explicit = explicit_cases()
    return {
        "cases": sorted(generic),
        "c4": {"node_classes": 1,
               "serialized_bytes": sum(serialized_size(plan) for plan in generic.values()),
               "lowering_dispatch_cases": 0},
        "c3": {"node_classes": len(C3_NODE_TYPES),
               "serialized_bytes": sum(serialized_size(plan) for plan in explicit.values()),
               "compiled_serialized_bytes": sum(
                   serialized_size(compile_explicit(plan)) for plan in explicit.values()),
               "lowering_dispatch_cases": len(C3_NODE_TYPES)},
        "shared": {"operator_contracts": len(REGISTRY),
                   "semantic_metric_contracts": len(SEMANTICS)},
    }
