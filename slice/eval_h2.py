"""H2 raw/advisory/enforced trace packet, collector, scorer and summary."""
import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from engine import run_question


HERE = Path(__file__).parent
EVAL_DIR = HERE.parent / "eval" / "semantic-layer-v1"
CASES_PATH = EVAL_DIR / "cases.json"
CONDITIONS_PATH = EVAL_DIR / "conditions.json"
TRACE_SCHEMA_REF = "schemas/agent-trace-v1.schema.json"


def load_cases():
    return json.loads(CASES_PATH.read_text())


def load_conditions():
    return json.loads(CONDITIONS_PATH.read_text())


def case_by_id(case_id):
    return next((case for case in load_cases() if case["id"] == case_id), None)


def dig(value, path):
    for key in path.split(".") if path else []:
        value = value[key]
    return value


def build_packet(condition, case_id, attempt=1):
    catalog = load_conditions()
    capability = catalog["conditions"].get(condition)
    case = case_by_id(case_id)
    if capability is None:
        raise ValueError(f"미등록 condition: {condition}")
    if case is None:
        raise ValueError(f"미등록 case_id: {case_id}")
    return {
        "experiment_version": catalog["experiment_version"],
        "condition": condition,
        "case": {"id": case["id"], "question": case["question"]},
        "attempt": attempt,
        "capability": capability,
        "output_schema_ref": TRACE_SCHEMA_REF,
        "trace_requirements": {
            "canonical_numeric_unit": "원장 단위 u를 유지하고 표시 단위 변환은 final_answer에서만 수행",
            "access_log": "읽거나 호출한 모든 resource를 기록",
            "reporting": "numeric_claims는 value와 source_ref를 기록; 인과 판정은 causal_claims에 기록",
        },
        "trace_template": {
            "trace_version": "1", "condition": condition, "case_id": case["id"],
            "attempt": attempt, "agent_ref": None, "access_log": ["question"],
            "observation": {
                "resolution": {"envelope_status": None, "reason": None,
                               "metric_id": None, "metric_version": None},
                "binding": {"metric_id": None, "metric_version": None,
                            "operation_family": None, "scope": None,
                            "focal_period": None, "comparison": None},
                "selection": {"selected_operators": [], "rejected_operators": []},
                "execution": {"result_key": None, "result_status": None,
                              "primary_value": None, "values": {},
                              "gates": [], "budget": None},
                "persistence": {"query_spec_hash": None, "metric_ref": None,
                                "input_snapshot_ref": None,
                                "result_provenance_refs": []},
                "reporting": {"report_status": None,
                              "report_envelope_status": None,
                              "lint_passed": None, "numeric_claims": [],
                              "causal_claims": [], "label_violations": []},
            },
            "final_answer": None,
        },
        "normalization_notes": {
            "resolution.envelope_status": (
                "계산 가능한 질의는 spec, 추가 확인이 필요하면 clarify, "
                "지표를 해소할 수 없으면 x1"),
            "binding": "Query Spec 전체가 아니라 template의 여섯 필드만 기록",
            "execution": (
                "질문의 주된 수치 답을 원장 단위로 primary_value에 기록; "
                "result_key와 values는 조건이 제공하는 이름만 사용"),
            "persistence": (
                "metric_ref는 metric ID/version을 알 때 <metric_id>@v<version>; "
                "제공되지 않은 hash와 provenance는 null 또는 빈 배열"),
            "reporting": (
                "raw/advisory의 C2 전용 report_status·report_envelope_status·lint_passed는 null"),
        },
    }


def _binding_from_envelope(envelope):
    spec = envelope["query_spec"]
    return {
        "metric_id": spec["subject"]["metric_id"],
        "metric_version": spec["subject"]["metric_version"],
        "operation_family": spec["intent"]["operation_family"],
        "scope": spec["scope"],
        "focal_period": spec["focal_period"],
        "comparison": spec["comparison"],
    }


