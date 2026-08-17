"""E-016 shadow-only Korean intent compiler and fidelity boundary.

The deterministic adapter is intentionally small and governed-corpus scoped. It
proposes source clauses; ``clause_binding`` validates the closed record, and the
compiler emits canonical Call+Ref Plans without touching ``engine.run_question``.
Unknown analytical language fails closed instead of falling back to the current
three-family interpreter.
"""
from dataclasses import replace
from datetime import date
import re

from analytical_ir import Call, Plan, Ref, Slice
from catalog import load_metric_catalog
from clause_binding import (
    ANALYSIS_REFS, BindingValue, ClauseBinding, SourceClauseBindingRecord,
    validate_binding_record,
)
from query_spec import shift_month
from shadow_registry import ShadowOperatorRegistry


DIMENSION_ALIASES = (
    (r"제품군(?:별(?:로)?)?|카테고리별(?:로)?", "category"),
    (r"지역별(?:로)?", "region"),
    (r"(?:어느\s*)?지역에서\s*발생", "region"),
    (r"고객\s*유형별(?:로)?", "customer_type"),
    (r"채널별(?:로)?", "channel"),
    (r"사업부별(?:로)?", "business_unit"),
    (r"창고별(?:로)?|(?:어느\s*)?창고에서", "warehouse"),
)

UNSUPPORTED_PATTERNS = (
    (r"재고\s*회전율", "subject",
     "derived inventory-turnover metric is not registered"),
    (r"증가\s*속도가\s*둔화(?:되고\s*있는가|됐나|되는가)?", "analysis",
     "acceleration/deceleration operator is not registered"),
    (r"감소가\s*일부\s*고객의\s*이상치\s*때문인가", "analysis",
     "outlier-sensitivity operator is not registered"),
    (r"제품과\s*지역\s*중\s*어디에\s*더\s*집중(?:되어\s*있나|되어\s*있는가|됐나)",
     "analysis", "cross-axis concentration operator is not registered"),
)

ANALYSIS_PATTERNS = (
    (r"계획\s*대비", "plan"),
    (r"엇갈렸(?:나|는가)?", "divergence"),
    (r"변동을\s*제품군별\s*기여로", "contribution"),
    (r"전월\s*대비\s*어떻게\s*달라졌(?:어|나)?", "contribution"),
    (r"변화\s*원인(?:은)?", "contribution"),
    (r"감소\s*동인(?:은)?", "contribution"),
    (r"왜\s*(?:변했|줄었|빠졌)(?:나|지|어)?", "contribution"),
    (r"감소|하락", "contribution"),
    (r"증가", "contribution"),
    (r"변했|변화|변동|달라졌", "delta"),
)


