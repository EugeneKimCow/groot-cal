"""Metric/result catalog 해소부터 실행 profile 선택까지의 공개 진입점."""
import re

from catalog import context_by_metric_ref, resolve_metric
from interpret import interpret
from pipeline import _input_hash, execute_query
from result_store import assess_staleness
from reporter import (build_report_spec, create_structured_report,
                      lint_structured_report)
from typed_pipeline import execute_typed_query


def prepare_question(question, contexts=None):
    context, resolution = resolve_metric(question, contexts)
    if resolution is not None:
        return resolution, None
    return interpret(question, context["sem"]), context


def _run_staleness_question(question, result_catalog, contexts=None, result_ref="latest"):
    if result_catalog is None:
        return ({"status": "clarify", "reason": "결과 참조 미확정",
                 "message": "어느 분석 결과를 확인할까요? result_id 또는 직전 결과 context가 필요합니다."},
                None)
    stored = result_catalog.resolve(result_ref)
    if stored is None:
        return ({"status": "clarify", "reason": "결과 참조 미확정",
                 "message": f"결과 참조를 찾지 못했습니다: {result_ref}"}, None)
    context = context_by_metric_ref(stored["metric_ref"], contexts)
    current_ref = None if context is None else f"sha256:{_input_hash(context['rows'])}"
    assessment = assess_staleness(stored, current_input_snapshot_ref=current_ref)
    envelope = {
        "status": "spec", "question": question,
        "result_query_spec": {"spec_version": "1", "intent": "inspect_staleness",
                              "result_ref": stored["result_id"]},
        "echo": f"이렇게 이해했습니다 — 저장 결과 {stored['result_id']}의 최신성 확인",
    }
    bundle = {
        "spec": envelope, "results": {"staleness": assessment},
        "execution_record": {
            "provenance": {"stored_result_ref": stored["result_id"],
                           "stored_input_snapshot_ref": stored["input_snapshot_ref"],
                           "current_input_snapshot_ref": current_ref}},
        "assumption_ledger": [], "external_reference_check": None,
    }
    return envelope, bundle


def run_question(question, contexts=None, result_catalog=None, result_ref="latest",
                 report_context=None, report_result_key=None,
                 report_genre="executive_memo"):
    if re.search(r"(경영진|CFO|임원).{0,8}(메모|보고서)|메모로 작성", question):
        if report_context is None:
            return ({"status": "clarify", "reason": "보고 결과 미확정",
                     "message": "어느 분석 결과를 메모로 작성할까요?"}, None)
        report_spec = build_report_spec(
            report_context, genre=report_genre, result_key=report_result_key)
        report = create_structured_report(report_context, report_spec=report_spec)
        lint = (lint_structured_report(report, report_context)
                if report["status"] == "result" else None)
        envelope = {"status": "spec", "question": question,
                    "report_spec": report_spec,
                    "echo": "이렇게 이해했습니다 — 직전 Result Envelope의 경영진 메모 작성"}
        return envelope, {"spec": envelope, "results": {"report": report, "lint": lint},
                          "execution_record": None, "assumption_ledger": [],
                          "external_reference_check": None}
    if re.search(r"(이|해당|저장된).{0,8}(분석 )?결과.{0,8}(유효|최신|오래|stale)", question):
        return _run_staleness_question(
            question, result_catalog, contexts=contexts, result_ref=result_ref)
    envelope, context = prepare_question(question, contexts)
    if envelope["status"] != "spec":
        return envelope, None
    if context["execution_profile"] == "commerce_extensions":
        bundle = execute_query(envelope, context["sem"], context["rows"])
    elif context["execution_profile"] == "typed_core":
        bundle = execute_typed_query(
            envelope, context["sem"], context["rows"], context["source_ref"])
    else:
        raise ValueError(f"지원하지 않는 execution profile: {context['execution_profile']}")
    return envelope, bundle
