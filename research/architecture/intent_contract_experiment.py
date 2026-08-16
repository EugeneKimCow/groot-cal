"""E-015 discriminator for two intent-to-C4 contract shapes.

This is an isolated architecture experiment.  It starts after a source-clause
inventory has been proposed and does not parse natural language or affect the
production engine.  Both candidates share the same closed, versioned binding
record and the same C4 Plan emitter so the only tested variable is whether a
second Bound Intent Spec earns its additional contract surface.
"""
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
import sys


SLICE_DIR = Path(__file__).resolve().parents[2] / "slice"
if str(SLICE_DIR) not in sys.path:
    sys.path.insert(0, str(SLICE_DIR))

from analytical_ir import Call, Plan, Ref, Slice  # noqa: E402


VALID_STATES = {
    "consumed", "preserved", "ambiguous", "unsupported", "non_semantic",
}
SUCCESS_STATES = {"consumed", "preserved", "non_semantic"}
ROLE_TARGETS = {
    "subject": "call.evaluate.metric",
    "reducer": "call.evaluate.reducer",
    "time.target": "call.evaluate.slice",
    "time.baseline": "call.evaluate.slice",
    "filter": "call.evaluate.slice.predicates",
    "breakdown": "call.evaluate.group_by",
    "analysis": "call.operator",
    "ranking": "call.rank",
    "nested_breakdown": "call.drilldown.group_by",
    "output": "plan.outputs",
}
SEMANTIC_REFS = {
    "commerce.net_sales@v1",
    "finance.operating_profit@v1",
    "scm.inventory_balance@v1",
}
DIMENSION_REFS = {"channel", "region", "product_category", "customer_type"}
DIMENSION_VALUES = {"channel": {"온라인", "오프라인"}}
REDUCERS = {"sum", "time_average", "time_last"}
ANALYSES = {"level", "delta", "contribution", "divergence"}
OUTPUTS = {"result", "only_ranked", "selected_segment_scope"}
RANK_MEASURES = {"value", "contribution"}
REGISTERED_OPERATORS = {
    "evaluate_metric@v1", "delta@v1", "contribution@v1", "rank@v1",
    "align_metrics@v1", "drilldown@v1",
}


@dataclass(frozen=True)
class ClauseBindingRecord:
    """One source clause and its deterministic binding outcome."""

    clause_id: str
    source_text: str
    start: int
    end: int
    material: bool
    state: str
    role: str | None = None
    value: object = None
    target_refs: tuple = ()
    reason: str | None = None
    record_version: str = "1"

    def to_dict(self):
        result = {
            "record_version": self.record_version,
            "clause_id": self.clause_id,
            "source": {
                "text": self.source_text,
                "span": [self.start, self.end],
                "material": self.material,
            },
            "binding": {
                "state": self.state,
                "role": self.role,
                "value": _wire(self.value),
                "target_refs": list(self.target_refs),
            },
        }
        if self.reason is not None:
            result["binding"]["reason"] = self.reason
        return result


@dataclass(frozen=True)
class BoundIntentSpec:
    """Candidate A: a second non-executable representation before C4."""

    subjects: tuple
    reducer: str | None
    target_period: str
    baseline_period: str | None
    filters: tuple
    breakdowns: tuple
    analyses: tuple
    ranking: object
    nested_breakdown: str | None
    outputs: tuple
    binding_hash: str
    intent_version: str = "1"

    def to_dict(self):
        return {
            "intent_version": self.intent_version,
            "subjects": list(self.subjects),
            "reducer": self.reducer,
            "temporal": {
                "target_period": self.target_period,
                "baseline_period": self.baseline_period,
            },
            "filters": [_wire(value) for value in self.filters],
            "breakdowns": list(self.breakdowns),
            "analyses": list(self.analyses),
            "ranking": _wire(self.ranking),
            "nested_breakdown": self.nested_breakdown,
            "outputs": list(self.outputs),
            "binding_hash": self.binding_hash,
        }

    def canonical_json(self):
        return _canonical_json(self.to_dict())


@dataclass(frozen=True)
class IntentCase:
    case_id: str
    question: str
    records: tuple
    defaults: tuple = ()

    def default_map(self):
        return dict(self.defaults)


