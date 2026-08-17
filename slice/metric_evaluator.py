"""Aggregation-algebra-driven metric evaluation for E-013 shadow parity.

The current engine does not import this module.  It is the candidate execution
contract behind ``evaluate_metric@v1`` and deliberately never dispatches on a
metric id, domain, or nominal metric type.
"""
from dataclasses import dataclass
from datetime import date
import re
import hashlib
import json
from numbers import Number
from typing import Any, Mapping, Tuple

from analytical_ir import ResultEnvelope, Slice


RESULT_TYPE = "MetricScalar"
OPERATOR_REF = "evaluate_metric@v1"
LABEL_CEILING = "data_confirmed"


@dataclass(frozen=True)
class AggregateOutcome:
    value: Number
    components: Mapping[str, Number]
    expression: Mapping[str, Any]
    checks: Tuple[Mapping[str, Any], ...] = ()


class AggregationStrategy:
    rule = None
    required_bindings = ()
    accepted_metric_types = ()

    def validate_metric(self, metric):
        metric_type = metric.get("type")
        passed = metric_type in self.accepted_metric_types
        return (_check(
            "metric_type_aggregation_compatible", passed,
            (f"{metric_type} uses {self.rule}" if passed else
             f"{self.rule} accepts {self.accepted_metric_types}, got {metric_type}")),)

    def aggregate(self, metric, bindings, rows):
        raise NotImplementedError


class SumStrategy(AggregationStrategy):
    rule = "sum"
    required_bindings = ("value_field",)
    accepted_metric_types = ("amount", "count")

    def aggregate(self, metric, bindings, rows):
        field = bindings["value_field"]
        invalid = [index for index, row in enumerate(rows)
                   if not _is_number(row.get(field))]
        if invalid:
            raise EvaluationFailure(
                "out_of_domain", "numeric_value",
                f"non-numeric {field} rows: {invalid}")
        value = sum(row[field] for row in rows)
        return AggregateOutcome(
            value=value,
            components={"sum": value},
            expression={"op": "sum", "field": field},
        )


class RatioOfSumsStrategy(AggregationStrategy):
    rule = "denominator_weighted_mean"
    required_bindings = ("numerator_field", "denominator_field")
    accepted_metric_types = ("rate",)

    def validate_metric(self, metric):
        checks = super().validate_metric(metric)
        if not (metric.get("properties") or {}).get("has_denominator"):
            return (*checks, _check(
                "rate_denominator_declared", False,
                "denominator_weighted_mean requires has_denominator:true"),)
        return checks

    def aggregate(self, metric, bindings, rows):
        numerator_field = bindings["numerator_field"]
        denominator_field = bindings["denominator_field"]
        for field in (numerator_field, denominator_field):
            invalid = [index for index, row in enumerate(rows)
                       if not _is_number(row.get(field))]
            if invalid:
                raise EvaluationFailure(
                    "out_of_domain", "numeric_value",
                    f"non-numeric {field} rows: {invalid}")
        numerator = sum(row[numerator_field] for row in rows)
        denominator = sum(row[denominator_field] for row in rows)
        if denominator < 0:
            raise EvaluationFailure(
                "out_of_domain", "positive_denominator",
                f"sum denominator={denominator}")
        if denominator == 0:
            raise EvaluationFailure(
                "suspended", "positive_denominator",
                "nonzero denominator", "denominator must be nonzero")
        return AggregateOutcome(
            value=numerator / denominator,
            components={"numerator": numerator, "denominator": denominator},
            expression={
                "op": "ratio",
                "numerator": {"op": "sum", "field": numerator_field},
                "denominator": {"op": "sum", "field": denominator_field},
            },
            checks=(_check(
                "positive_denominator", True,
                f"sum denominator={denominator}"),),
        )


class PeriodEndSumStrategy(SumStrategy):
    rule = "semi_additive:last"
    accepted_metric_types = ("balance",)

    def validate_metric(self, metric):
        checks = super().validate_metric(metric)
        properties = metric.get("properties") or {}
        passed = (properties.get("time_semantics") == "period_end"
                  and properties.get("additive_across_time") is False)
        return (*checks, _check(
            "balance_time_semantics", passed,
            ("period-end reducer with time additivity disabled" if passed else
             "semi_additive:last requires time_semantics=period_end and "
             "additive_across_time=false")),)

    def aggregate(self, metric, bindings, rows):
        outcome = super().aggregate(metric, bindings, rows)
        expression = dict(outcome.expression)
        expression["time_selection"] = "period_end"
        return AggregateOutcome(
            value=outcome.value, components=outcome.components,
            expression=expression, checks=outcome.checks)


