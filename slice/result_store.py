"""분석 결과 materialization과 staleness 판정 경계."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from result_adapter import adapt_result


POLICIES = {"immutable_snapshot", "recompute_on_source_change", "expires_at"}


def _iso_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def materialize_result(bundle, result_key, created_at=None,
                       policy="recompute_on_source_change", expires_at=None):
    if policy not in POLICIES:
        return {"status": "out_of_domain",
                "violated": [{"check": "staleness_policy", "passed": False,
                              "detail": policy}]}
    if policy == "expires_at" and not expires_at:
        return {"status": "out_of_domain",
                "violated": [{"check": "expires_at_required", "passed": False,
                              "detail": "expires_at policy에는 만료 시각 필요"}]}
    record = bundle.get("execution_record")
    result = (bundle.get("results") or {}).get(result_key)
    adapted = adapt_result(result, result_key)
    if record is None or adapted["status"] != "result":
        return {"status": "out_of_domain",
                "violated": [{"check": "materializable_result", "passed": False,
                              "detail": f"정상 operator result 필요: {result_key}"}]}

    result_view = adapted["view"]
    provenance = record["provenance"]
    identity = "|".join([
        record["query_spec_hash"], result_key, result_view["operator_ref"],
        provenance["input_snapshot_ref"],
    ])
    result_id = "result-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
    return {
        "result_id": result_id,
        "storage_kind": "materialized_result",
        "result_key": result_key,
        "query_spec_hash": record["query_spec_hash"],
        "operator_ref": result_view["operator_ref"],
        "metric_ref": provenance["metric_ref"],
        "input_snapshot_ref": provenance["input_snapshot_ref"],
        "created_at": created_at or _iso_now(),
        "question": bundle["spec"].get("question"),
        "query_spec": bundle["spec"].get("query_spec"),
        "staleness": {"policy": policy, "expires_at": expires_at},
        "provenance": provenance,
        "payload": result,
    }


def save_stored_result(stored, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = load_stored_result(path)
        if existing != stored:
            raise FileExistsError(f"기존 저장 결과를 덮어쓸 수 없음: {path}")
        return path
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(stored, ensure_ascii=False, indent=2))
    temp.replace(path)
    return path


def load_stored_result(path):
    return json.loads(Path(path).read_text())


def assess_staleness(stored, current_input_snapshot_ref=None, as_of=None):
    required = {"result_id", "input_snapshot_ref", "staleness", "created_at"}
    missing = sorted(required - set(stored))
    if missing:
        return {"status": "out_of_domain",
                "violated": [{"check": "stored_result_valid", "passed": False,
                              "detail": f"누락 필드 {missing}"}]}
    policy = stored["staleness"].get("policy")
    if policy not in POLICIES:
        return {"status": "out_of_domain",
                "violated": [{"check": "staleness_policy", "passed": False,
                              "detail": str(policy)}]}

    common = {
        "status": "result", "output_type": "StalenessAssessment",
        "result_id": stored["result_id"], "policy": policy,
        "label_ceiling": {"staleness": "데이터 확인"},
    }
    if policy == "immutable_snapshot":
        return {**common, "staleness_status": "immutable_snapshot",
                "reason": "입력 스냅샷에 고정된 결과; 최신 상태 주장 아님"}
    if policy == "expires_at":
        expires_at = stored["staleness"].get("expires_at")
        if not expires_at:
            return {"status": "out_of_domain",
                    "violated": [{"check": "expires_at_required", "passed": False,
                                  "detail": "저장 결과에 expires_at 없음"}]}
        now = _parse_time(as_of or _iso_now())
        expired = now >= _parse_time(expires_at)
        return {**common, "staleness_status": "stale" if expired else "fresh",
                "reason": f"expires_at={expires_at}, as_of={as_of or 'now'}"}

    if current_input_snapshot_ref is None:
        return {"status": "suspended", "missing_inputs": ["current_input_snapshot_ref"],
                "pass_conditions": "현재 원천 스냅샷 hash를 제공하면 판정 가능"}
    changed = current_input_snapshot_ref != stored["input_snapshot_ref"]
    return {**common, "staleness_status": "stale" if changed else "fresh",
            "reason": ("원천 스냅샷 변경" if changed else "원천 스냅샷 동일"),
            "stored_input_snapshot_ref": stored["input_snapshot_ref"],
            "current_input_snapshot_ref": current_input_snapshot_ref}