def compile_shadow_intent(question, contexts=None, registry=None, proposer=None):
    """Compile a governed Korean question to C4 or a clause-local refusal.

    ``proposer``는 절 바인딩 제안 함수를 교체하는 명시적 주입점이다(기본:
    규칙 기반). 어떤 제안자든 검증·컴파일·실행의 결정론 권위는 바뀌지 않는다.
    """
    contexts = contexts or load_metric_catalog()
    registry = registry or ShadowOperatorRegistry()
    vocabulary = _vocabulary(contexts, registry)
    proposer = proposer or propose_clause_bindings
    proposed = proposer(question, contexts, vocabulary=vocabulary)

    problems = validate_binding_record(proposed, vocabulary)
    if problems:
        return _failure("out_of_domain", "clause_binding_valid", problems, proposed)

    ambiguous = [row for row in proposed.clauses
                 if row.material and row.state == "ambiguous"]
    if ambiguous:
        return _failure(
            "clarify", "material_clause_ambiguous",
            [f"{row.clause_id}: {row.reason}" for row in ambiguous], proposed)
    unsupported = [row for row in proposed.clauses
                   if row.material and row.state == "unsupported"]
    if unsupported:
        return _failure(
            "out_of_domain", "material_clause_supported",
            [f"{row.clause_id}: {row.reason}" for row in unsupported], proposed)

    projection, projection_problems = _project(proposed, contexts)
    if projection_problems:
        return _failure("out_of_domain", "intent_projection_valid",
                        projection_problems, proposed)

    calls, outputs, consumers = _emit_calls(proposed, projection)
    final_clauses = tuple(replace(
        row, target_refs=tuple(consumers.get(row.clause_id, ())))
        for row in proposed.clauses)
    final_record = replace(proposed, clauses=final_clauses)
    allowed_targets = {target for targets in consumers.values() for target in targets}
    problems = validate_binding_record(
        final_record, vocabulary, allowed_targets=allowed_targets,
        require_targets=True)
    if problems:
        return _failure("out_of_domain", "clause_plan_link_valid", problems,
                        final_record)

    plan = Plan(
        calls=tuple(calls), outputs=tuple(outputs), binding_ledger=(),
        limits=projection["limits"],
        metadata={
            "question": question,
            "intent_binding_hash": final_record.binding_hash(),
            "operation_family": _derive_operation_family(calls),
            "outputs": list(projection["outputs"]),
            "defaults_applied": dict(final_record.defaults),
            "experiment": "E-016",
            "shadow_only": True,
        },
    )
    semantic_metrics = {
        metric_ref: context["sem"]["metric"]
        for metric_ref, context in vocabulary["metric_contexts"].items()
    }
    plan_check = registry.validate_plan(plan, semantic_metrics)
    if plan_check["status"] != "result":
        return {
            **plan_check,
            "binding_record": final_record,
            "binding_hash": final_record.binding_hash(),
        }
    return {
        "status": "result",
        "plan": plan,
        "plan_hash": plan.plan_hash(),
        "binding_record": final_record,
        "binding_hash": final_record.binding_hash(),
        "validation": plan_check,
    }


def _window_of(period):
    """period 형식으로 등록 window를 판별한다 (YYYY-Wnn → iso_week)."""
    return "iso_week" if period and "-W" in period else "month"


