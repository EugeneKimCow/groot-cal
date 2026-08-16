"""Golden set v1의 현재 실행 가능 사례를 검증한다.

challenge/planned 사례는 목표 계약으로 보존하되 통과 수치에 포함하지 않는다.
"""
import json
from pathlib import Path

from engine import run_question
from result_catalog import ResultCatalog
from result_store import materialize_result


HERE = Path(__file__).parent
CASES = HERE.parent / "eval" / "golden-set-v1" / "cases.json"


def dig(value, path):
    for key in path.split("."):
        value = value[key]
    return value


def evaluate_assertion(assertion, context):
    if "path" in assertion:
        got = dig(context, assertion["path"])
        label = assertion["path"]
    else:
        result = context["bundle"]["results"][assertion["result"]]
        row = next((r for r in result["segments"]
                    if r["segment"] == assertion["segment"]), None)
        got = None if row is None else row.get(assertion["field"])
        label = f"{assertion['result']}[{assertion['segment']}].{assertion['field']}"

    if "contains" in assertion:
        expected = assertion["contains"]
        passed = expected in got
    else:
        expected = assertion["equals"]
        passed = got == expected
    return {"field": label, "passed": passed, "got": got, "expected": expected}


def run_case(case):
    result_catalog = None
    report_context = None
    setup = case.get("setup")
    if setup and "materialize_question" in setup:
        _, prior_bundle = run_question(setup["materialize_question"])
        stored = materialize_result(
            prior_bundle, setup["result_key"], created_at="2026-08-14T00:00:00Z")
        result_catalog = ResultCatalog()
        result_catalog.add(stored, aliases=["latest"])
    if setup and "report_question" in setup:
        _, report_context = run_question(setup["report_question"])
    envelope, bundle = run_question(
        case["question"], result_catalog=result_catalog, report_context=report_context,
        report_result_key=(setup or {}).get("report_result_key"))
    context = {"envelope": envelope}
    if bundle is not None:
        context["bundle"] = bundle
    return [evaluate_assertion(a, context) for a in case["assertions"]]


def main():
    catalog = json.loads(CASES.read_text())
    ready = [c for c in catalog["cases"] if c["maturity"] == "ready"]
    deferred = [c for c in catalog["cases"] if c["maturity"] != "ready"]
    passed_count = 0
    for case in ready:
        checks = run_case(case)
        passed = all(c["passed"] for c in checks)
        passed_count += passed
        print(f"{'✓' if passed else '✗'} {case['id']}")
        for check in checks:
            if not check["passed"]:
                print(f"  {check['field']}: {check['got']} != {check['expected']}")

    by_maturity = {name: sum(c["maturity"] == name for c in deferred)
                   for name in ("challenge", "planned")}
    print(f"\nready: {passed_count}/{len(ready)} passed")
    print(f"deferred: challenge={by_maturity['challenge']}, planned={by_maturity['planned']}")
    return 0 if passed_count == len(ready) else 1


if __name__ == "__main__":
    raise SystemExit(main())
