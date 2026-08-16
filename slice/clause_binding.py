"""Closed source-clause binding contract for the E-016 shadow compiler.

The natural-language adapter may propose bindings, but this module is the
deterministic authority for their wire shape, source fidelity, role/value types,
and links to concrete Analytical Plan consumers.
"""
from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Mapping, Tuple


VALID_STATES = frozenset({
    "consumed", "preserved", "ambiguous", "unsupported", "non_semantic",
})
SUCCESS_STATES = frozenset({"consumed", "preserved", "non_semantic"})
ROLE_VALUE_KINDS = {
    "subject": "metric_ref",
    "reducer": "reducer_ref",
    "time.target": "month",
    "time.baseline": "month",
    "filter": "predicate",
    "breakdown": "dimension_ref",
    "analysis": "analysis_ref",
    "ranking": "ranking",
    "nested_breakdown": "dimension_ref",
    "scenario": "scenario_ref",
    "output": "output_ref",
}
REDUCER_REFS = frozenset({"sum", "ratio_of_sums", "distinct", "time_last",
                          "time_average"})
ANALYSIS_REFS = frozenset({"level", "delta", "contribution", "divergence",
                           "plan"})
OUTPUT_REFS = frozenset({"result", "only_ranked", "selected_segment_scope",
                         "target_level"})
RANK_MEASURES = frozenset({"value", "contribution"})


@dataclass(frozen=True)
class BindingValue:
    """Closed tagged union payload. The clause role fixes the allowed tag."""

    kind: str
    value: Any

    def to_dict(self):
        return {"kind": self.kind, "value": _wire(self.value)}


@dataclass(frozen=True)
class ClauseBinding:
    clause_id: str
    source_text: str
    start: int
    end: int
    material: bool
    state: str
    role: str | None = None
    value: BindingValue | None = None
    target_refs: Tuple[str, ...] = ()
    reason: str | None = None

    def to_dict(self):
        result = {
            "clause_id": self.clause_id,
            "source": {
                "text": self.source_text,
                "span": [self.start, self.end],
                "material": self.material,
            },
            "binding": {
                "state": self.state,
                "role": self.role,
                "value": None if self.value is None else self.value.to_dict(),
                "target_refs": list(self.target_refs),
            },
        }
        if self.reason is not None:
            result["binding"]["reason"] = self.reason
        return result


@dataclass(frozen=True)
class SourceClauseBindingRecord:
    """One versioned audit record beside a canonical C4 Plan."""

    question: str
    clauses: Tuple[ClauseBinding, ...]
    defaults: Mapping[str, Any] = field(default_factory=dict)
    record_version: str = "1"

    def to_dict(self):
        return {
            "record_version": self.record_version,
            "question": self.question,
            "clauses": [clause.to_dict() for clause in sorted(
                self.clauses, key=lambda row: (row.start, row.end, row.clause_id))],
            "defaults": _wire(dict(self.defaults)),
        }

    def canonical_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)

    def binding_hash(self):
        digest = hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
        return f"sha256:{digest}"


