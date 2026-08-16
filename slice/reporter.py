"""Report Spec v1 기반 Result Envelope 전용 reporter와 구조 lint."""
import re

from result_adapter import (adapt_result, claim_ceiling,
                            label_within_ceiling)


REPORT_VERSION = "1"
SUPPORTED_GENRES = {"executive_memo"}
ALLOWED_LABELS = {"데이터 확인", "데이터 시사", "컨설턴트 판단", "참고치"}
EXECUTIVE_REQUIRED_SLOTS = [
    "header_meta", "headline_verdict", "reassurance_signal",
    "decomposition_where", "cause_mapping_why", "ambiguity_block",
    "watchpoints_validation", "followup_actions", "source_basis_footer",
]
ALL_SLOTS = [
    "header_meta", "headline_verdict", "reassurance_signal",
    "decomposition_where", "volume_rate_decomp", "cause_mapping_why",
    "ambiguity_block", "rejected_alternatives", "offset_positive", "plan_gap",
    "watchpoints_validation", "followup_actions", "recommendations",
    "verification_appendix", "source_basis_footer",
]


def _dig(value, path):
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def _format(value, unit, signed=False):
    sign = "+" if signed else ""
    if unit == "ratio":
        return f"{value * 100:{sign}.1f}%"
    if unit == "percent":
        return f"{value:{sign}.1f}%"
    if unit == "0.1억원(u)" or unit is None:
        return f"{value * 0.1:{sign}.1f}억원"
    return f"{value:{sign}g}{unit}"


def _dominance_score(result, result_key):
    adapted = adapt_result(result, result_key)
    if adapted["status"] != "result":
        return 0
    change = adapted["view"].get("change")
    if change is None:
        return 0
    if change["segments"]:
        return max(abs(row["value"]) for row in change["segments"])
    return abs(change["value"])


def _candidate_results(bundle):
    return {
        key: result for key, result in (bundle.get("results") or {}).items()
        if result.get("status") == "result" and key != "events"
    }


def select_report_result(bundle, result_key=None):
    candidates = _candidate_results(bundle)
    if result_key is not None:
        result = candidates.get(result_key)
        if result is None:
            return None, f"정상 결과에서 result_key를 찾지 못함: {result_key}"
        return result_key, "explicit_result_key"

    family = (((bundle.get("spec") or {}).get("query_spec") or {})
              .get("intent", {}).get("operation_family"))
    preferred = {"inspect_level": "level", "compare_plan": "plan_gap"}.get(family)
    if preferred in candidates:
        return preferred, f"operation_family={family}"

    if family == "explain_change":
        top_level = {
            key: result for key, result in candidates.items()
            if (key.startswith("contrib:") or key.startswith("distinct:"))
            and not key.startswith("drill:")
        }
        if top_level:
            selected = min(
                top_level,
                key=lambda key: (-_dominance_score(top_level[key], key), key),
            )
            return selected, "largest_absolute_segment_contribution"

    if len(candidates) == 1:
        return next(iter(candidates)), "only_normal_result"
    if not candidates:
        return None, "정상 operator result 없음"
    return None, f"결과 선택 모호: {sorted(candidates)}"


def build_report_spec(bundle, genre="executive_memo", result_key=None):
    return {
        "spec_version": REPORT_VERSION,
        "genre": genre,
        "audience": "executive",
        "language": "ko",
        "result_selector": {
            "mode": "explicit" if result_key is not None else "primary",
            "result_key": result_key,
        },
        "required_slots": list(EXECUTIVE_REQUIRED_SLOTS),
        "input_capability": "result_envelope_only",
    }


def validate_report_spec(report_spec):
    problems = []
    if not isinstance(report_spec, dict):
        return ["Report Spec은 object여야 함"]
    if report_spec.get("spec_version") != REPORT_VERSION:
        problems.append("지원하지 않는 spec_version")
    if report_spec.get("genre") not in SUPPORTED_GENRES:
        problems.append(f"지원하지 않는 genre: {report_spec.get('genre')}")
    if report_spec.get("audience") != "executive":
        problems.append("audience는 executive여야 함")
    if report_spec.get("language") != "ko":
        problems.append("language는 ko여야 함")
    if report_spec.get("input_capability") != "result_envelope_only":
        problems.append("input_capability는 result_envelope_only여야 함")
    selector = report_spec.get("result_selector") or {}
    mode = selector.get("mode")
    result_key = selector.get("result_key")
    if mode not in {"primary", "explicit"}:
        problems.append(f"result_selector mode 오류: {mode}")
    elif mode == "primary" and result_key is not None:
        problems.append("primary selector의 result_key는 null이어야 함")
    elif mode == "explicit" and not isinstance(result_key, str):
        problems.append("explicit selector에는 result_key가 필요")
    if set(report_spec.get("required_slots") or []) != set(EXECUTIVE_REQUIRED_SLOTS):
        problems.append("executive_memo 필수 슬롯 집합 불일치")
    return problems