def collect_enforced_trace(case, attempt=1, agent_ref="deterministic-engine"):
    envelope, bundle = run_question(case["question"])
    resolution = {
        "envelope_status": envelope["status"],
        "reason": envelope.get("reason"),
        "metric_id": None,
        "metric_version": None,
    }
    binding = None
    if envelope["status"] == "spec":
        binding = _binding_from_envelope(envelope)
        resolution["metric_id"] = binding["metric_id"]
        resolution["metric_version"] = binding["metric_version"]

    record = bundle.get("execution_record") if bundle else None
    selection = {"selected_operators": [], "rejected_operators": []}
    persistence = None
    if record is not None:
        considered = record["operators_considered"]
        selection = {
            "selected_operators": [x["operator"] for x in considered["selected"]],
            "rejected_operators": [x["operator"] for x in considered["runtime_rejected"]],
        }
        result_refs = sorted({value["provenance_ref"] for value in bundle["results"].values()
                              if value.get("provenance_ref")})
        provenance = record["provenance"]
        persistence = {
            "query_spec_hash": record["query_spec_hash"],
            "metric_ref": provenance["metric_ref"],
            "input_snapshot_ref": provenance["input_snapshot_ref"],
            "result_provenance_refs": result_refs,
        }

    execution = None
    expected = case["expect"]
    if bundle is not None and "result_key" in expected:
        result = bundle["results"][expected["result_key"]]
        values = {}
        if "path" in expected:
            values[expected["path"]] = dig(result, expected["path"])
        execution = {
            "result_key": expected["result_key"],
            "result_status": result["status"],
            "primary_value": (None if "path" not in expected else
                              dig(result, expected["path"])),
            "values": values,
            "gates": ([] if record is None else record["gates_passed"]),
            "budget": (None if record is None else record["budget"]),
        }

    reporting = None
    if execution is not None and execution["result_status"] == "result":
        report_envelope, report_bundle = run_question(
            "이 결과를 경영진 메모로 작성해줘", report_context=bundle)
        report = report_bundle["results"]["report"]
        lint = report_bundle["results"]["lint"]
        reporting = {
            "report_status": report["status"],
            "lint_passed": lint["passed"],
            "numeric_claims": [
                {"value": claim["value"], "source_ref": claim["source_ref"]}
                for claim in report.get("claims", []) if "value" in claim
            ],
            "causal_claims": [
                violation["detail"] for violation in lint["violations"]
                if violation["rule"] == "CAU01"
            ],
            "label_violations": [
                violation["detail"] for violation in lint["violations"]
                if violation["rule"] == "LBL01"
            ],
            "report_envelope_status": report_envelope["status"],
        }

    return {
        "trace_version": "1", "condition": "enforced",
        "case_id": case["id"], "attempt": attempt, "agent_ref": agent_ref,
        "access_log": ["question", "engine.run_question", "result_envelope"],
        "observation": {
            "resolution": resolution, "binding": binding, "selection": selection,
            "execution": execution, "persistence": persistence, "reporting": reporting,
        },
        "final_answer": None,
    }


def _stage(status, checks=None):
    return {"status": status, "checks": checks or []}


def _check(field, got, expected):
    return {"field": field, "passed": got == expected, "got": got, "expected": expected}


def _normalized_result_status(value, condition):
    if condition in {"raw", "advisory"}:
        aliases = {"success": "result", "succeeded": "result",
                   "computed": "result", "completed": "result"}
        return aliases.get(value, value)
    return value


def _normalized_operator(value):
    return re.sub(r"@v\d+$", "", value)


def _prohibited_causal_verdicts(claims):
    prohibited = []
    for claim in claims:
        text = claim if isinstance(claim, str) else claim.get("claim", "")
        if not re.search(r"때문|원인|기인|초래|야기|탓", text):
            continue
        if re.search(r"확정할 수 없|판정할 수 없|특정할 수 없|정합|시사|가능", text):
            continue
        prohibited.append(claim)
    return prohibited


def _resource_matches(resource, declared):
    return resource == declared or (declared.endswith("/") and resource.startswith(declared))