class EntityCardinalityStrategy(AggregationStrategy):
    rule = "non_aggregable"
    required_bindings = ("entity_id_field",)
    accepted_metric_types = ("distinct",)

    def aggregate(self, metric, bindings, rows):
        field = bindings["entity_id_field"]
        if any(row.get(field) is None for row in rows):
            raise EvaluationFailure(
                "out_of_domain", "entity_id_present", "NULL entity id")
        try:
            entities = {row[field] for row in rows}
        except TypeError:
            raise EvaluationFailure(
                "out_of_domain", "entity_id_hashable",
                "entity id must be a scalar hashable value")
        value = len(entities)
        return AggregateOutcome(
            value=value,
            components={"cardinality": value},
            expression={"op": "cardinality", "field": field},
        )


class AggregationStrategyRegistry:
    def __init__(self, strategies=None):
        self._strategies = {}
        for strategy in strategies or default_strategies():
            self.register(strategy)

    def register(self, strategy):
        if not strategy.rule:
            raise ValueError("aggregation strategy rule is required")
        if strategy.rule in self._strategies:
            raise ValueError(f"duplicate aggregation strategy: {strategy.rule}")
        self._strategies[strategy.rule] = strategy

    def resolve(self, rule):
        return self._strategies.get(rule)

    @property
    def rules(self):
        return tuple(sorted(self._strategies))


class EvaluationFailure(Exception):
    def __init__(self, status, check, detail, pass_conditions=None):
        super().__init__(detail)
        self.status = status
        self.check = check
        self.detail = detail
        self.pass_conditions = pass_conditions


def default_strategies():
    return (SumStrategy(), RatioOfSumsStrategy(), PeriodEndSumStrategy(),
            EntityCardinalityStrategy())


def evaluate_metric(metric, dimensions, rows, metric_slice, semantic_model_ref,
                    registry=None):
    """Return a strict ResultEnvelope containing one normalized MetricScalar."""
    metric_ref = _metric_ref(metric)
    design_problems = _descriptor_problems(metric, metric_slice)
    if design_problems:
        return _out_of_domain(design_problems)

    registry = registry or AggregationStrategyRegistry()
    rule = metric["properties"].get("aggregation_rule")
    strategy = registry.resolve(rule)
    if strategy is None:
        return _out_of_domain((_check(
            "aggregation_strategy_registered", False,
            f"unsupported aggregation rule: {rule}"),))

    window_checks = _validate_window(metric, metric_slice)
    failed_window = tuple(check for check in window_checks
                          if not check["passed"])
    if failed_window:
        return _out_of_domain(failed_window)

    bindings, binding_checks = _validate_bindings(metric, rows, strategy)
    if bindings is None:
        return _out_of_domain(binding_checks)

    _scope, scope_checks = _validate_scope(dimensions, rows, metric_slice)
    failed_scope = tuple(check for check in scope_checks if not check["passed"])
    if failed_scope:
        return _out_of_domain(failed_scope)

    selected = [row for row in rows if _matches(row, metric_slice)]
    if not selected:
        return ResultEnvelope(
            status="suspended", result_type=RESULT_TYPE,
            missing_inputs=(f"rows {metric_slice.period}",),
            pass_conditions="requested period observations must be loaded")

    if metric_slice.window == "iso_week":
        date_field = metric["bindings"]["date_field"]
        observed_days = {row.get(date_field) for row in selected}
        if len(observed_days) < 7:
            # 부분 주는 조용히 답하지 않는다 — 완결성은 달력 대비 관측일 수다.
            return ResultEnvelope(
                status="suspended", result_type=RESULT_TYPE,
                missing_inputs=(
                    f"rows {metric_slice.period} ({len(observed_days)}/7일)",),
                pass_conditions="완결 주(월~일 7일) 관측이 적재되면 실행 가능")

    strategy_checks = strategy.validate_metric(metric)
    failed_strategy = tuple(check for check in strategy_checks
                            if not check["passed"])
    if failed_strategy:
        return _out_of_domain(failed_strategy)

    sign_check = _validate_sign(metric, bindings, strategy, selected)
    if not sign_check["passed"]:
        return _out_of_domain((sign_check,))

    try:
        outcome = strategy.aggregate(metric, bindings, selected)
    except EvaluationFailure as failure:
        if failure.status == "suspended":
            return ResultEnvelope(
                status="suspended", result_type=RESULT_TYPE,
                missing_inputs=(failure.detail,),
                pass_conditions=failure.pass_conditions)
        return _out_of_domain((_check(
            failure.check, False, failure.detail),))

    bounds_check = _validate_bounds(metric, outcome.value)
    if not bounds_check["passed"]:
        return _out_of_domain((bounds_check,))

    provenance = {
        "metric_ref": metric_ref,
        "semantic_model_ref": semantic_model_ref,
        "input_snapshot_ref": _input_snapshot_ref(rows),
        "as_of": metric_slice.as_of,
    }
    provenance_ref = _provenance_ref(provenance, metric_slice)
    scalar = {
        "metric_ref": metric_ref,
        "slice": metric_slice.to_dict(),
        "value": outcome.value,
        "unit": metric["unit"],
        "aggregation": {
            "rule": rule,
            "expression": dict(outcome.expression),
            "components": dict(outcome.components),
        },
        "checks": [*binding_checks, *scope_checks, sign_check,
                   *strategy_checks, *outcome.checks, bounds_check],
        "provenance": provenance,
    }
    return ResultEnvelope(
        status="result", result_type=RESULT_TYPE, value=scalar,
        operator_ref=OPERATOR_REF, provenance_ref=provenance_ref,
        label_ceiling=LABEL_CEILING)


