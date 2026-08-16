"""Executable operator contracts for Analytical Plan v1 shadow validation."""
from dataclasses import dataclass
from datetime import date
from numbers import Number
import re
from typing import Mapping, Tuple

from analytical_ir import Ref, Slice


@dataclass(frozen=True)
class OperatorPort:
    name: str
    value_type: str
    required: bool = True


@dataclass(frozen=True)
class OperatorContract:
    operator_ref: str
    inputs: Tuple[OperatorPort, ...]
    outputs: Mapping[str, str]
    validators: Tuple[str, ...] = ()


class ShadowOperatorRegistry:
    """Closed registry that validates ports, Ref edges, and named laws."""

    def __init__(self, contracts=None):
        self._contracts = {}
        self._validators = {
            "same_metric_inputs": self._same_metric_inputs,
            "distinct_periods": self._distinct_periods,
        }
        for contract in contracts or default_contracts():
            self.register(contract)

    def register(self, contract):
        if contract.operator_ref in self._contracts:
            raise ValueError(f"duplicate operator contract: {contract.operator_ref}")
        if not re.fullmatch(r"[^@]+@v[1-9][0-9]*", contract.operator_ref):
            raise ValueError(f"invalid operator_ref: {contract.operator_ref}")
        port_names = [port.name for port in contract.inputs]
        if len(port_names) != len(set(port_names)):
            raise ValueError(f"duplicate input ports: {contract.operator_ref}")
        if "" not in contract.outputs:
            raise ValueError(f"root output type missing: {contract.operator_ref}")
        missing = set(contract.validators) - set(self._validators)
        if missing:
            raise ValueError(f"unknown named validators: {sorted(missing)}")
        self._contracts[contract.operator_ref] = contract

    @property
    def operator_refs(self):
        """Return the closed operator vocabulary exposed to shadow compilers."""
        return frozenset(self._contracts)

    def validate_plan(self, plan, semantic_metrics):
        problems = []
        output_types = {}
        calls_by_id = {}

        if plan.plan_version != "1":
            problems.append("unsupported plan_version")
        if not plan.calls:
            problems.append("plan must contain at least one call")
        for name, value in plan.limits.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                problems.append(f"invalid plan limit {name}: {value}")
        for entry in plan.binding_ledger:
            if entry.state == "unconsumed":
                problems.append(f"unconsumed binding clause: {entry.clause}")

        for call in plan.calls:
            if call.call_id in calls_by_id:
                problems.append(f"duplicate call_id: {call.call_id}")
                continue
            contract = self._contracts.get(call.operator_ref)
            if contract is None:
                problems.append(f"unregistered operator: {call.operator_ref}")
                calls_by_id[call.call_id] = call
                continue

            if call.guard is not None:
                guard_type = output_types.get(
                    (call.guard.call_id, call.guard.path), "UnknownRef")
                if guard_type != "Boolean":
                    problems.append(
                        f"{call.call_id}.guard: {guard_type} != Boolean")

            ports = {port.name: port for port in contract.inputs}
            unknown = set(call.inputs) - set(ports)
            if unknown:
                problems.append(f"{call.call_id} unknown inputs: {sorted(unknown)}")
            for port in contract.inputs:
                if port.required and port.name not in call.inputs:
                    problems.append(f"{call.call_id} missing input: {port.name}")
                elif port.name in call.inputs:
                    if isinstance(call.inputs[port.name], Slice):
                        problems.extend(
                            f"{call.call_id}.{port.name}: {detail}"
                            for detail in self._slice_problems(call.inputs[port.name]))
                    actual = self._input_type(
                        call.inputs[port.name], output_types, semantic_metrics)
                    if not self._type_matches(actual, port.value_type):
                        problems.append(
                            f"{call.call_id}.{port.name}: {actual} != {port.value_type}")

            for validator_name in contract.validators:
                detail = self._validators[validator_name](call, calls_by_id)
                if detail:
                    problems.append(f"{call.call_id} {validator_name}: {detail}")

            calls_by_id[call.call_id] = call
            for path, value_type in contract.outputs.items():
                output_types[(call.call_id, path)] = value_type

        for output in plan.outputs:
            if (output.call_id, output.path) not in output_types:
                problems.append(
                    f"unknown plan output: {output.call_id}.{output.path}")

        if problems:
            return {"status": "out_of_domain", "violated": [
                {"check": "analytical_plan_valid", "passed": False,
                 "detail": detail} for detail in problems
            ]}
        return {"status": "result", "check": "analytical_plan_valid",
                "passed": True}

    @staticmethod
    def _input_type(value, output_types, semantic_metrics):
        if isinstance(value, Ref):
            return output_types.get((value.call_id, value.path), "UnknownRef")
        if isinstance(value, Slice):
            return "Slice"
        if isinstance(value, Number) and not isinstance(value, bool):
            return "Number"
        if isinstance(value, (tuple, list)):
            if value and all(isinstance(item, Ref) for item in value):
                if any((item.call_id, item.path) not in output_types for item in value):
                    return "UnknownRefList"
                return "RefList"
            if all(isinstance(item, str) for item in value):
                return "StringList"
        if isinstance(value, str) and value in semantic_metrics:
            return "MetricRef"
        if isinstance(value, str) and re.fullmatch(r"[^@]+@v[1-9][0-9]*", value):
            return "UnknownMetricRef"
        if isinstance(value, str):
            return "String"
        return type(value).__name__

    @staticmethod
    def _type_matches(actual, expected):
        return actual in expected.split("|")

    @staticmethod
    def _slice_problems(metric_slice):
        problems = []
        if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", metric_slice.period):
            problems.append(f"invalid month: {metric_slice.period}")
        try:
            date.fromisoformat(metric_slice.as_of)
        except (TypeError, ValueError):
            problems.append(f"invalid as_of: {metric_slice.as_of}")
        dimensions = set()
        for dimension, values in metric_slice.predicates:
            if not dimension or dimension in dimensions:
                problems.append(f"duplicate or empty predicate: {dimension}")
            dimensions.add(dimension)
            if not values or any(not isinstance(value, str) or not value
                                 for value in values):
                problems.append(f"invalid predicate values: {dimension}")
        return problems

    @staticmethod
    def _same_metric_inputs(call, calls_by_id):
        refs = [call.inputs.get("before"), call.inputs.get("after")]
        producers = [calls_by_id.get(ref.call_id) if isinstance(ref, Ref) else None
                     for ref in refs]
        if None in producers:
            return "before and after must reference prior calls"
        metrics = [producer.inputs.get("metric") for producer in producers]
        if metrics[0] != metrics[1]:
            return f"metric mismatch: {metrics[0]} != {metrics[1]}"
        return None

    @staticmethod
    def _distinct_periods(call, calls_by_id):
        refs = [call.inputs.get("before"), call.inputs.get("after")]
        producers = [calls_by_id.get(ref.call_id) if isinstance(ref, Ref) else None
                     for ref in refs]
        if None in producers:
            return "before and after must reference prior calls"
        slices = [producer.inputs.get("slice") for producer in producers]
        if not all(isinstance(value, Slice) for value in slices):
            return "both producers must carry a Slice"
        if slices[0].period == slices[1].period:
            return f"comparison periods are identical: {slices[0].period}"
        return None