def propose_clause_bindings(question, contexts=None, vocabulary=None):
    """Deterministically inventory clauses; validation remains authoritative."""
    contexts = contexts or load_metric_catalog()
    registry = ShadowOperatorRegistry()
    vocabulary = vocabulary or _vocabulary(contexts, registry)
    clauses = []
    protected = []

    def add(match, state, role=None, kind=None, value=None, material=True,
            reason=None, protect=False):
        clauses.append(ClauseBinding(
            clause_id="pending", source_text=match.group(0),
            start=match.start(), end=match.end(), material=material,
            state=state, role=role,
            value=(BindingValue(kind, value) if kind is not None else None),
            reason=reason,
        ))
        if protect:
            protected.append((match.start(), match.end()))

    for pattern, role, reason in UNSUPPORTED_PATTERNS:
        for match in re.finditer(pattern, question):
            if not _overlaps(match.span(), protected):
                add(match, "unsupported", role=role, reason=reason, protect=True)

    for match in re.finditer(r"(?<![0-9])([0-9]{1,2})월", question):
        if not 1 <= int(match.group(1)) <= 12 and not _overlaps(match.span(), protected):
            add(match, "ambiguous", role="time.target",
                reason="month must be between 1 and 12", protect=True)

    week_matches = list(re.finditer(
        r"(?:(20\d{2})-)?W(\d{1,2})(?:\s*(대비))?|(\d{1,2})주차(?:\s*(대비))?",
        question))
    default_year = _default_as_of(contexts)[:4]
    usable_weeks = [match for match in week_matches
                    if not _overlaps(match.span(), protected)]
    for index, match in enumerate(usable_weeks):
        week_number = int(match.group(2) or match.group(4))
        if not 1 <= week_number <= 53:
            add(match, "ambiguous", role="time.target",
                reason="ISO week must be between 1 and 53", protect=True)
            continue
        year = match.group(1) or default_year
        period = f"{year}-W{week_number:02d}"
        marked_baseline = bool(match.group(3) or match.group(5))
        later = (usable_weeks[index + 1]
                 if index + 1 < len(usable_weeks) else None)
        between = question[match.end():later.start()] if later else ""
        role = ("time.baseline"
                if marked_baseline or (later and "대비" in between)
                else "time.target")
        add(match, "consumed", role=role, kind="month", value=period,
            protect=True)

    time_matches = list(re.finditer(
        r"(?<![0-9])(?:(20\d{2})년\s*)?(1[0-2]|[1-9])월(?:\s*말)?(?:\s*(대비))?",
        question))
    usable_times = [match for match in time_matches
                    if not _overlaps(match.span(), protected)]
    # 연도 문맥 전파 (E-026): 같은 질문에 명시 연도가 정확히 하나면 연도 없는
    # 월에도 그 연도를 적용한다. 복수의 명시 연도 사이의 연도 미상 월은 반문.
    explicit_years = sorted({m.group(1) for m in usable_times if m.group(1)})
    for index, match in enumerate(usable_times):
        if not match.group(1) and len(explicit_years) > 1:
            add(match, "ambiguous", role="time.target",
                reason="복수의 명시 연도 사이에서 연도가 지정되지 않은 월",
                protect=True)
            continue
        year = (match.group(1)
                or (explicit_years[0] if explicit_years else default_year))
        month = f"{year}-{int(match.group(2)):02d}"
        later = usable_times[index + 1] if index + 1 < len(usable_times) else None
        between = question[match.end():later.start()] if later else ""
        trailing = question[match.end():match.end() + 6]
        role = ("time.baseline" if match.group(3) or "대비" in trailing
                or (later and "대비" in between) else "time.target")
        add(match, "consumed", role=role, kind="month", value=month)

    target_month = next((row.value.value for row in clauses
                         if row.role == "time.target" and row.value), None)
    if target_month is not None:
        relative = re.search(r"전월\s*대비", question)
        if relative and not _overlaps(relative.span(), protected):
            add(relative, "consumed", role="time.baseline", kind="month",
                value=shift_month(target_month, -1))
        previous_year = re.search(r"(?:작년|전년)(?:\s*동월)?\s*대비", question)
        if previous_year and not _overlaps(previous_year.span(), protected):
            add(previous_year, "consumed", role="time.baseline", kind="month",
                value=shift_month(target_month, -12))

    metric_spans = []
    for alias, metric_ref in sorted(vocabulary["metric_aliases"].items(),
                                    key=lambda item: (-len(item[0]), item[0])):
        for match in re.finditer(re.escape(alias), question):
            if (_overlaps(match.span(), protected)
                    or _overlaps(match.span(), metric_spans)):
                continue
            add(match, "consumed", role="subject", kind="metric_ref",
                value=metric_ref)
            metric_spans.append(match.span())

    if not metric_spans and re.search(r"실적|이익", question):
        match = re.search(r"실적|이익", question)
        add(match, "ambiguous", role="subject",
            reason="multiple governed metrics match performance")

    for dimension_ref, values in vocabulary["dimension_values"].items():
        for raw in sorted(values, key=lambda item: (-len(item), item)):
            for match in re.finditer(re.escape(raw), question):
                if _overlaps(match.span(), protected):
                    continue
                add(match, "consumed", role="filter", kind="predicate",
                    value={"dimension_ref": dimension_ref, "values": [raw]})

    for pattern, dimension_ref in DIMENSION_ALIASES:
        if dimension_ref not in vocabulary["dimension_refs"]:
            continue
        for match in re.finditer(pattern, question):
            if not _overlaps(match.span(), protected):
                nested_marker = re.search(r"그\s*안에서", question)
                is_nested = nested_marker is not None and match.start() > nested_marker.end()
                add(match, "consumed",
                    role=("nested_breakdown" if is_nested else "breakdown"),
                    kind="dimension_ref", value=dimension_ref)

    nested_marker = re.search(r"그\s*안에서", question)
    if nested_marker and not _overlaps(nested_marker.span(), protected):
        add(nested_marker, "preserved", role="output", kind="output_ref",
            value="selected_segment_scope")
    connector = re.search(r"찾고", question)
    if connector and not _overlaps(connector.span(), protected):
        add(connector, "non_semantic", material=False,
            reason="coordination between requested analytical steps")

    average = re.search(r"평균", question)
    if average and not _overlaps(average.span(), protected):
        add(average, "consumed", role="reducer", kind="reducer_ref",
            value="time_average")

    analysis_match = None
    analysis_value = None
    for pattern, value in ANALYSIS_PATTERNS:
        match = re.search(pattern, question)
        if match and not _overlaps(match.span(), protected):
            analysis_match, analysis_value = match, value
            break
    if analysis_match is None:
        explicit_comparison = re.search(r"대비", question)
        if explicit_comparison and not _overlaps(explicit_comparison.span(), protected):
            analysis_match, analysis_value = explicit_comparison, "delta"
    if analysis_match is not None:
        add(analysis_match, "consumed", role="analysis", kind="analysis_ref",
            value=analysis_value)
    elif "왜 안 좋아" in question:
        match = re.search(r"왜\s*안\s*좋아", question)
        add(match, "ambiguous", role="analysis",
            reason="comparison period and analytical objective are unspecified")

    scenario = re.search(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}(?=.{0,8}(?:계획|예산|목표))",
                         question)
    if scenario and not _overlaps(scenario.span(), protected):
        add(scenario, "consumed", role="scenario", kind="scenario_ref",
            value=scenario.group(0))
    elif analysis_value == "plan":
        plan_word = re.search(r"계획|예산|목표", question)
        add(plan_word, "ambiguous", role="scenario",
            reason="plan comparison requires a pinned scenario vintage")

    ranking = re.search(r"상위\s*(\d+)개|가장\s*큰", question)
    if ranking and not _overlaps(ranking.span(), protected):
        limit = int(ranking.group(1)) if ranking.group(1) else 1
        add(ranking, "consumed", role="ranking", kind="ranking",
            value={"measure": "contribution", "order": "descending",
                   "limit": limit})
    only = re.search(r"만", question)
    if only and ranking and not _overlaps(only.span(), protected):
        add(only, "preserved", role="output", kind="output_ref",
            value="only_ranked")
    show = re.search(r"보여\s*줘|분해해\s*줘", question)
    if show and not _overlaps(show.span(), protected):
        add(show, "preserved", role="output", kind="output_ref", value="result")
    target_level = re.search(r"얼마이고", question)
    if target_level and not _overlaps(target_level.span(), protected):
        add(target_level, "preserved", role="output", kind="output_ref",
            value="target_level")

    return finalize_clause_record(question, clauses, contexts, vocabulary)