def _metric_ref(metric):
    metric_id = metric.get("id")
    version = metric.get("version")
    if not metric_id or not isinstance(version, int) or isinstance(version, bool):
        return "invalid@v0"
    return f"{metric_id}@v{version}"


def _descriptor_problems(metric, metric_slice):
    problems = []
    if not metric.get("id"):
        problems.append(_check("metric_identity", False, "metric id is required"))
    version = metric.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        problems.append(_check("metric_identity", False, "positive version is required"))
    if not metric.get("unit"):
        problems.append(_check("metric_unit", False, "metric unit is required"))
    if metric.get("type") not in {"amount", "count", "rate", "balance", "distinct"}:
        problems.append(_check("metric_type", False,
                               f"unsupported metric type: {metric.get('type')}"))
    if not isinstance(metric.get("properties"), dict):
        problems.append(_check("metric_properties", False,
                               "metric properties object is required"))
    if not isinstance(metric_slice, Slice):
        problems.append(_check("slice_valid", False, "Slice value is required"))
        return tuple(problems)
    try:
        date.fromisoformat(metric_slice.as_of)
    except (TypeError, ValueError):
        problems.append(_check("slice_valid", False,
                               f"invalid as_of: {metric_slice.as_of}"))
    if not _valid_period(metric_slice.period, metric_slice.window):
        problems.append(_check(
            "slice_valid", False,
            f"invalid {metric_slice.window} period: {metric_slice.period}"))
    predicate_dimensions = [dimension for dimension, _ in metric_slice.predicates]
    if len(predicate_dimensions) != len(set(predicate_dimensions)):
        problems.append(_check("slice_valid", False,
                               "duplicate predicate dimensions are ambiguous"))
    if any(not dimension or not values
           or any(not isinstance(value, str) or not value for value in values)
           for dimension, values in metric_slice.predicates):
        problems.append(_check("slice_valid", False,
                               "predicate values must be nonempty strings"))
    return tuple(problems)


PERIOD_FORMATS = {
    "month": r"[0-9]{4}-(0[1-9]|1[0-2])",
    "iso_week": r"[0-9]{4}-W(0[1-9]|[1-4][0-9]|5[0-3])",
}


def _valid_period(period, window):
    pattern = PERIOD_FORMATS.get(window)
    return (pattern is not None and isinstance(period, str)
            and re.fullmatch(pattern, period) is not None)


def _validate_bindings(metric, rows, strategy):
    bindings = metric.get("bindings")
    if not isinstance(bindings, dict):
        return None, (_check(
            "field_binding", False, "bindings object is required"),)
    values = list(bindings.values())
    if any(not isinstance(value, str) or not value for value in values):
        return None, (_check(
            "field_binding", False, "binding values must be nonempty field names"),)
    if len(values) != len(set(values)):
        return None, (_check(
            "field_binding_unique", False,
            "duplicate field bindings are ambiguous"),)
    missing_bindings = [name for name in strategy.required_bindings
                        if not bindings.get(name)]
    if missing_bindings:
        return None, (_check(
            "field_binding", False,
            f"missing bindings: {missing_bindings}"),)
    bound_fields = [bindings[name] for name in strategy.required_bindings]
    missing_fields = sorted({field for row in rows for field in bound_fields
                             if field not in row})
    if missing_fields:
        return None, (_check(
            "field_binding", False,
            f"fields absent from source rows: {missing_fields}"),)
    return bindings, (
        _check("field_binding_unique", True,
               f"unique bindings: {sorted(bindings)}"),
        _check("field_binding", True, f"bound fields: {bound_fields}"),
    )