def default_contracts():
    return (
        OperatorContract(
            operator_ref="evaluate_metric@v1",
            inputs=(OperatorPort("metric", "MetricRef"),
                    OperatorPort("slice", "Slice"),
                    OperatorPort("reducer", "String", required=False),
                    OperatorPort("group_by", "StringList", required=False)),
            outputs={"": "MetricEvaluation", "value": "Number"},
        ),
        OperatorContract(
            operator_ref="delta@v1",
            inputs=(OperatorPort("before", "Number"),
                    OperatorPort("after", "Number")),
            outputs={"": "Delta", "value": "Number"},
            validators=("same_metric_inputs", "distinct_periods"),
        ),
        OperatorContract(
            operator_ref="contribution@v1",
            inputs=(OperatorPort("before", "MetricEvaluation"),
                    OperatorPort("after", "MetricEvaluation")),
            outputs={"": "Attribution"},
            validators=("same_metric_inputs", "distinct_periods"),
        ),
        OperatorContract(
            operator_ref="set_transition@v1",
            inputs=(OperatorPort("before", "MetricEvaluation"),
                    OperatorPort("after", "MetricEvaluation")),
            outputs={"": "Attribution"},
            validators=("same_metric_inputs", "distinct_periods"),
        ),
        OperatorContract(
            operator_ref="rank@v1",
            inputs=(OperatorPort("input", "Attribution"),
                    OperatorPort("measure", "String"),
                    OperatorPort("order", "String"),
                    OperatorPort("limit", "Number")),
            outputs={"": "RankedSelection"},
        ),
        OperatorContract(
            operator_ref="align_metrics@v1",
            inputs=(OperatorPort("metrics", "RefList"),),
            outputs={"": "MetricAlignment"},
        ),
        OperatorContract(
            operator_ref="drilldown@v1",
            inputs=(OperatorPort("selection", "Attribution|RankedSelection"),
                    OperatorPort("group_by", "String")),
            outputs={"": "Attribution"},
        ),
        OperatorContract(
            operator_ref="plan_gap@v1",
            inputs=(OperatorPort("metric", "MetricRef"),
                    OperatorPort("slice", "Slice"),
                    OperatorPort("vintage_id", "String")),
            outputs={"": "Attribution"},
        ),
    )