def compile_bound_intent(case):
    """Candidate A: records -> Bound Intent Spec -> C4 Plan."""
    preflight = _preflight(case)
    if preflight is not None:
        return preflight
    projection = _project(case)
    spec = BoundIntentSpec(
        subjects=projection["subjects"],
        reducer=projection["reducer"],
        target_period=projection["target_period"],
        baseline_period=projection["baseline_period"],
        filters=projection["filters"],
        breakdowns=projection["breakdowns"],
        analyses=projection["analyses"],
        ranking=projection["ranking"],
        nested_breakdown=projection["nested_breakdown"],
        outputs=projection["outputs"],
        binding_hash=binding_hash(case.records),
    )
    consistency = _bound_intent_problems(spec, projection)
    if consistency:
        return _failure("out_of_domain", "bound_intent_consistent", consistency,
                        case.records)
    return _success(_emit_plan(case, projection), case.records, spec)


def compile_direct_plan(case):
    """Candidate B: records -> C4 Plan, with no serialized intermediate IR."""
    preflight = _preflight(case)
    if preflight is not None:
        return preflight
    return _success(_emit_plan(case, _project(case)), case.records, None)


def compile_existing_bound_spec(case, spec):
    """Expose Candidate A's additional consistency surface for red-team tests."""
    preflight = _preflight(case)
    if preflight is not None:
        return preflight
    projection = _project(case)
    problems = _bound_intent_problems(spec, projection)
    if problems:
        return _failure("out_of_domain", "bound_intent_consistent", problems,
                        case.records)
    return _success(_emit_plan(case, projection), case.records, spec)


def comparison_metrics(cases=None):
    cases = cases or intent_cases()
    plan_parity = 0
    refusal_parity = 0
    bound_bytes = 0
    duplicated_values = 0
    successful = 0
    for case in cases.values():
        bound = compile_bound_intent(case)
        direct = compile_direct_plan(case)
        if bound["status"] != direct["status"]:
            continue
        if bound["status"] == "result":
            successful += 1
            if (bound["plan"].canonical_json()
                    == direct["plan"].canonical_json()):
                plan_parity += 1
            bound_bytes += len(bound["bound_intent"].canonical_json().encode())
            duplicated_values += sum(
                record.state in {"consumed", "preserved"}
                for record in case.records)
        elif bound["violated"] == direct["violated"]:
            refusal_parity += 1
    return {
        "cases": len(cases),
        "successful_cases": successful,
        "plan_byte_parity": plan_parity,
        "refusal_parity": refusal_parity,
        "shared_record_types": 1,
        "candidate_a": {
            "additional_serialized_contracts": 1,
            "additional_intermediate_bytes": bound_bytes,
            "duplicated_bound_values": duplicated_values,
            "additional_consistency_checks": 1,
            "source_to_plan_hops": 3,
        },
        "candidate_b": {
            "additional_serialized_contracts": 0,
            "additional_intermediate_bytes": 0,
            "duplicated_bound_values": 0,
            "additional_consistency_checks": 0,
            "source_to_plan_hops": 2,
        },
    }


def select_contract(cases=None):
    """Apply the documented E-015 equal-fidelity/minimality decision rule."""
    metrics = comparison_metrics(cases)
    fidelity_equal = (
        metrics["plan_byte_parity"] == metrics["successful_cases"]
        and metrics["plan_byte_parity"] + metrics["refusal_parity"]
        == metrics["cases"]
    )
    if not fidelity_equal:
        return {"selected": None, "reason": "fidelity parity not established",
                "metrics": metrics}
    if (metrics["candidate_b"]["additional_serialized_contracts"]
            < metrics["candidate_a"]["additional_serialized_contracts"]):
        return {
            "selected": "direct_plan_plus_binding_record",
            "rejected": "bound_intent_spec",
            "reason": (
                "equal Plan/refusal fidelity with no duplicated serialized "
                "intent contract or cross-representation consistency state"),
            "metrics": metrics,
        }
    return {"selected": None, "reason": "no minimality discriminator",
            "metrics": metrics}


