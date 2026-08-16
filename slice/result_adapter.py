"""Central read-only normalization boundary for analytical results.

The adapter does not mutate or replace current public result payloads.  It gives
reporting, CLI, and storage one governed view while commerce and typed kernels
still emit their historical shapes.
"""
from numbers import Number

from analytical_ir import ResultEnvelope


CANONICAL_LABELS = {
    "data_confirmed": "데이터 확인",
    "data_suggestive": "데이터 시사",
    "consultant_judgment": "컨설턴트 판단",
    "reference": "참고치",
}


def adapt_result(result, result_key=None):
    """Return a normalized success view or a fail-closed adapter result."""
    if isinstance(result, ResultEnvelope):
        return _adapt_canonical_wire(result.to_dict(), result_key)
    if not isinstance(result, dict):
        return _failure("result must be an object")
    if "envelope_version" in result:
        return _adapt_canonical_wire(result, result_key)
    return _adapt_legacy(result, result_key)


def claim_ceiling(view, statement_type):
    """Select the declared ceiling relevant to a report statement role."""
    capabilities = set(view.get("label_capabilities") or [])
    preferences = {
        "fact": ("data_confirmed", "reference", "data_suggestive"),
        "arithmetic": ("data_confirmed", "reference", "data_suggestive"),
        "suggestion": ("data_suggestive", "data_confirmed", "reference"),
        "judgment": ("consultant_judgment",),
        "meta": ("data_confirmed", "reference", "data_suggestive"),
    }.get(statement_type, ())
    capability = next((item for item in preferences if item in capabilities), None)
    return None if capability is None else CANONICAL_LABELS[capability]


def label_within_ceiling(label, ceiling):
    """Whether a claim label is no stronger/different than its declared ceiling."""
    allowed = {
        "데이터 확인": {"데이터 확인", "데이터 시사", "참고치"},
        "데이터 시사": {"데이터 시사", "참고치"},
        "컨설턴트 판단": {"컨설턴트 판단"},
        "참고치": {"참고치"},
    }
    return label in allowed.get(ceiling, set())


def _adapt_legacy(result, result_key):
    if result.get("status") != "result":
        return _failure("normal analytical result required")
    result_type = result.get("output_type")
    if not result_type:
        return _failure("successful result requires output_type")
    operator_ref = result.get("operator_ref")
    provenance_ref = result.get("provenance_ref")
    if not operator_ref or not provenance_ref:
        return _failure("successful result requires operator_ref and provenance_ref")

    capabilities = _legacy_label_capabilities(result.get("label_ceiling"))
    if not capabilities:
        return _failure("successful result requires a recognized label_ceiling")

    scalar = None
    if result_type == "MetricLevel":
        fields = [field for field in ("value_u", "value") if field in result]
        if len(fields) != 1:
            return _failure(
                f"MetricLevel requires exactly one scalar field, got {fields}")
        field = fields[0]
        if not isinstance(result[field], Number) or isinstance(result[field], bool):
            return _failure(f"MetricLevel scalar must be numeric: {field}")
        if not result_key:
            return _failure("MetricLevel normalization requires result_key")
        unit = result.get("unit")
        if field == "value_u":
            if unit not in (None, "0.1억원(u)"):
                return _failure(f"value_u has incompatible unit: {unit}")
            unit = "0.1억원(u)"
        elif not unit:
            return _failure("value scalar requires an explicit unit")
        scalar = {
            "value": result[field],
            "unit": unit,
            "source_ref": f"results.{result_key}.{field}",
        }

    change = None
    total = result.get("total")
    if isinstance(total, dict):
        fields = [field for field in ("delta_u", "gap_u", "delta")
                  if field in total]
        if len(fields) != 1:
            return _failure(
                f"result total requires exactly one change field, got {fields}")
        field = fields[0]
        if not _numeric(total[field]):
            return _failure(f"result change must be numeric: {field}")
        unit = _legacy_unit(field, result.get("unit"))
        if unit is None:
            return _failure(f"change field has no compatible unit: {field}")
        before_field = next(
            (name for name in ("before_u", "plan_u", "before") if name in total),
            None)
        pct_change = None
        if "pct_change" in total:
            if not _numeric(total["pct_change"]):
                return _failure("pct_change must be numeric")
            pct_change = {
                "value": total["pct_change"],
                "source_ref": f"results.{result_key}.total.pct_change",
                "denominator_ref": (f"results.{result_key}.total.{before_field}"
                                    if before_field else None),
            }
        segments = []
        for index, segment in enumerate(result.get("segments") or []):
            segment_fields = [name for name in ("delta_u", "gap_u", "delta")
                              if name in segment]
            if len(segment_fields) != 1:
                return _failure(
                    f"segment {index} requires exactly one change field, "
                    f"got {segment_fields}")
            segment_field = segment_fields[0]
            if not _numeric(segment[segment_field]):
                return _failure(
                    f"segment {index} change must be numeric: {segment_field}")
            if "segment" not in segment:
                return _failure(f"segment {index} requires segment identity")
            segments.append({
                "segment": segment["segment"],
                "value": segment[segment_field],
                "source_ref": (
                    f"results.{result_key}.segments.{index}.{segment_field}"),
            })
        change = {
            "value": total[field],
            "unit": unit,
            "source_ref": f"results.{result_key}.total.{field}",
            "pct_change": pct_change,
            "segments": segments,
        }

    return {
        "status": "result",
        "view": {
            "result_key": result_key,
            "result_type": result_type,
            "operator_ref": operator_ref,
            "provenance_ref": provenance_ref,
            "scalar": scalar,
            "change": change,
            "label_capabilities": sorted(capabilities),
            "source_shape": "legacy",
        },
    }