def _empty_slots():
    return {name: {"status": "not_applicable", "claim_refs": [],
                   "reason": "현재 장르 또는 Result Envelope에서 비대상"}
            for name in ALL_SLOTS}


def _claim(claims, slot, statement_type, text, label, **fields):
    claim_id = f"claim-{len(claims) + 1:03d}"
    row = {
        "claim_id": claim_id, "slot": slot, "statement_type": statement_type,
        "text": text, "label": label, **fields,
    }
    claims.append(row)
    return claim_id


def _set_slot(slots, name, claim_refs=None, **fields):
    slots[name] = {"status": "populated", "claim_refs": claim_refs or [], **fields}


def _header_meta(bundle):
    spec = ((bundle.get("spec") or {}).get("query_spec") or {})
    provenance = ((bundle.get("execution_record") or {}).get("provenance") or {})
    return {
        "as_of": spec.get("as_of") or provenance.get("as_of"),
        "metric_ref": provenance.get("metric_ref"),
        "focal_period": spec.get("focal_period"),
        "comparison": spec.get("comparison"),
        "scope": spec.get("scope", {}),
        "input_snapshot_ref": provenance.get("input_snapshot_ref"),
    }


def _add_primary_claims(bundle, key, result_view, claims, slots):
    scalar = result_view.get("scalar")
    change = result_view.get("change")
    unit = (scalar["unit"] if scalar is not None else
            change["unit"] if change is not None else None)
    headline = []
    decomposition = []
    reassurance = []
    arithmetic_label = claim_ceiling(result_view, "arithmetic")
    fact_label = claim_ceiling(result_view, "fact")

    if scalar is not None:
        source = scalar["source_ref"]
        headline.append(_claim(
            claims, "headline_verdict", "fact",
            f"지표 수준은 {_format(scalar['value'], unit)}으로 확인됩니다.",
            fact_label, value=scalar["value"], unit=unit,
            source_ref=source, result_key=key))
    elif change is not None:
        headline.append(_claim(
            claims, "headline_verdict", "arithmetic",
            f"관측된 변화는 {_format(change['value'], unit, True)}입니다.",
            arithmetic_label, value=change["value"], unit=unit,
            source_ref=change["source_ref"], result_key=key))
        if change["pct_change"] is not None:
            percent = change["pct_change"]
            headline.append(_claim(
                claims, "headline_verdict", "arithmetic",
                f"이전 기간 수준 대비 {_format(percent['value'], 'percent', True)}입니다.",
                arithmetic_label, value=percent["value"], unit="percent",
                source_ref=percent["source_ref"],
                denominator_ref=percent["denominator_ref"],
                result_key=key))

    segments = change["segments"] if change is not None else []
    for index, segment in enumerate(segments[:2]):
        decomposition.append(_claim(
            claims, "decomposition_where", "arithmetic",
            f"{segment['segment']} 기여분은 {_format(segment['value'], unit, True)}입니다.",
            arithmetic_label, value=segment["value"], unit=unit,
            source_ref=segment["source_ref"], result_key=key,
            provenance_ref=result_view.get("provenance_ref")))

    total_delta = change["value"] if change is not None else None
    if total_delta not in (None, 0) and segments:
        opposite = next((index for index, segment in enumerate(segments)
                         if segment["value"] * total_delta < 0), None)
        if opposite is not None:
            segment = segments[opposite]
            reassurance.append(_claim(
                claims, "reassurance_signal", "arithmetic",
                f"상쇄 요인인 {segment['segment']}은 {_format(segment['value'], unit, True)}입니다.",
                arithmetic_label, value=segment["value"], unit=unit,
                source_ref=segment["source_ref"], result_key=key,
                provenance_ref=result_view.get("provenance_ref")))

    _set_slot(slots, "headline_verdict", headline, result_key=key)
    if decomposition:
        _set_slot(slots, "decomposition_where", decomposition,
                  result_keys=[key], identity_required=True)
    if reassurance:
        _set_slot(slots, "reassurance_signal", reassurance)
    else:
        slots["reassurance_signal"] = {
            "status": "not_applicable", "claim_refs": [],
            "reason": "선택 결과에 반대 부호의 상쇄 세그먼트가 없음",
        }


