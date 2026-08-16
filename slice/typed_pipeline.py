"""Metric descriptor와 field binding만 소비하는 공통 실행 adapter."""
from pipeline import _input_hash, _spec_hash
from query_spec import validate_query_spec
from runtime import ExecutionRuntime, load_operator_registry
from typed_kernel import (denominator_weighted_rate, typed_contrib_decomp,
                          typed_distinct_decomp, typed_distinct_level,
                          typed_metric_level)


def _bundle(spec_envelope, results, runtime, sem, rows, source_ref):
    spec = spec_envelope["query_spec"]
    record = runtime.record
    record["query_spec_hash"] = _spec_hash(spec)
    record["provenance"] = {
        "metric_ref": f"{sem['metric']['id']}@v{sem['metric']['version']}",
        "semantic_model_ref": source_ref,
        "input_snapshot_ref": f"sha256:{_input_hash(rows)}",
        "as_of": spec["as_of"],
    }
    return {
        "spec": spec_envelope, "results": results, "execution_record": record,
        "assumption_ledger": [], "external_reference_check": None,
    }


def execute_typed_query(spec_envelope, sem, rows, source_ref="typed-domain-pack"):
    spec = spec_envelope["query_spec"]
    checked = validate_query_spec(spec, sem, rows)
    if checked["status"] != "result":
        return {"spec": spec_envelope, "results": {"query_spec": checked},
                "execution_record": None, "assumption_ledger": [],
                "external_reference_check": None}

    metric = sem["metric"]
    dimensions = sem["dimensions"]
    scope = spec["scope"]
    focal = spec["focal_period"]
    comp = spec["comparison"]
    family = spec["intent"]["operation_family"]
    registry = load_operator_registry()
    runtime = ExecutionRuntime(
        sem["question_defaults"]["exploration_budget"], family,
        registry=registry, metric=metric)
    results = {}

    if family == "inspect_level":
        if metric["type"] == "rate":
            operator = "rate_level"

            def invoke(record):
                record["calls"].append(
                    {"operator": operator, "month": focal, "within": scope})
                return denominator_weighted_rate(
                    metric, rows, focal, registry, within=scope, dimensions=dimensions)
        elif metric["type"] == "distinct":
            operator = "distinct_level"

            def invoke(record):
                record["calls"].append(
                    {"operator": operator, "month": focal, "within": scope})
                return typed_distinct_level(
                    metric, dimensions, rows, focal, registry, within=scope)
        else:
            operator = "metric_level"

            def invoke(record):
                record["calls"].append(
                    {"operator": operator, "month": focal, "within": scope})
                return typed_metric_level(
                    metric, dimensions, rows, focal, registry, within=scope)

        results["level"] = runtime.execute(operator, 1, 1, invoke)

    elif family == "explain_change":
        if metric["type"] == "distinct":
            month_a, month_b = comp["period"], focal
            axes = [dim for dim in dimensions if dim not in scope]
            for dim in dimensions:
                if dim not in axes:
                    runtime.reject(f"distinct_decomp:{dim}",
                                   "query scope에서 이미 고정된 차원")
            for dim in axes:
                key = f"distinct:{dim}"

                def invoke(record, dim=dim):
                    record["calls"].append({
                        "operator": "distinct_decomp", "dim": dim,
                        "months": [month_a, month_b], "within": scope})
                    return typed_distinct_decomp(
                        metric, dimensions, rows, dim, month_a, month_b,
                        registry, within=scope)

                results[key] = runtime.execute(
                    f"distinct_decomp:{dim}", 1, len(dimensions[dim]["values"]), invoke)
        elif not metric["properties"].get("additive_across_dims"):
            results["change"] = {
                "status": "out_of_domain",
                "violated": [{"check": "change_operator_available", "passed": False,
                              "detail": f"{metric['type']} 변화 연산자 미등록"}],
                "alternatives": ["rate 변화 분해 operator 등록"],
            }
        else:
            month_a, month_b = comp["period"], focal
            axes = [dim for dim in dimensions if dim not in scope]
            for dim in dimensions:
                if dim not in axes:
                    runtime.reject(f"contrib_decomp:{dim}", "query scope에서 이미 고정된 차원")
            for dim in axes:
                key = f"contrib:{dim}"

                def invoke(record, dim=dim):
                    record["calls"].append({
                        "operator": "contrib_decomp", "dim": dim,
                        "months": [month_a, month_b], "within": scope})
                    return typed_contrib_decomp(
                        metric, dimensions, rows, dim, month_a, month_b,
                        registry, within=scope)

                results[key] = runtime.execute(
                    f"contrib_decomp:{dim}", 1, len(dimensions[dim]["values"]), invoke)
    else:
        results["intent"] = {
            "status": "out_of_domain",
            "violated": [{"check": "operation_family", "passed": False,
                          "detail": f"typed_core는 {family} 미지원"}],
        }

    return _bundle(spec_envelope, results, runtime, sem, rows, source_ref)