def _score_capability(trace, condition):
    allowed = condition["allowed_resources"]
    prohibited = condition["prohibited_resources"]
    violations = []
    for resource in trace.get("access_log", []):
        if any(_resource_matches(resource, p) for p in prohibited):
            violations.append(f"prohibited:{resource}")
        elif not any(_resource_matches(resource, a) for a in allowed):
            violations.append(f"undeclared:{resource}")
    return {"passed": not violations, "violations": violations}


def _invalid_trace_stages(case):
    if case is None:
        return {}
    expected = case["expect"]
    failure = lambda name: _stage(
        "fail", [{"field": name, "passed": False,
                  "got": "invalid_trace", "expected": "valid agent-trace-v1"}])
    return {
        "resolution": failure("resolution"),
        "binding": failure("binding") if "spec" in expected else _stage("not_applicable"),
        "selection": failure("selection") if "selection" in expected else _stage("not_applicable"),
        "execution": failure("execution") if "result_key" in expected else _stage("not_applicable"),
        "persistence": (failure("persistence") if "persistence_required" in expected
                        else _stage("not_applicable")),
        "reporting": (failure("reporting") if expected.get("result_status") == "result"
                      else _stage("not_applicable")),
    }


def score_trace(trace):
    required = {"trace_version", "condition", "case_id", "attempt", "access_log", "observation"}
    missing = sorted(required - set(trace))
    case = case_by_id(trace.get("case_id"))
    conditions = load_conditions()["conditions"]
    condition = conditions.get(trace.get("condition"))
    if missing or case is None or condition is None or trace.get("trace_version") != "1":
        nested = trace.get("trace_template", {})
        if not isinstance(nested, dict):
            nested = {}
        inferred_condition = trace.get("condition") or nested.get("condition")
        inferred_case_id = trace.get("case_id") or nested.get("case_id")
        inferred_case = case_by_id(inferred_case_id)
        return {
            "valid": False,
            "condition": inferred_condition,
            "case_id": inferred_case_id,
            "attempt": trace.get("attempt") or nested.get("attempt"),
            "passed": False,
            "capability": {"passed": True, "violations": []},
            "stages": _invalid_trace_stages(inferred_case),
            "missing": missing,
            "error": "trace 구조, case_id 또는 condition 오류",
        }

    expected = case["expect"]
    observed = trace["observation"]
    stages = {}

    resolution = observed.get("resolution") or {}
    checks = [_check("envelope_status", resolution.get("envelope_status"),
                     expected["envelope_status"])]
    if "reason" in expected:
        if trace["condition"] == "enforced":
            checks.append(_check("reason", resolution.get("reason"), expected["reason"]))
        else:
            checks.append({"field": "reason", "passed": bool(resolution.get("reason")),
                           "got": resolution.get("reason"), "expected": "non-empty"})
    if "spec" in expected:
        checks.extend([
            _check("metric_id", resolution.get("metric_id"), expected["spec"]["metric_id"]),
            _check("metric_version", resolution.get("metric_version"),
                   expected["spec"]["metric_version"]),
        ])
    stages["resolution"] = _stage("pass" if all(c["passed"] for c in checks) else "fail", checks)

    if "spec" not in expected:
        stages["binding"] = _stage("not_applicable")
    elif observed.get("binding") is None:
        stages["binding"] = _stage("fail", [_check("binding", None, expected["spec"])])
    else:
        checks = [_check(field, observed["binding"].get(field), value)
                  for field, value in expected["spec"].items()]
        stages["binding"] = _stage("pass" if all(c["passed"] for c in checks) else "fail", checks)

    if "selection" not in expected:
        stages["selection"] = _stage("not_applicable")
    else:
        got_selected_raw = observed.get("selection", {}).get("selected_operators", [])
        got_rejected_raw = observed.get("selection", {}).get("rejected_operators", [])
        got_selected = [_normalized_operator(value) for value in got_selected_raw]
        got_rejected = [_normalized_operator(value) for value in got_rejected_raw]
        checks = []
        for operator in expected["selection"]["must_include"]:
            checks.append({"field": f"selected:{operator}", "passed": operator in got_selected,
                           "got": got_selected, "expected": "included"})
        for operator in expected["selection"]["must_exclude"]:
            checks.append({"field": f"excluded:{operator}",
                           "passed": operator not in got_selected and operator in got_rejected,
                           "got": {"selected": got_selected, "rejected": got_rejected},
                           "expected": "not selected and rejection recorded"})
        stages["selection"] = _stage("pass" if all(c["passed"] for c in checks) else "fail", checks)

    if "result_key" not in expected:
        stages["execution"] = _stage("not_applicable")
    elif observed.get("execution") is None:
        stages["execution"] = _stage("fail", [_check("execution", None, expected["result_key"])])
    else:
        execution = observed["execution"]
        result_status = _normalized_result_status(
            execution.get("result_status"), trace["condition"])
        checks = [_check("result_status", result_status, expected["result_status"])]
        if trace["condition"] == "enforced":
            checks.insert(0, _check("result_key", execution.get("result_key"),
                                    expected["result_key"]))
            if "path" in expected:
                checks.append(_check(
                    expected["path"], execution.get("values", {}).get(expected["path"]),
                    expected["value"]))
        elif "value" in expected:
            checks.append(_check("primary_value", execution.get("primary_value"),
                                 expected["value"]))
        stages["execution"] = _stage("pass" if all(c["passed"] for c in checks) else "fail", checks)

    if "persistence_required" not in expected:
        stages["persistence"] = _stage("not_applicable")
    elif expected["persistence_required"]:
        persistence = observed.get("persistence") or {}
        metric_ref = f"{expected['spec']['metric_id']}@v{expected['spec']['metric_version']}"
        checks = [
            {"field": "query_spec_hash", "passed": bool(persistence.get("query_spec_hash")),
             "got": persistence.get("query_spec_hash"), "expected": "non-empty"},
            _check("metric_ref", persistence.get("metric_ref"), metric_ref),
            {"field": "input_snapshot_ref", "passed": bool(persistence.get("input_snapshot_ref")),
             "got": persistence.get("input_snapshot_ref"), "expected": "non-empty"},
            {"field": "result_provenance_refs",
             "passed": bool(persistence.get("result_provenance_refs")),
             "got": persistence.get("result_provenance_refs"), "expected": "non-empty"},
        ]
        stages["persistence"] = _stage("pass" if all(c["passed"] for c in checks) else "fail", checks)
    else:
        checks = [_check("persistence", observed.get("persistence"), None)]
        stages["persistence"] = _stage("pass" if checks[0]["passed"] else "fail", checks)

    reporting = observed.get("reporting")
    reporting_applicable = expected.get("result_status") == "result"
    if not reporting_applicable:
        stages["reporting"] = _stage("not_applicable")
    elif reporting is None:
        stages["reporting"] = _stage("not_observed")
    else:
        claims = reporting.get("numeric_claims", [])
        checks = []
        if trace["condition"] == "enforced":
            checks.extend([
                _check("report_status", reporting.get("report_status"), "result"),
                _check("report_envelope_status", reporting.get("report_envelope_status"), "spec"),
                _check("lint_passed", reporting.get("lint_passed"), True),
            ])
        checks.append(
            {"field": "numeric_sources",
             "passed": bool(claims) and all(c.get("source_ref") for c in claims),
             "got": claims, "expected": "every numeric claim has source_ref"})
        if "value" in expected:
            checks.append({"field": "expected_numeric_claim",
                           "passed": any(c.get("value") == expected["value"] for c in claims),
                           "got": [c.get("value") for c in claims], "expected": expected["value"]})
        checks.extend([
            _check("prohibited_causal_verdicts",
                   _prohibited_causal_verdicts(reporting.get("causal_claims", [])), []),
            _check("label_violations", reporting.get("label_violations", []), []),
        ])
        stages["reporting"] = _stage("pass" if all(c["passed"] for c in checks) else "fail", checks)

    capability = _score_capability(trace, condition)
    evaluated = [stage for stage in stages.values()
                 if stage["status"] in {"pass", "fail"}]
    observed_count = sum(stage["status"] != "not_observed" for stage in evaluated)
    return {
        "valid": True, "condition": trace["condition"], "case_id": trace["case_id"],
        "attempt": trace["attempt"], "capability": capability, "stages": stages,
        "passed": capability["passed"] and all(s["status"] == "pass" for s in evaluated),
        "reporting_observed": stages["reporting"]["status"] != "not_observed",
        "observed_stage_count": observed_count,
    }