def _add_events(bundle, events_view, claims, slots, actions):
    events_result = (bundle.get("results") or {}).get("events") or {}
    events = events_result.get("events") if events_result.get("status") == "result" else []
    if not events:
        slots["cause_mapping_why"] = {
            "status": "not_applicable", "claim_refs": [],
            "reason": "등록 이벤트 대조 결과 없음",
        }
        slots["watchpoints_validation"] = {
            "status": "not_applicable", "claim_refs": [],
            "reason": "재분류할 이벤트 가설 없음",
        }
        return

    event_claims = []
    event_refs = []
    suggestion_label = claim_ceiling(events_view, "suggestion")
    judgment_label = claim_ceiling(events_view, "judgment")
    for index, event in enumerate(events[:2]):
        ref = f"results.events.events.{index}"
        event_refs.append(ref)
        event_claims.append(_claim(
            claims, "cause_mapping_why", "suggestion",
            f"등록 이벤트 '{event['name']}'는 관측 범위와 정합하지만 원인으로 확정할 수 없습니다.",
            suggestion_label, evidence_refs=[ref],
            evidence_grade=event.get("evidence_grade"), result_key="events"))
        if event.get("declared_magnitude_u") is None:
            actions.append({
                "action_id": f"action-{len(actions) + 1:03d}",
                "purpose": f"{event['name']}의 자사 영향 규모 특정",
                "evidence_refs": [ref], "owner": None, "due_at": None,
                "status": "needs_assignment",
            })
    _set_slot(slots, "cause_mapping_why", event_claims, result_key="events")
    watch_claim = _claim(
        claims, "watchpoints_validation", "judgment",
        "이벤트별 자사 영향 규모가 특정되면 현재 시사 등급을 재분류할 필요가 있습니다.",
        judgment_label, evidence_refs=event_refs)
    _set_slot(slots, "watchpoints_validation", [watch_claim],
              validation_state="awaiting_magnitude")


def _add_ambiguity(bundle, claims, slots, actions):
    ledger = bundle.get("assumption_ledger") or []
    unresolved = [(index, row) for index, row in enumerate(ledger)
                  if row.get("status") != "checked"]
    if not unresolved:
        slots["ambiguity_block"] = {
            "status": "not_applicable", "claim_refs": [],
            "reason": "미검증 가정 없음",
        }
        return
    refs = []
    for index, row in unresolved:
        ref = f"assumption_ledger.{index}"
        refs.append(_claim(
            claims, "ambiguity_block", "meta",
            f"확인 상한은 여기까지입니다: {row['assumption']}은 아직 검증되지 않았습니다.",
            "데이터 확인", evidence_refs=[ref], evidence_grade=row.get("status")))
        actions.append({
            "action_id": f"action-{len(actions) + 1:03d}",
            "purpose": row.get("note") or row["assumption"],
            "evidence_refs": [ref], "owner": None, "due_at": None,
            "status": "needs_assignment",
        })
    _set_slot(slots, "ambiguity_block", refs)


def _add_followups(claims, slots, actions):
    if not actions:
        slots["followup_actions"] = {
            "status": "not_applicable", "claim_refs": [],
            "reason": "Result Envelope에 미해결 데이터 갭 없음",
            "items": [],
        }
        return
    refs = []
    for action in actions:
        refs.append(_claim(
            claims, "followup_actions", "judgment",
            f"후속 확인 항목은 '{action['purpose']}'입니다. 데이터 확보와 담당 지정이 필요합니다.",
            "컨설턴트 판단", evidence_refs=action["evidence_refs"],
            action_ref=action["action_id"]))
    _set_slot(slots, "followup_actions", refs, items=actions)