def finalize_clause_record(question, clauses, contexts, vocabulary):
    """제안된 절 목록을 결정론적으로 마무리한다 — 제안자(규칙·LLM)와 무관한 정본.

    의미 호환성 강등, 미소비 텍스트의 실토(unaccounted), clause_id 부여,
    defaults 계산은 어느 제안자가 왔든 여기서만 수행된다.
    """
    clauses = _apply_semantic_compatibility(list(clauses), vocabulary)
    clauses.extend(_unaccounted_clauses(question, clauses))
    clauses = tuple(replace(row, clause_id=f"c{index:02d}")
                    for index, row in enumerate(sorted(
                        clauses, key=lambda row: (row.start, row.end, row.role or "")),
                        start=1))

    defaults = {"as_of": _default_as_of(contexts)}
    if not any(row.role == "time.target" and row.state == "consumed"
               for row in clauses):
        defaults["target_period"] = shift_month(defaults["as_of"][:7], -1)
    resolved_analysis = next((row.value.value for row in clauses
                              if row.role == "analysis" and row.value), "level")
    target = next((row.value.value for row in clauses
                   if row.role == "time.target" and row.value),
                  defaults.get("target_period"))
    if (resolved_analysis != "level"
            and resolved_analysis != "plan"
            and target is not None and _window_of(target) == "month"
            and not any(row.role == "time.baseline" and row.state == "consumed"
                        for row in clauses)):
        defaults["baseline_period"] = shift_month(target, -1)
    if (resolved_analysis == "contribution"
            and not any(row.role == "breakdown" and row.state == "consumed"
                        for row in clauses)):
        subject = next((row.value.value for row in clauses
                        if row.role == "subject" and row.value), None)
        context = vocabulary["metric_contexts"].get(subject)
        if context is not None:
            metric = context["sem"]["metric"]
            identities = metric.get("decomposition_identities") or []
            axes = (identities[0].get("dimensions", ()) if identities
                    else tuple(context["sem"]["dimensions"]))
            fixed = {row.value.value["dimension_ref"] for row in clauses
                     if row.role == "filter" and row.value}
            defaults["breakdowns"] = [axis for axis in axes if axis not in fixed]
    return SourceClauseBindingRecord(
        question=question, clauses=clauses, defaults=defaults)