def summarize(scored):
    summary = {}
    for condition in ("raw", "advisory", "enforced"):
        rows = [row for row in scored if row.get("condition") == condition]
        valid_rows = [row for row in rows if row.get("valid")]
        stage_counts = defaultdict(lambda: {"pass": 0, "fail": 0,
                                            "not_observed": 0, "not_applicable": 0})
        stage_failures = defaultdict(list)
        for row in rows:
            for name, stage in row["stages"].items():
                stage_counts[name][stage["status"]] += 1
                if stage["status"] == "fail":
                    stage_failures[name].append(
                        f"{row['case_id']}#{row['attempt']}")
        summary[condition] = {
            "traces": len(rows),
            "valid_traces": len(valid_rows),
            "invalid_traces": len(rows) - len(valid_rows),
            "passed": sum(row.get("valid") and row.get("passed") for row in rows),
            "capability_violations": sum(
                not row["capability"]["passed"] for row in rows),
            "stages": dict(stage_counts),
            "stage_failures": {name: sorted(case_ids)
                               for name, case_ids in stage_failures.items()},
            "invalid_trace_ids": sorted(
                f"{row.get('case_id') or 'unknown'}#{row.get('attempt') or 'unknown'}"
                for row in rows if not row.get("valid")),
        }
    return summary