def _add_source_footer(bundle, claims, slots):
    provenance = ((bundle.get("execution_record") or {}).get("provenance") or {})
    refs = []
    if provenance:
        ref = "execution_record.provenance.input_snapshot_ref"
        refs.append(_claim(
            claims, "source_basis_footer", "meta",
            f"기준 시점 {provenance.get('as_of')}의 입력 스냅샷에 근거한 결과입니다.",
            "데이터 확인", evidence_refs=[ref]))
    comparison = (((bundle.get("spec") or {}).get("query_spec") or {})
                  .get("comparison"))
    if comparison:
        ref = "spec.query_spec.comparison"
        refs.append(_claim(
            claims, "source_basis_footer", "meta",
            f"비교 기준은 {comparison.get('kind')}입니다.",
            "데이터 확인", evidence_refs=[ref]))
    if refs:
        _set_slot(slots, "source_basis_footer", refs)
    else:
        slots["source_basis_footer"] = {
            "status": "suspended", "claim_refs": [],
            "missing_inputs": ["execution provenance", "comparison basis"],
            "pass_conditions": "입력 스냅샷과 비교 기준이 있으면 작성 가능",
        }


def _sections(slots, claims):
    headings = {
        "headline_verdict": "요약", "reassurance_signal": "상쇄·안심 신호",
        "decomposition_where": "정량 분해", "cause_mapping_why": "원인 대조",
        "ambiguity_block": "확인 상한", "watchpoints_validation": "관전 포인트",
        "followup_actions": "후속 행동", "source_basis_footer": "출처와 비교 기준",
    }
    by_id = {claim["claim_id"]: claim for claim in claims}
    rows = []
    for slot in EXECUTIVE_REQUIRED_SLOTS:
        if slot == "header_meta":
            continue
        claim_refs = slots[slot].get("claim_refs", [])
        rows.append({
            "slot": slot, "heading": headings[slot], "claim_refs": claim_refs,
            "sentences": [by_id[ref]["text"] for ref in claim_refs],
            "status": slots[slot]["status"],
        })
    return rows


def create_structured_report(bundle, report_spec=None, result_key=None):
    report_spec = report_spec or build_report_spec(bundle, result_key=result_key)
    problems = validate_report_spec(report_spec)
    if problems:
        return {"status": "out_of_domain", "violated": [
            {"check": "report_spec_valid", "passed": False, "detail": problem}
            for problem in problems
        ]}
    requested_key = result_key
    if requested_key is None:
        requested_key = (report_spec.get("result_selector") or {}).get("result_key")
    key, reason = select_report_result(bundle, requested_key)
    if key is None:
        return {"status": "suspended", "missing_inputs": ["selected result"],
                "pass_conditions": reason, "report_spec": report_spec}

    result = bundle["results"][key]
    adapted = adapt_result(result, key)
    if adapted["status"] != "result":
        return adapted
    result_view = adapted["view"]
    events_view = None
    events_result = (bundle.get("results") or {}).get("events")
    if events_result is not None and events_result.get("status") == "result":
        events_adapted = adapt_result(events_result, "events")
        if events_adapted["status"] != "result":
            return events_adapted
        events_view = events_adapted["view"]
    claims = []
    actions = []
    slots = _empty_slots()
    slots["header_meta"] = {"status": "populated", "claim_refs": [],
                            "value": _header_meta(bundle)}
    _add_primary_claims(bundle, key, result_view, claims, slots)
    _add_events(bundle, events_view, claims, slots, actions)
    _add_ambiguity(bundle, claims, slots, actions)
    _add_followups(claims, slots, actions)
    _add_source_footer(bundle, claims, slots)

    if key == "plan_gap":
        slots["plan_gap"] = {"status": "populated", "claim_refs": [],
                             "result_key": key}
    if key.startswith("vrm:"):
        slots["volume_rate_decomp"] = {
            "status": "populated", "claim_refs": [], "result_key": key}

    return {
        "status": "result", "output_type": "StructuredReport",
        "report_version": REPORT_VERSION, "genre": report_spec["genre"],
        "report_spec": report_spec,
        "selected_result": {
            "result_key": key, "selection_reason": reason,
            "operator_ref": result_view["operator_ref"],
            "provenance_ref": result_view["provenance_ref"],
        },
        "header_meta": slots["header_meta"]["value"],
        "slots": slots, "claims": claims,
        "sections": _sections(slots, claims),
        "capability": {"inputs": ["result_envelope"], "raw_access": False},
    }


def _prohibited_causal_text(text):
    if not re.search(r"때문|원인|기인|초래|야기|탓", text):
        return False
    return not re.search(r"확정할 수 없|판정할 수 없|특정할 수 없|정합|시사|가능", text)


def _violation(rule, detail):
    return {"rule": rule, "detail": detail}