def fidelity_report(questions, contexts=None):
    """Report intent outcomes separately; never hide refusals in one aggregate."""
    rows = []
    for question in questions:
        result = compile_shadow_intent(question, contexts=contexts)
        rows.append({
            "question": question,
            "status": result["status"],
            "operation_family": (
                result["plan"].metadata["operation_family"]
                if result["status"] == "result" else None),
            "silent_substitution": _has_silent_substitution(result),
            "violated": [item["check"] for item in result.get("violated", ())],
        })
    return rows


def _vocabulary(contexts, registry):
    metric_contexts = {}
    metric_aliases = {}
    dimension_values = {}
    metric_dimensions = {}
    for context in contexts:
        sem = context["sem"]
        metric = sem["metric"]
        metric_ref = f"{metric['id']}@v{metric['version']}"
        metric_contexts[metric_ref] = context
        for alias in metric.get("aliases", [metric["name"]]):
            metric_aliases[alias] = metric_ref
        metric_dimensions[metric_ref] = frozenset(sem["dimensions"])
        for name, dimension in sem["dimensions"].items():
            dimension_values.setdefault(name, set()).update(dimension["values"])
    return {
        "metric_refs": frozenset(metric_contexts),
        "metric_contexts": metric_contexts,
        "metric_aliases": metric_aliases,
        "metric_dimensions": metric_dimensions,
        "dimension_refs": frozenset(dimension_values),
        "dimension_values": {name: frozenset(values)
                             for name, values in dimension_values.items()},
        "operator_refs": registry.operator_refs,
    }


def _apply_semantic_compatibility(clauses, vocabulary):
    subjects = [row.value.value for row in clauses
                if row.role == "subject" and row.value and row.state == "consumed"]
    result = []
    for row in clauses:
        if row.state != "consumed":
            result.append(row)
            continue
        if row.role == "reducer" and row.value.value == "time_average":
            result.append(replace(
                row, state="unsupported", value=None,
                reason=("time_average is not admissible for the registered "
                        "monthly point-in-time source")))
            continue
        if row.role == "analysis" and row.value.value == "contribution" and subjects:
            metric_types = {
                vocabulary["metric_contexts"][subject]["sem"]["metric"]["type"]
                for subject in subjects
            }
            if "rate" in metric_types:
                result.append(replace(
                    row, state="unsupported", value=None,
                    reason="registered rate-change decomposition is unavailable"))
                continue
        if row.role in {"filter", "breakdown", "nested_breakdown"} and subjects:
            dimension = (row.value.value.get("dimension_ref")
                         if row.role == "filter" else row.value.value)
            if any(dimension not in vocabulary["metric_dimensions"][subject]
                   for subject in subjects):
                result.append(replace(
                    row, state="unsupported", value=None,
                    reason=f"dimension {dimension} is not registered for every subject"))
                continue
        result.append(row)
    return result