def _exact_mcnemar(improved, regressed):
    discordant = improved + regressed
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, k)
               for k in range(min(improved, regressed) + 1))
    return min(1.0, 2 * tail / (2 ** discordant))


def compare_paired(scored, baseline="raw", treatment="advisory"):
    indexed = {
        (row.get("condition"), row.get("case_id"), row.get("attempt")): row
        for row in scored
        if row.get("condition") in {baseline, treatment}
        and row.get("case_id") is not None and row.get("attempt") is not None
    }
    identities = sorted({(case_id, attempt)
                         for condition, case_id, attempt in indexed
                         if condition == baseline}
                        & {(case_id, attempt)
                           for condition, case_id, attempt in indexed
                           if condition == treatment})

    def comparison_for(values):
        both_pass = both_fail = improved = regressed = 0
        for baseline_pass, treatment_pass in values:
            if baseline_pass and treatment_pass:
                both_pass += 1
            elif not baseline_pass and not treatment_pass:
                both_fail += 1
            elif treatment_pass:
                improved += 1
            else:
                regressed += 1
        return {
            "pairs": len(values), "both_pass": both_pass, "both_fail": both_fail,
            "improved": improved, "regressed": regressed,
            "net_improved": improved - regressed,
            "mcnemar_exact_two_sided_p": _exact_mcnemar(improved, regressed),
        }

    fully_passed = comparison_for([
        (bool(indexed[(baseline, *identity)].get("valid")
              and indexed[(baseline, *identity)].get("passed")),
         bool(indexed[(treatment, *identity)].get("valid")
              and indexed[(treatment, *identity)].get("passed")))
        for identity in identities
    ])

    stages = {}
    stage_names = sorted({name for row in scored if row.get("valid")
                          for name in row.get("stages", {})})
    for stage_name in stage_names:
        values = []
        excluded = 0
        for identity in identities:
            baseline_row = indexed[(baseline, *identity)]
            treatment_row = indexed[(treatment, *identity)]
            if (stage_name not in baseline_row.get("stages", {})
                    or stage_name not in treatment_row.get("stages", {})):
                excluded += 1
                continue
            baseline_status = baseline_row["stages"][stage_name]["status"]
            treatment_status = treatment_row["stages"][stage_name]["status"]
            if baseline_status not in {"pass", "fail"} or treatment_status not in {"pass", "fail"}:
                continue
            values.append((baseline_status == "pass", treatment_status == "pass"))
        stages[stage_name] = comparison_for(values)
        stages[stage_name]["excluded_invalid_pairs"] = excluded

    return {
        "baseline": baseline, "treatment": treatment,
        "matched_pairs": len(identities),
        "fully_passed": fully_passed,
        "stages": stages,
    }