def binding_hash(records):
    raw = _canonical_json([record.to_dict() for record in
                           sorted(records, key=lambda item: item.clause_id)])
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def _preflight(case):
    problems = _record_problems(case)
    if problems:
        return _failure("out_of_domain", "clause_binding_valid", problems,
                        case.records)
    ambiguous = [record for record in case.records
                 if record.material and record.state == "ambiguous"]
    if ambiguous:
        return _failure("clarify", "material_clause_ambiguous",
                        [f"{row.clause_id}: {row.reason}" for row in ambiguous],
                        case.records)
    unsupported = [record for record in case.records
                   if record.material and record.state == "unsupported"]
    if unsupported:
        return _failure("out_of_domain", "material_clause_supported",
                        [f"{row.clause_id}: {row.reason}" for row in unsupported],
                        case.records)
    unaccounted = [record.clause_id for record in case.records
                   if record.material and record.state not in SUCCESS_STATES]
    if unaccounted:
        return _failure("out_of_domain", "material_clause_accounted",
                        unaccounted, case.records)
    return None


def _record_problems(case):
    problems = []
    ids = [record.clause_id for record in case.records]
    if len(ids) != len(set(ids)):
        problems.append("duplicate clause_id")
    singleton_roles = {
        "reducer", "time.target", "time.baseline", "analysis", "ranking",
        "nested_breakdown",
    }
    for role in singleton_roles:
        bound = [record.clause_id for record in case.records
                 if record.state in {"consumed", "preserved"}
                 and record.role == role]
        if len(bound) > 1:
            problems.append(
                f"{role}: multiple bindings require explicit composition: {bound}")
    for record in case.records:
        prefix = record.clause_id
        if record.record_version != "1":
            problems.append(f"{prefix}: unsupported record_version")
        if record.state not in VALID_STATES:
            problems.append(f"{prefix}: unknown state {record.state}")
        if not (0 <= record.start < record.end <= len(case.question)):
            problems.append(f"{prefix}: invalid source span")
        elif case.question[record.start:record.end] != record.source_text:
            problems.append(f"{prefix}: source span/text mismatch")
        if record.material and record.state == "non_semantic":
            problems.append(f"{prefix}: material clause cannot be non_semantic")
        if record.state in {"consumed", "preserved"}:
            expected_target = ROLE_TARGETS.get(record.role)
            if expected_target is None:
                problems.append(f"{prefix}: unknown bound role {record.role}")
            elif expected_target not in record.target_refs:
                problems.append(f"{prefix}: role is not linked to {expected_target}")
        if record.state in {"ambiguous", "unsupported", "non_semantic"}:
            if not record.reason:
                problems.append(f"{prefix}: {record.state} requires reason")
        if record.state in {"ambiguous", "unsupported"} and record.target_refs:
            problems.append(f"{prefix}: unresolved clause cannot name a Plan target")
        problems.extend(_role_value_problems(record))
    unresolved = any(record.material and record.state in
                     {"ambiguous", "unsupported"} for record in case.records)
    if not unresolved and not any(
            record.state in {"consumed", "preserved"}
            and record.role == "subject" for record in case.records):
        problems.append("successful binding requires at least one subject")
    return problems


def _role_value_problems(record):
    if record.state not in {"consumed", "preserved"}:
        return []
    value = record.value
    if record.role == "subject" and value not in SEMANTIC_REFS:
        return [f"{record.clause_id}: unregistered semantic ref {value}"]
    if record.role in {"breakdown", "nested_breakdown"} \
            and value not in DIMENSION_REFS:
        return [f"{record.clause_id}: unregistered dimension {value}"]
    if record.role == "reducer" and value not in REDUCERS:
        return [f"{record.clause_id}: unregistered reducer {value}"]
    if record.role == "analysis" and value not in ANALYSES:
        return [f"{record.clause_id}: unregistered analysis {value}"]
    if record.role in {"time.target", "time.baseline"}:
        if (not isinstance(value, str)
                or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value)):
            return [f"{record.clause_id}: invalid month {value}"]
    if record.role == "filter":
        if (not isinstance(value, dict)
                or value.get("dimension") not in DIMENSION_REFS
                or not isinstance(value.get("values"), list)
                or not value["values"]):
            return [f"{record.clause_id}: invalid filter binding"]
        registered_values = DIMENSION_VALUES.get(value["dimension"])
        if (registered_values is not None
                and not set(value["values"]).issubset(registered_values)):
            return [f"{record.clause_id}: unregistered filter value"]
    if record.role == "ranking":
        if (not isinstance(value, dict)
                or value.get("measure") not in RANK_MEASURES
                or value.get("order") not in {"ascending", "descending"}
                or not isinstance(value.get("limit"), int)
                or isinstance(value.get("limit"), bool)
                or value["limit"] <= 0):
            return [f"{record.clause_id}: invalid ranking binding"]
    if record.role == "output" and value not in OUTPUTS:
        return [f"{record.clause_id}: unregistered output restriction {value}"]
    return []