def _project(record, contexts):
    values = {}
    clause_ids = {}
    for row in sorted(record.clauses, key=lambda item: (item.start, item.clause_id)):
        if row.state not in {"consumed", "preserved"}:
            continue
        values.setdefault(row.role, []).append(row.value.value)
        clause_ids.setdefault(row.role, []).append(row.clause_id)
    subjects = tuple(values.get("subject", ()))
    problems = []
    if not subjects:
        problems.append("no governed metric subject")
        return None, problems
    analysis = _one(values, "analysis", "level")
    if analysis not in ANALYSIS_REFS:
        problems.append(f"unsupported analysis projection: {analysis}")
    target = _one(values, "time.target", record.defaults.get("target_period"))
    baseline = _one(values, "time.baseline", record.defaults.get("baseline_period"))
    if analysis not in {"level", "plan"} and baseline is None:
        problems.append("comparison analysis requires a baseline period")
    context_map = _context_map(contexts)
    reducers = {_metric_reducer(context_map[subject]["sem"]["metric"])
                for subject in subjects}
    explicit_reducer = _one(values, "reducer")
    if explicit_reducer is not None:
        reducers = {explicit_reducer}
    if len(reducers) != 1:
        problems.append(f"subjects require incompatible reducers: {sorted(reducers)}")
    if len(subjects) > 1 and analysis != "divergence":
        problems.append("multiple subjects require a registered composition")
    if values.get("ranking") and len(subjects) > 1:
        problems.append("ranking multiple subjects requires explicit composition")
    if problems:
        return None, problems
    scenario = _one(values, "scenario")
    if analysis == "plan" and scenario is None:
        problems.append("plan comparison requires a pinned scenario vintage")
    if analysis != "plan" and scenario is not None:
        problems.append("scenario vintage requires plan comparison")
    if problems:
        return None, problems
    limits = next(iter(context_map.values()))["sem"].get(
        "question_defaults", {}).get("exploration_budget", {})
    return {
        "subjects": subjects,
        "subject_clause_ids": tuple(clause_ids["subject"]),
        "reducer": next(iter(reducers)),
        "target_period": target,
        "baseline_period": baseline,
        "filters": tuple(values.get("filter", ())),
        "breakdowns": tuple(values.get(
            "breakdown", record.defaults.get("breakdowns", ()))),
        "analysis": analysis,
        "ranking": _one(values, "ranking"),
        "nested_breakdown": _one(values, "nested_breakdown"),
        "scenario": scenario,
        "outputs": tuple(values.get("output", ())),
        "as_of": record.defaults["as_of"],
        "limits": limits,
    }, []