def _trace_paths(traces_dir):
    return sorted(
        path for path in Path(traces_dir).rglob("*.json")
        if not path.name.endswith((".score.json", ".audit.json"))
        and path.name != "batch-summary.json"
    )


def _write_scores(traces_dir):
    rows = []
    for path in _trace_paths(traces_dir):
        scored = score_trace(json.loads(path.read_text()))
        score_path = path.with_name(f"{path.stem}.score.json")
        score_path.write_text(json.dumps(scored, ensure_ascii=False, indent=2))
        rows.append(scored)
    return rows


def _write_enforced_traces(out_dir, attempt):
    out_dir.mkdir(parents=True, exist_ok=True)
    for case in load_cases():
        trace = collect_enforced_trace(case, attempt=attempt)
        path = out_dir / f"{case['id']}__{attempt:02d}.json"
        path.write_text(json.dumps(trace, ensure_ascii=False, indent=2))
        print(path)


def _write_packets(out_dir, conditions=None, attempts=None):
    catalog = load_conditions()
    selected = conditions or list(catalog["conditions"])
    repeats = attempts or catalog["target_attempts_per_case"]
    paths = []
    for condition in selected:
        if condition not in catalog["conditions"]:
            raise ValueError(f"미등록 condition: {condition}")
        condition_dir = out_dir / condition
        condition_dir.mkdir(parents=True, exist_ok=True)
        for case in load_cases():
            for attempt in range(1, repeats + 1):
                packet = build_packet(condition, case["id"], attempt)
                path = condition_dir / f"{case['id']}__{attempt:02d}.json"
                path.write_text(json.dumps(packet, ensure_ascii=False, indent=2))
                paths.append(path)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    packet = sub.add_parser("packet")
    packet.add_argument("--condition", required=True)
    packet.add_argument("--case-id", required=True)
    packet.add_argument("--attempt", type=int, default=1)
    collect = sub.add_parser("collect-enforced")
    collect.add_argument("--out-dir", required=True)
    collect.add_argument("--attempt", type=int, default=1)
    prepare = sub.add_parser("prepare-batch")
    prepare.add_argument("--out-dir", required=True)
    prepare.add_argument("--condition", action="append",
                         choices=["raw", "advisory", "enforced"])
    prepare.add_argument("--attempts", type=int)
    score = sub.add_parser("score")
    score.add_argument("trace", nargs="+")
    summary_parser = sub.add_parser("summary")
    summary_parser.add_argument("--traces-dir", required=True)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("--traces-dir", required=True)
    rescore_parser = sub.add_parser("rescore")
    rescore_parser.add_argument("--traces-dir", required=True)
    args = parser.parse_args(argv)

    if args.command == "packet":
        print(json.dumps(build_packet(args.condition, args.case_id, args.attempt),
                         ensure_ascii=False, indent=2))
        return 0
    if args.command == "collect-enforced":
        _write_enforced_traces(Path(args.out_dir), args.attempt)
        return 0
    if args.command == "prepare-batch":
        paths = _write_packets(Path(args.out_dir), args.condition, args.attempts)
        print(json.dumps({"out_dir": args.out_dir, "packets": len(paths)},
                         ensure_ascii=False, indent=2))
        return 0
    if args.command == "rescore":
        rescored = _write_scores(args.traces_dir)
        print(json.dumps(summarize(rescored), ensure_ascii=False, indent=2))
        return 0

    paths = ([Path(p) for p in args.trace] if args.command == "score" else
             _trace_paths(args.traces_dir))
    scored = [score_trace(json.loads(path.read_text())) for path in paths]
    if args.command == "score":
        payload = scored
    elif args.command == "compare":
        payload = compare_paired(scored)
    else:
        payload = summarize(scored)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.command == "compare":
        return 0
    return 0 if all(row.get("valid") and row.get("passed") for row in scored) else 1


if __name__ == "__main__":
    raise SystemExit(main())