def _adapt_canonical_wire(result, result_key):
    if result.get("envelope_version") != "1" or result.get("status") != "result":
        return _failure("canonical Result Envelope v1 success required")
    evidence = result.get("evidence") or {}
    operator_ref = evidence.get("operator_ref")
    provenance_ref = evidence.get("provenance_ref")
    if not operator_ref or not provenance_ref:
        return _failure("canonical result evidence is incomplete")
    capabilities = _canonical_label_capabilities(evidence.get("label_ceiling"))
    if not capabilities:
        return _failure("canonical result requires a recognized label_ceiling")

    scalar = None
    if result.get("result_type") == "MetricScalar":
        value = result.get("value")
        if not isinstance(value, dict) or "value" not in value or not value.get("unit"):
            return _failure("MetricScalar payload requires value and unit")
        if not isinstance(value["value"], Number) or isinstance(value["value"], bool):
            return _failure("MetricScalar value must be numeric")
        if not result_key:
            return _failure("MetricScalar normalization requires result_key")
        scalar = {
            "value": value["value"],
            "unit": value["unit"],
            "source_ref": f"results.{result_key}.value.value",
        }

    return {
        "status": "result",
        "view": {
            "result_key": result_key,
            "result_type": result.get("result_type"),
            "operator_ref": operator_ref,
            "provenance_ref": provenance_ref,
            "scalar": scalar,
            "change": None,
            "label_capabilities": sorted(capabilities),
            "source_shape": "canonical",
        },
    }


def _legacy_label_capabilities(raw_ceiling):
    if not isinstance(raw_ceiling, dict) or not raw_ceiling:
        return set()
    capabilities = set()
    for value in raw_ceiling.values():
        if not isinstance(value, str):
            continue
        if "데이터 확인" in value or "조건부 확인" in value:
            capabilities.add("data_confirmed")
        if "데이터 시사" in value or "시사 상한" in value:
            capabilities.add("data_suggestive")
        if "컨설턴트 판단" in value:
            capabilities.add("consultant_judgment")
        if "참고" in value:
            capabilities.add("reference")
    return capabilities


def _canonical_label_capabilities(raw_ceiling):
    if isinstance(raw_ceiling, str) and raw_ceiling in CANONICAL_LABELS:
        return {raw_ceiling}
    if isinstance(raw_ceiling, list):
        return {value for value in raw_ceiling if value in CANONICAL_LABELS}
    return set()


def _failure(detail):
    return {
        "status": "out_of_domain",
        "violated": [{
            "check": "result_normalization", "passed": False,
            "detail": detail,
        }],
    }


def _legacy_unit(field, declared_unit):
    if field.endswith("_u"):
        return "0.1억원(u)" if declared_unit in (None, "0.1억원(u)") else None
    return declared_unit


def _numeric(value):
    return isinstance(value, Number) and not isinstance(value, bool)