def _project(case):
    values = {}
    for record in sorted(case.records, key=lambda item: (item.start, item.clause_id)):
        if record.state not in {"consumed", "preserved"}:
            continue
        values.setdefault(record.role, []).append(record.value)
    defaults = case.default_map()
    return {
        "subjects": tuple(values.get("subject", ())),
        "reducer": _one(values, "reducer", defaults.get("reducer", "sum")),
        "target_period": _one(
            values, "time.target", defaults.get("target_period", "2026-07")),
        "baseline_period": _one(
            values, "time.baseline", defaults.get("baseline_period")),
        "filters": tuple(values.get("filter", ())),
        "breakdowns": tuple(values.get("breakdown", ())),
        "analyses": tuple(values.get("analysis", ())) or ("level",),
        "ranking": _one(values, "ranking"),
        "nested_breakdown": _one(values, "nested_breakdown"),
        "outputs": tuple(values.get("output", ())),
        "binding_hash": binding_hash(case.records),
    }


def _one(values, role, default=None):
    items = values.get(role, ())
    if len(items) > 1:
        raise ValueError(f"multiple bindings for singleton role: {role}")
    return items[0] if items else default


def _bound_intent_problems(spec, projection):
    expected = {
        "subjects": projection["subjects"],
        "reducer": projection["reducer"],
        "target_period": projection["target_period"],
        "baseline_period": projection["baseline_period"],
        "filters": projection["filters"],
        "breakdowns": projection["breakdowns"],
        "analyses": projection["analyses"],
        "ranking": projection["ranking"],
        "nested_breakdown": projection["nested_breakdown"],
        "outputs": projection["outputs"],
    }
    problems = [name for name, value in expected.items()
                if getattr(spec, name) != value]
    if spec.intent_version != "1":
        problems.append("intent_version")
    if spec.binding_hash != projection["binding_hash"]:
        problems.append("binding_hash")
    return problems


def _emit_plan(case, projection):
    if not projection["subjects"]:
        raise ValueError("successful intent requires a subject")
    scope = {}
    for item in projection["filters"]:
        scope[item["dimension"]] = item["values"]
    target_slice = Slice.from_scope(
        projection["target_period"], "2026-08-16", scope)
    baseline = projection["baseline_period"]
    calls = []
    roots = []
    analysis = projection["analyses"][0]
    group_by = list(projection["breakdowns"])

    for index, subject in enumerate(projection["subjects"], start=1):
        suffix = f"{index:02d}"
        common = {"metric": subject, "reducer": projection["reducer"]}
        if group_by:
            common["group_by"] = group_by
        if baseline:
            before_id = f"n{suffix}a"
            before_inputs = dict(common)
            before_inputs["slice"] = Slice.from_scope(
                baseline, "2026-08-16", scope)
            calls.append(Call(before_id, "evaluate_metric@v1", before_inputs))
        after_id = f"n{suffix}b" if baseline else f"n{suffix}"
        after_inputs = dict(common)
        after_inputs["slice"] = target_slice
        calls.append(Call(after_id, "evaluate_metric@v1", after_inputs))
        root = Ref(after_id)
        if baseline:
            operator = ("contribution@v1" if analysis == "contribution"
                        else "delta@v1")
            compare_id = f"n{suffix}c"
            calls.append(Call(compare_id, operator, {
                "before": Ref(before_id), "after": Ref(after_id),
            }))
            root = Ref(compare_id)
        roots.append(root)

    if analysis == "divergence":
        align_id = "n090"
        calls.append(Call(align_id, "align_metrics@v1", {
            "metrics": tuple(roots),
        }))
        roots = [Ref(align_id)]

    if projection["ranking"]:
        rank_id = "n091"
        rank = projection["ranking"]
        calls.append(Call(rank_id, "rank@v1", {
            "input": roots[0], "measure": rank.get("measure", "value"),
            "order": rank["order"], "limit": rank["limit"],
        }))
        roots = [Ref(rank_id)]

    if projection["nested_breakdown"]:
        drill_id = "n092"
        calls.append(Call(drill_id, "drilldown@v1", {
            "selection": roots[0],
            "group_by": projection["nested_breakdown"],
        }))
        roots = [Ref(drill_id)]

    unknown = {call.operator_ref for call in calls} - REGISTERED_OPERATORS
    if unknown:
        raise ValueError(f"unregistered emitted operators: {sorted(unknown)}")
    return Plan(
        calls=tuple(calls), outputs=tuple(roots), binding_ledger=(),
        metadata={
            "question": case.question,
            "intent_binding_hash": binding_hash(case.records),
            "outputs": list(projection["outputs"]),
            "defaults_applied": dict(case.defaults),
            "experiment": "E-015",
            "shadow_only": True,
        },
    )