def validate_binding_record(record, vocabulary, allowed_targets=None,
                            require_targets=False):
    """Return deterministic contract violations for one proposed/final record."""
    problems = []
    if record.record_version != "1":
        problems.append("unsupported record_version")
    if not isinstance(record.question, str) or not record.question.strip():
        problems.append("question must be a non-empty string")
    ids = [clause.clause_id for clause in record.clauses]
    if len(ids) != len(set(ids)):
        problems.append("duplicate clause_id")

    singleton_roles = {
        "reducer", "time.target", "time.baseline", "analysis", "ranking",
        "nested_breakdown", "scenario",
    }
    for role in singleton_roles:
        rows = [row.clause_id for row in record.clauses
                if row.state in {"consumed", "preserved"} and row.role == role]
        if len(rows) > 1:
            problems.append(
                f"{role}: multiple bindings require registered composition: {rows}")

    for clause in record.clauses:
        prefix = clause.clause_id
        if not prefix:
            problems.append("empty clause_id")
        if clause.state not in VALID_STATES:
            problems.append(f"{prefix}: unknown state {clause.state}")
        if not (0 <= clause.start < clause.end <= len(record.question)):
            problems.append(f"{prefix}: invalid source span")
        elif record.question[clause.start:clause.end] != clause.source_text:
            problems.append(f"{prefix}: source span/text mismatch")
        if clause.material and clause.state == "non_semantic":
            problems.append(f"{prefix}: material clause cannot be non_semantic")
        if not clause.material and clause.state != "non_semantic":
            problems.append(f"{prefix}: non-material clause must be non_semantic")

        resolved = clause.state in {"consumed", "preserved"}
        if resolved:
            expected_kind = ROLE_VALUE_KINDS.get(clause.role)
            if expected_kind is None:
                problems.append(f"{prefix}: unknown bound role {clause.role}")
            elif clause.value is None or clause.value.kind != expected_kind:
                got = None if clause.value is None else clause.value.kind
                problems.append(
                    f"{prefix}: {clause.role} requires {expected_kind}, got {got}")
            if require_targets and not clause.target_refs:
                problems.append(f"{prefix}: resolved clause has no Plan consumer")
        elif clause.value is not None:
            problems.append(f"{prefix}: unresolved clause cannot carry a bound value")

        if clause.state in {"ambiguous", "unsupported", "non_semantic"}:
            if not clause.reason:
                problems.append(f"{prefix}: {clause.state} requires reason")
        elif clause.reason is not None:
            problems.append(f"{prefix}: resolved clause cannot carry a failure reason")
        if clause.state in {"ambiguous", "unsupported", "non_semantic"} \
                and clause.target_refs:
            problems.append(f"{prefix}: unresolved/non-semantic clause has Plan targets")
        if allowed_targets is not None:
            unknown = sorted(set(clause.target_refs) - set(allowed_targets))
            if unknown:
                problems.append(f"{prefix}: unknown Plan targets {unknown}")
        problems.extend(_value_problems(clause, vocabulary))

    unresolved = any(row.material and row.state in {"ambiguous", "unsupported"}
                     for row in record.clauses)
    if not unresolved and not any(
            row.state in {"consumed", "preserved"} and row.role == "subject"
            for row in record.clauses):
        problems.append("successful binding requires at least one subject")
    return problems


def _value_problems(clause, vocabulary):
    if clause.state not in {"consumed", "preserved"} or clause.value is None:
        return []
    value = clause.value.value
    prefix = clause.clause_id
    if clause.role == "subject":
        if value not in vocabulary["metric_refs"]:
            return [f"{prefix}: unregistered metric ref {value}"]
    elif clause.role in {"breakdown", "nested_breakdown"}:
        if value not in vocabulary["dimension_refs"]:
            return [f"{prefix}: unregistered dimension ref {value}"]
    elif clause.role == "reducer":
        if value not in REDUCER_REFS:
            return [f"{prefix}: unregistered reducer ref {value}"]
    elif clause.role in {"time.target", "time.baseline"}:
        if not isinstance(value, str) or not re.fullmatch(
                r"[0-9]{4}-(0[1-9]|1[0-2])", value):
            return [f"{prefix}: invalid month {value}"]
    elif clause.role == "filter":
        if not isinstance(value, Mapping):
            return [f"{prefix}: predicate must be an object"]
        dimension = value.get("dimension_ref")
        values = value.get("values")
        if (dimension not in vocabulary["dimension_refs"]
                or not isinstance(values, (tuple, list)) or not values
                or any(not isinstance(item, str) or not item for item in values)):
            return [f"{prefix}: invalid predicate"]
        allowed = vocabulary["dimension_values"].get(dimension)
        if allowed is not None and not set(values).issubset(allowed):
            return [f"{prefix}: unregistered predicate value"]
    elif clause.role == "analysis":
        if value not in ANALYSIS_REFS:
            return [f"{prefix}: unregistered analysis ref {value}"]
    elif clause.role == "scenario":
        if not isinstance(value, str) or not re.fullmatch(
                r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value):
            return [f"{prefix}: invalid scenario ref {value}"]
    elif clause.role == "ranking":
        if (not isinstance(value, Mapping)
                or value.get("measure") not in RANK_MEASURES
                or value.get("order") not in {"ascending", "descending"}
                or not isinstance(value.get("limit"), int)
                or isinstance(value.get("limit"), bool)
                or value["limit"] <= 0):
            return [f"{prefix}: invalid ranking"]
    elif clause.role == "output" and value not in OUTPUT_REFS:
        return [f"{prefix}: unregistered output ref {value}"]
    return []


def _wire(value):
    if isinstance(value, Mapping):
        return {key: _wire(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_wire(item) for item in value]
    if isinstance(value, list):
        return [_wire(item) for item in value]
    return value
