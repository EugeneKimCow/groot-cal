"""Canonical Analytical Plan v1 value objects.

This module is deliberately independent from the current engine and pipelines.  It
defines the wire contract used by the shadow planner; importing it has no effect on
the production execution route.
"""
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Dict, Mapping, Optional, Tuple


@dataclass(frozen=True)
class Ref:
    """Reference to a prior Call output."""

    call_id: str
    path: str = ""

    def to_dict(self):
        return {"$ref": self.call_id, "path": self.path}


@dataclass(frozen=True)
class Slice:
    """A governed metric slice over a registered time window.

    ``window``는 등록된 calendar 종류다(기본 month, E-023부터 iso_week).
    Predicates are stored as sorted ``(dimension, values)`` tuples so equivalent
    scopes have a deterministic serialization and hash.
    """

    period: str
    as_of: str
    predicates: Tuple[Tuple[str, Tuple[str, ...]], ...] = ()
    window: str = "month"

    @classmethod
    def from_scope(cls, period, as_of, scope, window="month"):
        predicates = []
        for dimension, raw_values in sorted(scope.items()):
            values = raw_values if isinstance(raw_values, list) else [raw_values]
            predicates.append((dimension, tuple(sorted(values))))
        return cls(period=period, as_of=as_of, predicates=tuple(predicates),
                   window=window)

    def to_dict(self):
        return {
            "time_window": {"kind": self.window, "period": self.period},
            "as_of": self.as_of,
            "predicates": {key: list(values) for key, values in self.predicates},
        }


@dataclass(frozen=True)
class BindingLedgerEntry:
    """Records whether an interpreted clause is executable or merely retained."""

    clause: str
    state: str
    value: Any
    consumers: Tuple[str, ...] = ()
    note: Optional[str] = None

    def __post_init__(self):
        if self.state not in {"consumed", "preserved", "unconsumed"}:
            raise ValueError(f"unknown binding state: {self.state}")

    def to_dict(self):
        result = {
            "clause": self.clause,
            "state": self.state,
            "value": _wire_value(self.value),
            "consumers": list(self.consumers),
        }
        if self.note is not None:
            result["note"] = self.note
        return result


@dataclass(frozen=True)
class Call:
    """One registered, typed operator invocation."""

    call_id: str
    operator_ref: str
    inputs: Mapping[str, Any]
    guard: Optional[Ref] = None

    def to_dict(self):
        result = {
            "call_id": self.call_id,
            "operator_ref": self.operator_ref,
            "inputs": {key: _wire_value(value)
                       for key, value in sorted(self.inputs.items())},
        }
        if self.guard is not None:
            result["guard"] = self.guard.to_dict()
        return result


@dataclass(frozen=True)
class Plan:
    """Canonical generic Call+Ref analytical plan."""

    calls: Tuple[Call, ...]
    outputs: Tuple[Ref, ...]
    binding_ledger: Tuple[BindingLedgerEntry, ...]
    limits: Mapping[str, int] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    plan_version: str = "1"

    def to_dict(self):
        return {
            "plan_version": self.plan_version,
            "calls": [call.to_dict() for call in self.calls],
            "outputs": [output.to_dict() for output in self.outputs],
            "limits": dict(sorted(self.limits.items())),
            "binding_ledger": [entry.to_dict() for entry in self.binding_ledger],
            "metadata": _wire_value(dict(self.metadata)),
        }

    def canonical_json(self):
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False)

    def plan_hash(self):
        digest = hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
        return f"sha256:{digest}"


@dataclass(frozen=True)
class ResultEnvelope:
    """Normalized tagged union for one analytical operator result.

    Current operator payloads are intentionally not adapted in Increment 1.  This
    contract is the migration target and prevents a successful payload from being
    confused with refusal, missing input, or exhausted exploration budget.
    """

    status: str
    result_type: str
    value: Any = None
    operator_ref: Optional[str] = None
    provenance_ref: Optional[str] = None
    label_ceiling: Optional[str] = None
    violated: Tuple[Mapping[str, Any], ...] = ()
    missing_inputs: Tuple[str, ...] = ()
    pass_conditions: Optional[str] = None
    envelope_version: str = "1"

    def __post_init__(self):
        if self.envelope_version != "1":
            raise ValueError(f"unsupported envelope_version: {self.envelope_version}")
        valid = {"result", "out_of_domain", "suspended", "budget_exhausted"}
        if self.status not in valid:
            raise ValueError(f"unknown result status: {self.status}")
        if not self.result_type:
            raise ValueError("result_type is required")
        if self.status == "result":
            if self.value is None or not self.operator_ref or not self.provenance_ref:
                raise ValueError(
                    "result requires value, operator_ref, and provenance_ref")
            if self.violated or self.missing_inputs or self.pass_conditions:
                raise ValueError("result cannot carry failure fields")
        elif self.status in {"out_of_domain", "budget_exhausted"}:
            if not self.violated:
                raise ValueError(f"{self.status} requires violated checks")
            if (self.value is not None or self.missing_inputs or self.pass_conditions
                    or self.operator_ref or self.provenance_ref or self.label_ceiling):
                raise ValueError(f"{self.status} cannot carry other union fields")
        elif self.status == "suspended":
            if not self.missing_inputs or not self.pass_conditions:
                raise ValueError(
                    "suspended requires missing_inputs and pass_conditions")
            if (self.value is not None or self.violated or self.operator_ref
                    or self.provenance_ref or self.label_ceiling):
                raise ValueError("suspended cannot carry other union fields")

    def to_dict(self):
        result = {
            "envelope_version": self.envelope_version,
            "status": self.status,
            "result_type": self.result_type,
        }
        if self.status == "result":
            result["value"] = _wire_value(self.value)
            result["evidence"] = {
                "operator_ref": self.operator_ref,
                "provenance_ref": self.provenance_ref,
            }
            if self.label_ceiling is not None:
                result["evidence"]["label_ceiling"] = self.label_ceiling
        elif self.status in {"out_of_domain", "budget_exhausted"}:
            result["violated"] = [_wire_value(item) for item in self.violated]
        else:
            result["missing_inputs"] = list(self.missing_inputs)
            result["pass_conditions"] = self.pass_conditions
        return result


def _wire_value(value):
    if isinstance(value, (Ref, Slice, BindingLedgerEntry, Call, Plan,
                          ResultEnvelope)):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {key: _wire_value(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_wire_value(item) for item in value]
    if isinstance(value, list):
        return [_wire_value(item) for item in value]
    return value
