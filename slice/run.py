"""Query Spec v1 기반 수직 조각 CLI.

기존 `out/bundle.json`은 과거 측정·보고서의 동결 입력이다. 이 러너는 실행 계약 v1의
산출물을 `out/bundle-v1.json`에 기록한다.
"""
import argparse
import json
from pathlib import Path

from engine import run_question
from result_adapter import adapt_result

HERE = Path(__file__).parent


def _format_value(value, unit, signed=False):
    sign = "+" if signed else ""
    if unit == "ratio":
        return f"{value * 100:{sign}.1f}%"
    if unit == "0.1억원(u)" or unit is None:
        return f"{value * 0.1:{sign}.1f}억"
    return f"{value:{sign}g}{unit}"


def _summary(bundle):
    spec = bundle["spec"]
    print(f"질의: {spec.get('question')}")
    print(f"명세 반향: {spec.get('echo')}")
    if bundle["execution_record"] is None:
        for value in bundle["results"].values():
            print(f"query_spec: {value['status']}")
            for item in value.get("violated", []):
                print(f"  - {item['detail']}")
            for item in value.get("missing_inputs", []):
                print(f"  - {item}")
        return
    for name, value in bundle["results"].items():
        suffix = ""
        adapted = adapt_result(value, name)
        scalar = (adapted["view"].get("scalar")
                  if adapted["status"] == "result" else None)
        change = (adapted["view"].get("change")
                  if adapted["status"] == "result" else None)
        if change is not None:
            suffix = f" Δ={_format_value(change['value'], change['unit'], signed=True)}"
        elif scalar is not None:
            suffix = f" value={_format_value(scalar['value'], scalar['unit'])}"
        print(f"{name}: {value['status']}{suffix}")
    budget = bundle["execution_record"]["budget"]
    print("예산: "
          f"depth {budget['consumed_depth']}/{budget['max_depth']}, "
          f"segments {budget['segments_examined']}/{budget['max_segments']}, "
          f"hypotheses {budget['hypotheses_examined']}/{budget['max_hypotheses']}, "
          f"calls {budget['operator_calls']}/{budget['max_operator_calls']}")
    rejected = bundle["execution_record"]["operators_considered"]["runtime_rejected"]
    for item in rejected:
        print(f"제외: {item['operator']} — {item['reason']}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("question", nargs="?", default="7월 매출이 왜 변했나?")
    parser.add_argument("--out", default=str(HERE / "out" / "bundle-v1.json"))
    parser.add_argument(
        "--route", choices=["current", "c4"], default="current",
        help="c4: intent compiler→라우팅된 C4 executor 시연 경로 (기본 경로 무변경)")
    parser.add_argument(
        "--show-plan", action="store_true",
        help="시연 경로에서 컴파일된 Call DAG를 함께 출력")
    args = parser.parse_args(argv)

    if args.route == "c4":
        from demo import demo_question, render_demo
        outcome = demo_question(args.question)
        print(render_demo(outcome, show_plan=args.show_plan))
        return 0 if outcome["stage"] == "executed" and \
            outcome["execution"]["status"] == "result" else 1

    envelope, bundle = run_question(args.question)
    if envelope["status"] != "spec":
        print(f"질의: {args.question}")
        print(f"[{envelope['status'].upper()}] {envelope['message']}")
        return 2

    _summary(bundle)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=1))
    print(f"Evidence Bundle v1 → {out}")
    return 0 if bundle["execution_record"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
