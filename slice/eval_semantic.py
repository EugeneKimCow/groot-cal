"""H2 evaluation의 enforced(C2) 기준선 실행기."""
import json
from pathlib import Path

from interpret import interpret
from kernel import load_ledger, load_semantic
from pipeline import execute_query

HERE = Path(__file__).parent
CASES = HERE.parent / "eval" / "semantic-layer-v1" / "cases.json"


def dig(value, path):
    for key in path.split(".") if path else []:
        value = value[key]
    return value


def run_case(case, sem, ledger):
    envelope = interpret(case["question"], sem)
    expected = case["expect"]
    checks = [{"field": "envelope_status", "passed": envelope["status"] == expected["envelope_status"],
               "got": envelope["status"], "expected": expected["envelope_status"]}]
    if envelope["status"] != "spec":
        if "reason" in expected:
            checks.append({"field": "reason", "passed": envelope.get("reason") == expected["reason"],
                           "got": envelope.get("reason"), "expected": expected["reason"]})
        return checks

    bundle = execute_query(envelope, sem, ledger)
    key = expected["result_key"]
    result = bundle["results"][key]
    checks.append({"field": "result_status", "passed": result["status"] == expected["result_status"],
                   "got": result["status"], "expected": expected["result_status"]})
    if "path" in expected:
        got = dig(result, expected["path"])
        checks.append({"field": expected["path"], "passed": got == expected["value"],
                       "got": got, "expected": expected["value"]})
    return checks


def main():
    sem, ledger = load_semantic(), load_ledger()
    cases = json.loads(CASES.read_text())
    rows = []
    for case in cases:
        checks = run_case(case, sem, ledger)
        passed = all(c["passed"] for c in checks)
        rows.append({"id": case["id"], "passed": passed, "checks": checks})
        print(f"{'✓' if passed else '✗'} {case['id']}")
        for check in checks:
            if not check["passed"]:
                print(f"  {check['field']}: {check['got']} != {check['expected']}")
    total = sum(r["passed"] for r in rows)
    print(f"\nenforced baseline: {total}/{len(rows)} cases passed")
    return 0 if total == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