def _success(plan, records, bound_intent):
    result = {
        "status": "result", "plan": plan,
        "binding_record": tuple(records),
    }
    if bound_intent is not None:
        result["bound_intent"] = bound_intent
    return result


def _failure(status, check, details, records):
    return {
        "status": status,
        "violated": tuple({"check": check, "detail": detail}
                          for detail in details),
        "binding_record": tuple(records),
    }


def _record(question, clause_id, text, state, role=None, value=None,
            material=True, reason=None, occurrence=0):
    start = -1
    offset = 0
    for _ in range(occurrence + 1):
        start = question.index(text, offset)
        offset = start + len(text)
    target = ROLE_TARGETS.get(role)
    return ClauseBindingRecord(
        clause_id=clause_id, source_text=text, start=start,
        end=start + len(text), material=material, state=state, role=role,
        value=value, target_refs=((target,) if target and state in
                                  {"consumed", "preserved"} else ()),
        reason=reason,
    )


def intent_cases():
    cases = {}

    question = "7월 평균 재고는?"
    cases["average_inventory"] = IntentCase("average_inventory", question, (
        _record(question, "c01", "7월", "consumed", "time.target", "2026-07"),
        _record(question, "c02", "평균", "consumed", "reducer", "time_average"),
        _record(question, "c03", "재고", "consumed", "subject",
                "scm.inventory_balance@v1"),
        _record(question, "c04", "는?", "consumed", "analysis", "level"),
    ))

    question = "7월 재고 회전율은?"
    cases["inventory_turnover"] = IntentCase("inventory_turnover", question, (
        _record(question, "c01", "7월", "consumed", "time.target", "2026-07"),
        _record(question, "c02", "재고 회전율", "unsupported", "subject",
                reason="derived metric is not registered"),
        _record(question, "c03", "은?", "consumed", "analysis", "level"),
    ))

    question = "7월 오프라인 매출 감소를 지역별로 보여줘"
    cases["filtered_region_change"] = IntentCase(
        "filtered_region_change", question, (
            _record(question, "c01", "7월", "consumed", "time.target", "2026-07"),
            _record(question, "c02", "오프라인", "consumed", "filter",
                    {"dimension": "channel", "values": ["오프라인"]}),
            _record(question, "c03", "매출", "consumed", "subject",
                    "commerce.net_sales@v1"),
            _record(question, "c04", "감소", "consumed", "analysis",
                    "contribution"),
            _record(question, "c05", "지역별로", "consumed", "breakdown", "region"),
            _record(question, "c06", "보여줘", "preserved", "output", "result"),
        ), (("baseline_period", "2026-06"),))

    question = "7월 매출 감소 상위 3개 제품군만 보여줘"
    cases["top3_product_change"] = IntentCase(
        "top3_product_change", question, (
            _record(question, "c01", "7월", "consumed", "time.target", "2026-07"),
            _record(question, "c02", "매출", "consumed", "subject",
                    "commerce.net_sales@v1"),
            _record(question, "c03", "감소", "consumed", "analysis",
                    "contribution"),
            _record(question, "c04", "상위 3개", "consumed", "ranking",
                    {"measure": "contribution", "order": "descending", "limit": 3}),
            _record(question, "c05", "제품군", "consumed", "breakdown",
                    "product_category"),
            _record(question, "c06", "만", "preserved", "output", "only_ranked"),
            _record(question, "c07", "보여줘", "preserved", "output", "result"),
        ), (("baseline_period", "2026-06"),))

    question = "2025년 7월 매출은?"
    cases["explicit_year"] = IntentCase("explicit_year", question, (
        _record(question, "c01", "2025년 7월", "consumed", "time.target", "2025-07"),
        _record(question, "c02", "매출", "consumed", "subject",
                "commerce.net_sales@v1"),
        _record(question, "c03", "은?", "consumed", "analysis", "level"),
    ))

    question = "2025년 6월 대비 2025년 7월 매출은?"
    cases["explicit_comparison"] = IntentCase("explicit_comparison", question, (
        _record(question, "c01", "2025년 6월", "consumed", "time.baseline",
                "2025-06"),
        _record(question, "c02", "대비", "consumed", "analysis", "delta"),
        _record(question, "c03", "2025년 7월", "consumed", "time.target",
                "2025-07"),
        _record(question, "c04", "매출", "consumed", "subject",
                "commerce.net_sales@v1"),
    ))

    for case_id, question, text, reason in (
        ("acceleration", "7월 매출 증가 속도가 둔화되고 있는가?", "증가 속도가 둔화",
         "acceleration operator is not registered"),
        ("outlier", "7월 매출 감소가 일부 고객의 이상치 때문인가?", "일부 고객의 이상치",
         "outlier sensitivity operator is not registered"),
        ("concentration", "7월 매출은 제품과 지역 중 어디에 더 집중되어 있나?",
         "제품과 지역 중 어디에 더 집중", "cross-axis concentration is not registered"),
    ):
        records = (
            _record(question, "c01", "7월", "consumed", "time.target", "2026-07"),
            _record(question, "c02", "매출", "consumed", "subject",
                    "commerce.net_sales@v1"),
            _record(question, "c03", text, "unsupported", "analysis", reason=reason),
        )
        cases[case_id] = IntentCase(case_id, question, records)

    question = "7월 매출과 영업이익은 왜 엇갈렸나?"
    cases["multi_metric_divergence"] = IntentCase(
        "multi_metric_divergence", question, (
            _record(question, "c01", "7월", "consumed", "time.target", "2026-07"),
            _record(question, "c02", "매출", "consumed", "subject",
                    "commerce.net_sales@v1"),
            _record(question, "c03", "영업이익", "consumed", "subject",
                    "finance.operating_profit@v1"),
            _record(question, "c04", "엇갈렸나", "consumed", "analysis", "divergence"),
        ), (("baseline_period", "2026-06"),))

    question = "가장 큰 매출 하락 제품군을 찾고 그 안에서 지역별로 다시 분해해줘"
    cases["nested_diagnosis"] = IntentCase(
        "nested_diagnosis", question, (
            _record(question, "c01", "매출", "consumed", "subject",
                    "commerce.net_sales@v1"),
            _record(question, "c02", "하락", "consumed", "analysis", "contribution"),
            _record(question, "c03", "제품군", "consumed", "breakdown",
                    "product_category"),
            _record(question, "c04", "가장 큰", "consumed", "ranking",
                    {"measure": "contribution", "order": "descending", "limit": 1}),
            _record(question, "c05", "그 안에서", "preserved", "output",
                    "selected_segment_scope"),
            _record(question, "c06", "지역별로", "consumed", "nested_breakdown", "region"),
        ), (("target_period", "2026-07"), ("baseline_period", "2026-06")))

    question = "실적이 왜 안 좋아?"
    cases["ambiguous_performance"] = IntentCase("ambiguous_performance", question, (
        _record(question, "c01", "실적", "ambiguous", "subject",
                reason="multiple governed metrics match"),
        _record(question, "c02", "왜 안 좋아", "ambiguous", "analysis",
                reason="time and comparison basis are unspecified"),
    ))
    return cases


def inconsistent_bound_spec(case):
    compiled = compile_bound_intent(case)
    if compiled["status"] != "result":
        raise ValueError("case must compile successfully")
    return replace(compiled["bound_intent"], reducer="time_last")


def _wire(value):
    if isinstance(value, dict):
        return {key: _wire(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [_wire(item) for item in value]
    if isinstance(value, list):
        return [_wire(item) for item in value]
    return value


def _canonical_json(value):
    return json.dumps(_wire(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)
