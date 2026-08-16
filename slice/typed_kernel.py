"""이종 지표 challenge용 타입 기반 최소 커널.

유통 `kernel.py`의 완전한 대체가 아니라 H1의 반증 도구다. 지표 이름을 보지 않고 metric
descriptor의 type, aggregation_rule, field binding만으로 연산의 정의역을 판정한다.
"""
from collections import defaultdict


def operator_admissible(registry, operator, metric):
    contract = registry["operators"].get(operator)
    if contract is None:
        return {"status": "out_of_domain",
                "violated": [{"check": "operator_registered", "passed": False,
                              "detail": operator}]}
    accepted = contract.get("metric_types")
    if accepted is not None and metric["type"] not in accepted:
        return {"status": "out_of_domain",
                "violated": [{"check": "metric_type_admissible", "passed": False,
                              "detail": f"{metric['type']} not in {accepted}"}]}
    return {"status": "result"}


def _matches(row, within):
    for key, expected in (within or {}).items():
        values = expected if isinstance(expected, list) else [expected]
        if row.get(key) not in values:
            return False
    return True


def _scope_check(dimensions, rows, months, within):
    problems = []
    for dim, expected in (within or {}).items():
        descriptor = dimensions.get(dim)
        if descriptor is None:
            problems.append(f"미등록 scope dimension {dim}")
            continue
        values = expected if isinstance(expected, list) else [expected]
        unknown = sorted(set(values) - set(descriptor["values"]))
        if unknown:
            problems.append(f"{dim} 미등록 값 {unknown}")
    for dim, descriptor in dimensions.items():
        declared = set(descriptor["values"])
        bad = sorted({str(r.get(dim)) for r in rows
                      if r.get("month") in months and _matches(r, within)
                      and r.get(dim) not in declared})
        if bad:
            problems.append(f"{dim} 원장 미등록 값 {bad}")
    if problems:
        return {"check": "dimension_coverage", "passed": False,
                "detail": "; ".join(problems)}
    return {"check": "dimension_coverage", "passed": True,
            "detail": "scope와 차원 커버리지 완전"}


def _value_binding(metric, rows, fields):
    bindings = metric.get("bindings") or {}
    all_bound = list(bindings.values())
    if len(all_bound) != len(set(all_bound)):
        return None, {"check": "field_binding_unique", "passed": False,
                      "detail": "중복 field binding은 모호하므로 실행 불가"}
    missing_bindings = [name for name in fields if not bindings.get(name)]
    if missing_bindings:
        return None, {"check": "field_binding", "passed": False,
                      "detail": f"미지정 binding {missing_bindings}"}
    bound = [bindings[name] for name in fields]
    missing_fields = sorted({field for row in rows for field in bound if field not in row})
    if missing_fields:
        return None, {"check": "field_binding", "passed": False,
                      "detail": f"원장에 없는 필드 {missing_fields}"}
    return bindings, {"check": "field_binding", "passed": True,
                      "detail": f"binding={bound}"}


def _balance_semantics(metric):
    if metric["type"] != "balance":
        return {"check": "balance_time_semantics", "passed": True,
                "detail": "balance 아님"}
    props = metric["properties"]
    passed = (props.get("additive_across_time") is False
              and props.get("aggregation_rule") == "semi_additive:last"
              and props.get("time_semantics") == "period_end")
    return {"check": "balance_time_semantics", "passed": passed,
            "detail": ("월말 시점 잔액·시간 합산 금지" if passed else
                       "balance는 additive_across_time:false, semi_additive:last, "
                       "time_semantics:period_end 필요")}


def typed_metric_level(metric, dimensions, rows, month, registry, within=None):
    admitted = operator_admissible(registry, "metric_level", metric)
    if admitted["status"] != "result":
        return admitted
    balance_check = _balance_semantics(metric)
    if not balance_check["passed"]:
        return {"status": "out_of_domain", "violated": [balance_check]}
    bindings, binding_check = _value_binding(metric, rows, ["value_field"])
    coverage = _scope_check(dimensions, rows, {month}, within)
    if bindings is None or not coverage["passed"]:
        return {"status": "out_of_domain",
                "violated": [c for c in (binding_check, coverage) if not c["passed"]]}
    value_field = bindings["value_field"]
    selected = [r for r in rows if r.get("month") == month and _matches(r, within)]
    if not selected:
        return {"status": "suspended", "missing_inputs": [f"rows {month}"],
                "pass_conditions": "요청 기간 관측치가 적재되면 실행 가능"}
    if metric["properties"].get("sign") == "nonnegative" \
            and any(r[value_field] < 0 for r in selected):
        return {"status": "out_of_domain",
                "violated": [{"check": "sign_policy", "passed": False,
                              "detail": "음수 값"}]}
    value = sum(r[value_field] for r in selected)
    return {"status": "result", "output_type": "MetricLevel",
            "estimand": f"{month} {metric['id']} 수준",
            "month": month, "value": value, "unit": metric["unit"],
            "checks": [binding_check, coverage, balance_check],
            "label_ceiling": {"level": "데이터 확인"}}