def _validate_scope(dimensions, rows, metric_slice):
    scope = {dimension: values for dimension, values in metric_slice.predicates}
    checks = []
    problems = []
    for dimension, values in scope.items():
        descriptor = dimensions.get(dimension)
        if descriptor is None:
            problems.append(f"unknown scope dimension: {dimension}")
            continue
        unknown = sorted(set(values) - set(descriptor.get("values", [])))
        if unknown:
            problems.append(f"unknown {dimension} values: {unknown}")
        for required_dimension, required_value in (
                descriptor.get("applies_to") or {}).items():
            if set(scope.get(required_dimension, ())) != {required_value}:
                problems.append(
                    f"{dimension} requires {required_dimension}={required_value}")
    checks.append(_check(
        "scope_declared", not problems,
        "scope is declared" if not problems else "; ".join(problems)))

    coverage = []
    for row in rows:
        if row.get("month") != metric_slice.period or not _matches_scope(row, scope):
            continue
        for dimension, descriptor in dimensions.items():
            applies_to = descriptor.get("applies_to") or {}
            if any(row.get(key) != expected for key, expected in applies_to.items()):
                continue
            if row.get(dimension) not in descriptor.get("values", []):
                coverage.append(f"{dimension}={row.get(dimension)}")
    checks.append(_check(
        "dimension_coverage", not coverage,
        "dimension coverage complete" if not coverage else
        f"undeclared dimension observations: {sorted(set(coverage))}"))
    return scope, tuple(checks)


def _validate_sign(metric, bindings, strategy, rows):
    sign = metric["properties"].get("sign")
    if sign not in {"nonnegative", "any"}:
        return _check("sign_policy", False, f"unsupported sign policy: {sign}")
    if sign == "any" or isinstance(strategy, EntityCardinalityStrategy):
        return _check("sign_policy", True, f"policy={sign}")
    fields = [bindings[name] for name in strategy.required_bindings]
    negatives = [(index, field) for index, row in enumerate(rows)
                 for field in fields if _is_number(row.get(field)) and row[field] < 0]
    return _check(
        "sign_policy", not negatives,
        "no negative bound values" if not negatives else
        f"negative bound values: {negatives}")


def _validate_bounds(metric, value):
    bounds = metric["properties"].get("bounded") or {}
    lower, upper = bounds.get("lower"), bounds.get("upper")
    passed = ((lower is None or value >= lower)
              and (upper is None or value <= upper))
    return _check(
        "value_bounds", passed,
        f"value={value}, lower={lower}, upper={upper}")


def _validate_window(metric, metric_slice):
    """등록된 time window만 실행한다 — grain 게이트 (E-007/E-023).

    월간 시점 원천에 주간 질의가 침묵 응답하지 않도록, window 가용성은
    metric 계약의 선언(available_windows)에서만 온다.
    """
    window = metric_slice.window
    if window == "month":
        return (_check("window_registered", True, "month is the base window"),)
    available = tuple(metric.get("properties", {}).get(
        "available_windows", ("month",)))
    checks = [_check(
        "window_registered", window in available,
        (f"{window} is registered" if window in available else
         f"{window} is not registered for this source; available {available}"))]
    if window in available and window == "iso_week":
        has_date = bool(metric.get("bindings", {}).get("date_field"))
        checks.append(_check(
            "window_date_binding", has_date,
            ("date_field binding present" if has_date else
             "iso_week window requires a date_field binding")))
    return tuple(checks)


def _matches(row, metric_slice):
    return (_row_period(row, metric_slice.window) == metric_slice.period
            and _matches_scope(
                row, {dimension: values
                      for dimension, values in metric_slice.predicates}))


def _row_period(row, window):
    """행이 속한 등록 window의 period 라벨. 파생은 결정론적 달력 계산이다."""
    if window == "month":
        return row.get("month")
    if window == "iso_week":
        raw = row.get("date")
        if not raw:
            return None
        iso = date.fromisoformat(raw).isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return None


def _matches_scope(row, scope):
    return all(row.get(dimension) in values
               for dimension, values in scope.items())


def _valid_month(value):
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-":
        return False
    try:
        year, month = map(int, value.split("-"))
        date(year, month, 1)
    except (TypeError, ValueError):
        return False
    return True


def _is_number(value):
    return isinstance(value, Number) and not isinstance(value, bool)


def _check(name, passed, detail):
    return {"check": name, "passed": passed, "detail": detail,
            "checker": "machine"}


def _out_of_domain(checks):
    return ResultEnvelope(
        status="out_of_domain", result_type=RESULT_TYPE,
        violated=tuple(checks))


def _input_snapshot_ref(rows):
    raw = json.dumps(
        rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(raw).hexdigest()[:16]}"


def _provenance_ref(provenance, metric_slice):
    payload = {"provenance": provenance, "slice": metric_slice.to_dict(),
               "operator_ref": OPERATOR_REF}
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return f"eval:{hashlib.sha256(raw).hexdigest()[:16]}"
