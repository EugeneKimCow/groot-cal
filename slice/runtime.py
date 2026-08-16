"""실행 계약 v1 — 등록 확인, 호출 전 예산 강제와 provenance 기록."""
import json
from pathlib import Path


def load_operator_registry():
    return json.loads((Path(__file__).parent / "operator_registry.json").read_text())


class ExecutionRuntime:
    def __init__(self, limits, operation_family, registry=None, metric=None):
        self.registry = registry or load_operator_registry()
        self.operation_family = operation_family
        self.metric = metric
        self.limits = {
            "max_depth": limits["max_depth"],
            "max_segments": limits["max_segments"],
            "max_hypotheses": limits.get("max_hypotheses", 0),
            "max_operator_calls": limits.get("max_operator_calls", 10),
        }
        self.record = {
            "registry_version": self.registry["registry_version"],
            "calls": [],
            "dag": [],
            "gates_passed": [],
            "operators_considered": {"selected": [], "runtime_rejected": []},
            "budget": {
                **self.limits,
                "consumed_depth": 0,
                "segments_examined": 0,
                "hypotheses_examined": 0,
                "operator_calls": 0,
                "on_exhaustion": "stop_and_report",
            },
        }

    def reject(self, operator, reason):
        self.record["operators_considered"]["runtime_rejected"].append(
            {"operator": operator, "reason": reason})

    def execute(self, operator, depth, expected_segments, invoke, expected_hypotheses=0):
        """예산을 선점한 뒤 invoke(record)를 실행한다.

        세그먼트 수는 등록 차원의 cardinality로 호출 전에 보수적으로 계산한다. 실행 후
        실제 출력이 더 크면 contract violation으로 정상 결과를 폐기한다.
        """
        base_operator = operator.split(":", 1)[0]
        contract = self.registry["operators"].get(base_operator)
        if contract is None:
            self.reject(operator, "미등록 연산자")
            return {"status": "out_of_domain",
                    "violated": [{"check": "operator_registered", "passed": False,
                                  "detail": f"미등록 연산자 {base_operator}"}]}
        if self.operation_family not in contract["operation_families"]:
            self.reject(operator, f"{self.operation_family}에 허용되지 않은 연산자")
            return {"status": "out_of_domain",
                    "violated": [{"check": "operator_admissible", "passed": False,
                                  "detail": f"{base_operator} × {self.operation_family}"}]}
        accepted_types = contract.get("metric_types")
        if self.metric is not None and accepted_types is not None \
                and self.metric["type"] not in accepted_types:
            self.reject(operator, f"{self.metric['type']}에 허용되지 않은 연산자")
            return {"status": "out_of_domain",
                    "violated": [{"check": "metric_type_admissible", "passed": False,
                                  "detail": f"{self.metric['type']} not in {accepted_types}"}]}

        budget = self.record["budget"]
        violations = []
        if depth > budget["max_depth"]:
            violations.append(f"depth {depth}>{budget['max_depth']}")
        if budget["operator_calls"] + 1 > budget["max_operator_calls"]:
            violations.append("max_operator_calls 소진")
        if budget["segments_examined"] + expected_segments > budget["max_segments"]:
            violations.append(
                f"segments {budget['segments_examined']}+{expected_segments}>{budget['max_segments']}")
        if budget["hypotheses_examined"] + expected_hypotheses > budget["max_hypotheses"]:
            violations.append(
                f"hypotheses {budget['hypotheses_examined']}+{expected_hypotheses}>"
                f"{budget['max_hypotheses']}")
        if violations:
            self.reject(operator, "; ".join(violations))
            return {"status": "budget_exhausted",
                    "violated": [{"check": "exploration_budget", "passed": False,
                                  "detail": v} for v in violations],
                    "label_ceiling": {"상태": "데이터 확인 — 예산 소진"}}

        budget["operator_calls"] += 1
        budget["consumed_depth"] = max(budget["consumed_depth"], depth)
        selected = {"operator": operator, "depth": depth}
        self.record["operators_considered"]["selected"].append(selected)
        before = len(self.record["calls"])
        result = invoke(self.record)
        actual_segments = len(result.get("segments", [])) + len(result.get("rows", []))
        actual_hypotheses = len(result.get("events", []))
        actual_violations = []
        if budget["segments_examined"] + actual_segments > budget["max_segments"]:
            actual_violations.append("실제 segment 출력이 max_segments 초과")
        if budget["hypotheses_examined"] + actual_hypotheses > budget["max_hypotheses"]:
            actual_violations.append("실제 hypothesis 출력이 max_hypotheses 초과")
        if actual_violations:
            self.reject(operator, "; ".join(actual_violations))
            return {"status": "budget_exhausted",
                    "violated": [{"check": "exploration_budget", "passed": False,
                                  "detail": detail} for detail in actual_violations],
                    "label_ceiling": {"상태": "데이터 확인 — 예산 소진"}}
        budget["segments_examined"] += actual_segments
        budget["hypotheses_examined"] += actual_hypotheses

        call_id = f"call-{budget['operator_calls']:03d}"
        for call in self.record["calls"][before:]:
            call["call_id"] = call_id
        self.record["dag"].append({"call_id": call_id, "operator": operator,
                                   "depth": depth, "status": result.get("status")})
        for check in result.get("checks", []) + result.get("violated", []):
            self.record["gates_passed"].append({"call_id": call_id, **check})
        result["provenance_ref"] = call_id
        result["operator_ref"] = f"{base_operator}@v{contract['version']}"
        return result