def typed_contrib_decomp(metric, dimensions, rows, dim, month_a, month_b,
                         registry, within=None):
    admitted = operator_admissible(registry, "contrib_decomp", metric)
    if admitted["status"] != "result":
        return admitted
    if not metric["properties"].get("additive_across_dims"):
        return {"status": "out_of_domain",
                "violated": [{"check": "additive_across_dims", "passed": False,
                              "detail": metric["id"]}]}
    if dim not in dimensions or not dimensions[dim].get("mece"):
        return {"status": "out_of_domain",
                "violated": [{"check": "mece_dimension", "passed": False,
                              "detail": dim}]}

    balance_check = _balance_semantics(metric)
    if not balance_check["passed"]:
        return {"status": "out_of_domain", "violated": [balance_check]}

    bindings, binding_check = _value_binding(metric, rows, ["value_field"])
    if bindings is None:
        return {"status": "out_of_domain", "violated": [binding_check]}
    coverage = _scope_check(dimensions, rows, {month_a, month_b}, within)
    if not coverage["passed"]:
        return {"status": "out_of_domain", "violated": [coverage]}
    value_field = bindings["value_field"]
    declared = dimensions[dim]["values"]
    unknown = sorted({str(r.get(dim)) for r in rows
                      if r["month"] in (month_a, month_b) and _matches(r, within)
                      and r.get(dim) not in declared})
    if unknown:
        return {"status": "out_of_domain",
                "violated": [{"check": "dimension_coverage", "passed": False,
                              "detail": f"미등록 값 {unknown}"}]}
    sign = metric["properties"].get("sign")
    if sign == "nonnegative" and any(
            r[value_field] < 0 for r in rows
            if r["month"] in (month_a, month_b) and _matches(r, within)):
        return {"status": "out_of_domain",
                "violated": [{"check": "sign_policy", "passed": False,
                              "detail": "음수 값"}]}

    totals = {month_a: defaultdict(int), month_b: defaultdict(int)}
    for row in rows:
        if row["month"] in totals and _matches(row, within):
            totals[row["month"]][row[dim]] += row[value_field]
    segments = [{"segment": value,
                 "before": totals[month_a][value],
                 "after": totals[month_b][value],
                 "delta": totals[month_b][value] - totals[month_a][value]}
                for value in declared]
    before = sum(r[value_field] for r in rows
                 if r["month"] == month_a and _matches(r, within))
    after = sum(r[value_field] for r in rows
                if r["month"] == month_b and _matches(r, within))
    total_delta = after - before
    contribution_sum = sum(s["delta"] for s in segments)
    identity = {"check": "identity_recheck", "passed": contribution_sum == total_delta,
                "detail": f"Σ기여={contribution_sum} vs 원시 Δ={total_delta}"}
    if not identity["passed"]:
        return {"status": "out_of_domain", "violated": [identity]}
    return {"status": "result", "output_type": "Attribution",
            "estimand": f"{metric['id']} Δ의 {dim} 가법 기여분",
            "total": {"before": before, "after": after, "delta": total_delta},
            "total_delta": total_delta, "unit": metric["unit"], "segments": segments,
            "checks": [binding_check, coverage, balance_check, identity],
            "label_ceiling": {"contribution": "데이터 확인"}}


def typed_distinct_level(metric, dimensions, rows, month, registry, within=None):
    admitted = operator_admissible(registry, "distinct_level", metric)
    if admitted["status"] != "result":
        return admitted
    bindings, binding_check = _value_binding(metric, rows, ["entity_id_field"])
    coverage = _scope_check(dimensions, rows, {month}, within)
    if bindings is None or not coverage["passed"]:
        return {"status": "out_of_domain",
                "violated": [c for c in (binding_check, coverage) if not c["passed"]]}
    selected = [r for r in rows if r["month"] == month and _matches(r, within)]
    if not selected:
        return {"status": "suspended", "missing_inputs": [f"rows {month}"],
                "pass_conditions": "요청 기간 관측치가 적재되면 실행 가능"}
    entity_field = bindings["entity_id_field"]
    if any(r.get(entity_field) is None for r in selected):
        return {"status": "out_of_domain",
                "violated": [{"check": "entity_id_present", "passed": False,
                              "detail": "NULL entity id"}]}
    value = len({r[entity_field] for r in selected})
    return {"status": "result", "output_type": "MetricLevel",
            "estimand": f"{month} {metric['id']} distinct entity 수",
            "month": month, "value": value, "unit": metric["unit"],
            "checks": [binding_check, coverage],
            "label_ceiling": {"level": "데이터 확인"}}