def lint_structured_report(report, bundle):
    violations = []
    warnings = []
    if report.get("capability") != {"inputs": ["result_envelope"], "raw_access": False}:
        violations.append(_violation("CAP01", "Result Envelope 전용 capability 위반"))
    if report.get("report_version") != REPORT_VERSION:
        violations.append(_violation("SPEC01", "report_version 오류"))
    report_spec = report.get("report_spec") or {}
    for problem in validate_report_spec(report_spec):
        violations.append(_violation("SPEC01", problem))

    slots = report.get("slots") or {}
    required_slots = report_spec.get("required_slots") or []
    for slot_name in required_slots:
        slot = slots.get(slot_name)
        if slot is None:
            violations.append(_violation("SLOT01", f"필수 슬롯 누락: {slot_name}"))
        elif slot.get("status") not in {"populated", "not_applicable", "suspended"}:
            violations.append(_violation("SLOT01", f"슬롯 상태 오류: {slot_name}"))
        elif slot.get("status") == "suspended" and not (
                slot.get("missing_inputs") and slot.get("pass_conditions")):
            violations.append(_violation("SLOT01", f"보류 계약 누락: {slot_name}"))

    claims = report.get("claims") or []
    by_id = {}
    normalized_views = {}
    for claim in claims:
        claim_id = claim.get("claim_id")
        if not claim_id or claim_id in by_id:
            violations.append(_violation("REF01", f"claim_id 오류: {claim_id}"))
        else:
            by_id[claim_id] = claim
    for slot_name, slot in slots.items():
        for claim_ref in slot.get("claim_refs", []):
            claim = by_id.get(claim_ref)
            if claim is None or claim.get("slot") != slot_name:
                violations.append(_violation(
                    "REF01", f"슬롯-claim 참조 오류: {slot_name}/{claim_ref}"))

    for claim in claims:
        source = claim.get("source_ref")
        if "value" in claim:
            try:
                source_value = _dig(bundle, source)
            except (KeyError, IndexError, TypeError, ValueError):
                source_value = None
            if source_value != claim.get("value"):
                violations.append(_violation(
                    "SRC01", f"{source}: {claim.get('value')} != {source_value}"))
            if claim.get("unit") == "percent" and not claim.get("denominator_ref"):
                violations.append(_violation("PCT01", f"분모 참조 누락: {claim.get('claim_id')}"))
        for evidence_ref in claim.get("evidence_refs", []):
            try:
                _dig(bundle, evidence_ref)
            except (KeyError, IndexError, TypeError, ValueError):
                violations.append(_violation("EVD01", f"근거 참조 오류: {evidence_ref}"))
        if claim.get("label") not in ALLOWED_LABELS:
            violations.append(_violation("LBL01", str(claim.get("label"))))
        result_key = claim.get("result_key")
        if result_key:
            if result_key not in normalized_views:
                source_result = (bundle.get("results") or {}).get(result_key)
                normalized_views[result_key] = adapt_result(source_result, result_key)
            adapted = normalized_views[result_key]
            if adapted["status"] != "result":
                violations.append(_violation(
                    "LBL02", f"결과 ceiling 해석 실패: {result_key}"))
            else:
                ceiling = claim_ceiling(
                    adapted["view"], claim.get("statement_type"))
                if ceiling is None or not label_within_ceiling(
                        claim.get("label"), ceiling):
                    violations.append(_violation(
                        "LBL02",
                        f"{claim.get('claim_id')}: {claim.get('label')} > {ceiling}"))
        if claim.get("label") in {"데이터 시사", "컨설턴트 판단"} \
                and not claim.get("evidence_refs"):
            violations.append(_violation(
                "EVD01", f"시사·판단 근거 누락: {claim.get('claim_id')}"))
        if _prohibited_causal_text(claim.get("text", "")):
            violations.append(_violation("CAU01", claim.get("text")))

    decomposition = slots.get("decomposition_where") or {}
    if len(set(decomposition.get("result_keys", []))) > 1:
        violations.append(_violation("AXIS01", "서로 다른 분해 축의 수치 혼합"))

    actions = (slots.get("followup_actions") or {}).get("items", [])
    for action in actions:
        if not action.get("owner") or not action.get("due_at"):
            warnings.append(_violation(
                "ACT01", f"담당·기한 지정 필요: {action.get('action_id')}"))

    return {
        "status": "result", "output_type": "ReportLint",
        "passed": not violations, "violations": violations, "warnings": warnings,
        "checked_claims": len(claims), "checked_slots": len(required_slots),
        "label_ceiling": {"lint": "데이터 확인"},
    }