def _emit_calls(record, projection):
    scope = {item["dimension_ref"]: item["values"]
             for item in projection["filters"]}
    calls = []
    roots = []
    consumers = {row.clause_id: [] for row in record.clauses}
    target_eval_ids = []
    baseline_eval_ids = []
    comparison_ids = []
    subject_eval_ids = {}
    group_by = list(projection["breakdowns"])

    if projection["analysis"] == "plan":
        for index, subject in enumerate(projection["subjects"], start=1):
            call_id = f"n{index:02d}p"
            calls.append(Call(call_id, "plan_gap@v1", {
                "metric": subject,
                "slice": Slice.from_scope(
                    projection["target_period"], projection["as_of"], scope,
                    window=_window_of(projection["target_period"])),
                "vintage_id": projection["scenario"],
            }))
            target_eval_ids.append(call_id)
            comparison_ids.append(call_id)
            roots.append(Ref(call_id))
        subject_rows = [row for row in record.clauses
                        if row.role == "subject" and row.state == "consumed"]
        for row, call_id in zip(subject_rows, target_eval_ids):
            consumers[row.clause_id] = [f"calls.{call_id}.inputs.metric"]
        for row in record.clauses:
            if row.role == "time.target" and row.state == "consumed":
                consumers[row.clause_id] = [
                    f"calls.{call_id}.inputs.slice" for call_id in target_eval_ids]
            elif row.role == "analysis" and row.state == "consumed":
                consumers[row.clause_id] = [
                    f"calls.{call_id}.operator_ref" for call_id in comparison_ids]
            elif row.role == "scenario" and row.state == "consumed":
                consumers[row.clause_id] = [
                    f"calls.{call_id}.inputs.vintage_id" for call_id in target_eval_ids]
            elif row.role == "filter" and row.state == "consumed":
                consumers[row.clause_id] = [
                    f"calls.{call_id}.inputs.slice.predicates" for call_id in target_eval_ids]
            elif row.role == "output" and row.state in {"consumed", "preserved"}:
                consumers[row.clause_id] = ["plan.metadata.outputs"]
        return calls, roots, consumers

    for index, subject in enumerate(projection["subjects"], start=1):
        axes = (group_by if projection["analysis"] == "contribution" and group_by
                else [None])
        subject_eval_ids[index - 1] = []
        for axis_index, axis in enumerate(axes, start=1):
            suffix = (f"{index:02d}" if len(axes) == 1
                      else f"{index:02d}{axis_index:02d}")
            common = {"metric": subject, "reducer": projection["reducer"]}
            if axis is not None:
                common["group_by"] = [axis]
            elif group_by:
                common["group_by"] = group_by
            if projection["baseline_period"]:
                before_id = f"n{suffix}a"
                before_inputs = dict(common)
                before_inputs["slice"] = Slice.from_scope(
                    projection["baseline_period"], projection["as_of"], scope,
                    window=_window_of(projection["baseline_period"]))
                calls.append(Call(before_id, "evaluate_metric@v1", before_inputs))
                baseline_eval_ids.append(before_id)
                subject_eval_ids[index - 1].append(before_id)
            after_id = (f"n{suffix}b" if projection["baseline_period"]
                        else f"n{suffix}")
            after_inputs = dict(common)
            after_inputs["slice"] = Slice.from_scope(
                projection["target_period"], projection["as_of"], scope,
                window=_window_of(projection["target_period"]))
            calls.append(Call(after_id, "evaluate_metric@v1", after_inputs))
            target_eval_ids.append(after_id)
            subject_eval_ids[index - 1].append(after_id)
            root = Ref(after_id)
            if projection["baseline_period"]:
                compare_id = f"n{suffix}c"
                if projection["analysis"] == "contribution":
                    operator_ref = ("set_transition@v1"
                                    if projection["reducer"] == "distinct"
                                    else "contribution@v1")
                    inputs = {"before": Ref(before_id), "after": Ref(after_id)}
                else:
                    operator_ref = "delta@v1"
                    inputs = {"before": Ref(before_id, "value"),
                              "after": Ref(after_id, "value")}
                calls.append(Call(compare_id, operator_ref, inputs))
                comparison_ids.append(compare_id)
                root = Ref(compare_id)
            roots.append(root)

    if projection["analysis"] == "divergence":
        call_id = "n090"
        calls.append(Call(call_id, "align_metrics@v1", {"metrics": tuple(roots)}))
        comparison_ids = [call_id]
        roots = [Ref(call_id)]
    if projection["ranking"]:
        rank = projection["ranking"]
        call_id = "n091"
        calls.append(Call(call_id, "rank@v1", {
            "input": roots[0], "measure": rank["measure"],
            "order": rank["order"], "limit": rank["limit"],
        }))
        roots = [Ref(call_id)]
    if projection["nested_breakdown"]:
        call_id = "n092"
        calls.append(Call(call_id, "drilldown@v1", {
            "selection": roots[0], "group_by": projection["nested_breakdown"],
        }))
        roots = [Ref(call_id)]
    if "target_level" in projection["outputs"]:
        roots = [*(Ref(call_id) for call_id in target_eval_ids), *roots]

    subject_rows = [row for row in record.clauses
                    if row.role == "subject" and row.state == "consumed"]
    for row, index in zip(subject_rows, range(len(subject_rows))):
        ids = subject_eval_ids[index]
        consumers[row.clause_id] = [f"calls.{call_id}.inputs.metric" for call_id in ids]
    for row in record.clauses:
        if row.state not in {"consumed", "preserved"}:
            continue
        if row.role == "time.target":
            consumers[row.clause_id] = [f"calls.{call_id}.inputs.slice" for call_id in target_eval_ids]
        elif row.role == "time.baseline":
            consumers[row.clause_id] = [f"calls.{call_id}.inputs.slice" for call_id in baseline_eval_ids]
        elif row.role == "reducer":
            consumers[row.clause_id] = [
                f"calls.{call_id}.inputs.reducer"
                for call_id in baseline_eval_ids + target_eval_ids]
        elif row.role == "filter":
            consumers[row.clause_id] = [
                f"calls.{call_id}.inputs.slice.predicates"
                for call_id in baseline_eval_ids + target_eval_ids]
        elif row.role == "breakdown":
            consumers[row.clause_id] = [
                f"calls.{call_id}.inputs.group_by"
                for call_id in baseline_eval_ids + target_eval_ids]
        elif row.role == "analysis":
            consumers[row.clause_id] = [
                f"calls.{call_id}.operator_ref" for call_id in comparison_ids]
        elif row.role == "ranking":
            consumers[row.clause_id] = ["calls.n091"]
        elif row.role == "nested_breakdown":
            consumers[row.clause_id] = ["calls.n092.inputs.group_by"]
        elif row.role == "output":
            consumers[row.clause_id] = [
                "plan.outputs" if row.value.value == "target_level"
                else "plan.metadata.outputs"]
    return calls, roots, consumers