def typed_distinct_decomp(metric, dimensions, rows, dim, month_a, month_b,
                          registry, within=None):
    admitted = operator_admissible(registry, "distinct_decomp", metric)
    if admitted["status"] != "result":
        return admitted
    descriptor = dimensions.get(dim)
    entity_type = metric["properties"].get("entity_type")
    if descriptor is None or not entity_type \
            or not (descriptor.get("entity_functional") or {}).get(entity_type):
        return {"status": "out_of_domain",
                "violated": [{"check": "entity_functional_dimension", "passed": False,
                              "detail": f"{dim} × {entity_type}"}]}
    bindings, binding_check = _value_binding(metric, rows, ["entity_id_field"])
    coverage = _scope_check(dimensions, rows, {month_a, month_b}, within)
    if bindings is None or not coverage["passed"]:
        return {"status": "out_of_domain",
                "violated": [c for c in (binding_check, coverage) if not c["passed"]]}
    entity_field = bindings["entity_id_field"]
    selected = [r for r in rows if r["month"] in (month_a, month_b) and _matches(r, within)]
    if any(r.get(entity_field) is None for r in selected):
        return {"status": "out_of_domain",
                "violated": [{"check": "entity_id_present", "passed": False,
                              "detail": "NULL entity id"}]}

    assignments = defaultdict(set)
    by_segment = {month_a: defaultdict(set), month_b: defaultdict(set)}
    totals = {month_a: set(), month_b: set()}
    for row in selected:
        key = (row["month"], row[entity_field])
        assignments[key].add(row[dim])
        by_segment[row["month"]][row[dim]].add(row[entity_field])
        totals[row["month"]].add(row[entity_field])
    conflicts = sorted(f"{month}:{entity}" for (month, entity), values in assignments.items()
                       if len(values) > 1)
    if conflicts:
        return {"status": "out_of_domain",
                "violated": [{"check": "entity_functional_runtime", "passed": False,
                              "detail": f"복수 값 entity {conflicts}"}]}

    segments = []
    for value in descriptor["values"]:
        before = len(by_segment[month_a][value])
        after = len(by_segment[month_b][value])
        segments.append({"segment": value, "before": before, "after": after,
                         "delta": after - before})
    total_before, total_after = len(totals[month_a]), len(totals[month_b])
    total_delta = total_after - total_before
    contribution_sum = sum(row["delta"] for row in segments)
    identity = {"check": "identity_recheck", "passed": contribution_sum == total_delta,
                "detail": f"Σdistinct 기여={contribution_sum} vs 전체 Δ={total_delta}"}
    if not identity["passed"]:
        return {"status": "out_of_domain", "violated": [identity]}
    return {"status": "result", "output_type": "Attribution",
            "estimand": f"{metric['id']} distinct Δ의 {dim} 기여분",
            "total": {"before": total_before, "after": total_after, "delta": total_delta},
            "total_delta": total_delta, "unit": metric["unit"], "segments": segments,
            "checks": [binding_check, coverage, identity],
            "label_ceiling": {"contribution": "데이터 확인"}}


def denominator_weighted_rate(metric, rows, month, registry, within=None, dimensions=None):
    admitted = operator_admissible(registry, "rate_level", metric)
    if admitted["status"] != "result":
        return admitted
    props = metric["properties"]
    if props.get("aggregation_rule") != "denominator_weighted_mean":
        return {"status": "out_of_domain",
                "violated": [{"check": "rate_aggregation_rule", "passed": False,
                              "detail": "rate는 denominator_weighted_mean 필요"}]}
    bindings, binding_check = _value_binding(
        metric, rows, ["numerator_field", "denominator_field"])
    if bindings is None:
        return {"status": "out_of_domain", "violated": [binding_check]}
    coverage = _scope_check(dimensions or {}, rows, {month}, within)
    if not coverage["passed"]:
        return {"status": "out_of_domain", "violated": [coverage]}
    selected = [r for r in rows if r["month"] == month and _matches(r, within)]
    if not selected:
        return {"status": "suspended", "missing_inputs": [f"rows {month}"],
                "pass_conditions": "요청 기간 관측치가 적재되면 실행 가능"}
    numerator_field = bindings["numerator_field"]
    denominator_field = bindings["denominator_field"]
    if metric["properties"].get("sign") == "nonnegative" and any(
            r[numerator_field] < 0 or r[denominator_field] < 0 for r in selected):
        return {"status": "out_of_domain",
                "violated": [{"check": "sign_policy", "passed": False,
                              "detail": "분자·분모에 음수 값"}]}
    numerator = sum(r[numerator_field] for r in selected)
    denominator = sum(r[denominator_field] for r in selected)
    if denominator < 0:
        return {"status": "out_of_domain",
                "violated": [{"check": "positive_denominator", "passed": False,
                              "detail": f"Σ분모={denominator}"}]}
    if denominator == 0:
        return {"status": "suspended", "missing_inputs": ["nonzero denominator"],
                "pass_conditions": "분모가 0이 아닌 관측 범위"}
    return {"status": "result", "output_type": "MetricLevel",
            "estimand": f"{month} {metric['id']} = Σ분자/Σ분모",
            "numerator": numerator, "denominator": denominator,
            "value": numerator / denominator,
            "unit": metric["unit"],
            "aggregation_rule": "denominator_weighted_mean",
            "checks": [binding_check, coverage,
                       {"check": "positive_denominator", "passed": True,
                        "detail": f"Σ분모={denominator}"}],
            "label_ceiling": {"rate": "데이터 확인"}}