def _unaccounted_clauses(question, clauses):
    covered = [False] * len(question)
    for row in clauses:
        for index in range(row.start, row.end):
            covered[index] = True
    rows = []
    start = None
    for index in range(len(question) + 1):
        occupied = index < len(question) and covered[index]
        if not occupied and start is None:
            start = index
        if (occupied or index == len(question)) and start is not None:
            text = question[start:index]
            normalized = re.sub(r"[\s?!.。，,]", "", text)
            if normalized:
                if len(normalized) <= 2:
                    rows.append(ClauseBinding(
                        "pending", text, start, index, False, "non_semantic",
                        reason="Korean particle or discourse morphology"))
                else:
                    rows.append(ClauseBinding(
                        "pending", text, start, index, True, "unsupported",
                        reason=f"unrecognized analytical language: {normalized}"))
            start = None
    return rows


def _metric_reducer(metric):
    rule = metric.get("properties", {}).get("aggregation_rule")
    return {
        "sum": "sum",
        "ratio_of_sums": "ratio_of_sums",
        "count_distinct": "distinct",
        "non_aggregable": "distinct",
        "semi_additive:last": "time_last",
    }.get(rule, rule or "sum")


def _derive_operation_family(calls):
    """Audit metadata derived from Calls; it is never an execution dispatch."""
    analytical = {call.operator_ref for call in calls
                  if call.operator_ref != "evaluate_metric@v1"}
    if "plan_gap@v1" in analytical:
        return "compare_plan"
    return "explain_change" if analytical else "inspect_level"


def _has_silent_substitution(result):
    """Detect a successful neighboring Plan or a failure that still carries one."""
    if result["status"] != "result":
        return "plan" in result
    record = result["binding_record"]
    if any(row.material and (
            row.state not in {"consumed", "preserved"} or not row.target_refs)
            for row in record.clauses):
        return True
    plan = result["plan"]
    operators = {call.operator_ref for call in plan.calls}
    expected = {
        "level": "evaluate_metric@v1",
        "delta": "delta@v1",
        "contribution": "contribution@v1",
        "divergence": "align_metrics@v1",
        "plan": "plan_gap@v1",
    }
    for row in record.clauses:
        if row.role == "analysis" and row.value:
            acceptable = {expected[row.value.value]}
            if row.value.value == "contribution":
                acceptable.add("set_transition@v1")
            if not acceptable.intersection(operators):
                return True
        if row.role == "subject" and row.value:
            # subject는 어느 Call이든 metric 입력으로 소비하면 유지된 것이다
            # (plan_gap@v1은 evaluate_metric 없이 metric을 직접 소비한다 —
            # E-024에서 발견된 scorer 오탐 수리).
            if not any(call.inputs.get("metric") == row.value.value
                       for call in plan.calls):
                return True
    return False


def _context_map(contexts):
    return {f"{row['sem']['metric']['id']}@v{row['sem']['metric']['version']}": row
            for row in contexts}


def _default_as_of(contexts):
    value = contexts[0]["sem"].get("question_defaults", {}).get("as_of")
    if value is None:
        raise ValueError("governed intent compilation requires an explicit as_of")
    date.fromisoformat(value)
    return value


def _one(values, role, default=None):
    rows = values.get(role, ())
    if len(rows) > 1:
        raise ValueError(f"multiple singleton bindings: {role}")
    return rows[0] if rows else default


def _overlaps(span, spans):
    return any(span[0] < other[1] and other[0] < span[1] for other in spans)


def _failure(status, check, details, record):
    return {
        "status": status,
        "violated": tuple({"check": check, "passed": False, "detail": detail}
                          for detail in details),
        "binding_record": record,
        "binding_hash": record.binding_hash(),
    }
