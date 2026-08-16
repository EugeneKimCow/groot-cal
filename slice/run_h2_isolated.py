"""C0/C1 H2 packet을 최소 파일 workspace와 Seatbelt에서 실행한다."""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from eval_h2 import load_conditions, score_trace


ROOT = Path(__file__).resolve().parent.parent
SKIP_RESOURCES = {"question", "calculator", "engine.run_question", "result_envelope"}


def prepare_condition_workspace(condition, parent=None):
    catalog = load_conditions()
    capability = catalog["conditions"].get(condition)
    if capability is None:
        raise ValueError(f"미등록 condition: {condition}")
    workspace = Path(tempfile.mkdtemp(prefix=f"groot-h2-{condition}-", dir=parent))
    copied = []
    for resource in capability["allowed_resources"]:
        if resource in SKIP_RESOURCES:
            continue
        relative = resource.rstrip("/")
        source = ROOT / relative
        if not source.exists():
            raise FileNotFoundError(f"허용 resource 부재: {resource}")
        target = workspace / relative
        if source.is_dir():
            shutil.copytree(source, target)
            copied.extend(path.relative_to(workspace).as_posix()
                          for path in target.rglob("*") if path.is_file())
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(target.relative_to(workspace).as_posix())
    manifest = {
        "condition": condition,
        "allowed_resources": capability["allowed_resources"],
        "prohibited_resources": capability["prohibited_resources"],
        "copied_files": sorted(copied),
    }
    (workspace / "CAPABILITY.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2))
    return workspace, manifest


def seatbelt_profile(project_root=ROOT):
    escaped = str(project_root).replace('"', '\\"')
    return "\n".join([
        "(version 1)",
        "(allow default)",
        f'(deny file-read* (subpath "{escaped}"))',
        f'(deny file-write* (subpath "{escaped}"))',
    ])


def verify_project_denied(workspace, project_root=ROOT, sandbox_bin="sandbox-exec"):
    profile = seatbelt_profile(project_root)
    allowed = subprocess.run(
        [sandbox_bin, "-p", profile, "/usr/bin/head", "-c", "1",
         str(workspace / "CAPABILITY.json")],
        capture_output=True, text=True, check=False)
    prohibited = subprocess.run(
        [sandbox_bin, "-p", profile, "/usr/bin/head", "-c", "1",
         str(project_root / "eval" / "golden-set-v1" / "cases.json")],
        capture_output=True, text=True, check=False)
    return {
        "passed": allowed.returncode == 0 and prohibited.returncode != 0,
        "allowed_returncode": allowed.returncode,
        "prohibited_returncode": prohibited.returncode,
    }


def _resource_payload(workspace, manifest):
    resources = []
    for relative in manifest["copied_files"]:
        path = workspace / relative
        resources.append({"path": relative, "content": path.read_text()})
    return resources


def build_prompt(packet, model, workspace, manifest):
    capability = packet["capability"]
    trace_contract = {
        "experiment_version": packet["experiment_version"],
        "condition": packet["condition"],
        "capability": capability,
        "output_schema_ref": packet["output_schema_ref"],
        "trace_requirements": packet["trace_requirements"],
        "trace_template": packet["trace_template"],
        "normalization_notes": packet["normalization_notes"],
    }
    assignment = {"case": packet["case"], "attempt": packet["attempt"]}
    return "\n".join([
        "당신은 독립 평가 실행자입니다. 이 대화 밖의 사전 지식이나 웹 검색을 사용하지 마세요.",
        "아래 resource_payload와 질문만 사용하고, 금지 resource를 탐색하거나 추측하지 마세요.",
        "resource_payload는 runner가 condition allowlist를 검증한 뒤 제공한 파일 내용입니다.",
        "필요한 계산을 반드시 수행하고, 사용한 payload path를 access_log에 기록하세요.",
        "최종 출력은 설명이나 markdown fence 없이 agent-trace-v1 JSON 객체 하나여야 합니다.",
        "trace_template의 key와 중첩 형태를 정확히 유지하고 임의 필드명으로 바꾸지 마세요.",
        "normalization_notes에 따라 서로 다른 조건의 관측을 공통 trace 형태로 정규화하세요.",
        f"agent_ref는 codex-cli:{model} 로 기록하세요.",
        "access_log에는 실제로 읽거나 호출한 상대 resource를 모두 기록하세요.",
        "숫자는 원장 단위 u로 기록하고 표시 단위 변환은 final_answer에서만 하세요.",
        "모르는 필드는 null 또는 빈 배열로 두되 관측하지 않은 사실을 만들지 마세요.",
        "조건 지시: " + capability["instructions"],
        "공통 trace 계약:",
        json.dumps(trace_contract, ensure_ascii=False, indent=2),
        "허용 resource payload:",
        json.dumps(_resource_payload(workspace, manifest), ensure_ascii=False),
        "이번 실행 assignment:",
        json.dumps(assignment, ensure_ascii=False, indent=2),
    ])


def parse_trace_from_jsonl(stdout):
    messages = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            messages.append(item.get("text", ""))
    if not messages:
        raise ValueError("agent_message가 없는 Codex JSONL 출력")
    text = messages[-1].strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])
    return json.loads(text)


def run_packet(packet_path, out_dir, model="gpt-5.6-terra", reasoning="medium",
               codex_bin=None, sandbox_bin="sandbox-exec", timeout=600):
    packet = json.loads(Path(packet_path).read_text())
    condition = packet["condition"]
    if condition not in {"raw", "advisory"}:
        raise ValueError("격리 agent runner는 raw/advisory packet만 실행한다")
    workspace, manifest = prepare_condition_workspace(condition)
    isolation = verify_project_denied(workspace, sandbox_bin=sandbox_bin)
    if not isolation["passed"]:
        raise RuntimeError(f"project read isolation 실패: {isolation}")
    executable = codex_bin or shutil.which("codex")
    if executable is None:
        raise FileNotFoundError("codex executable을 찾지 못함")
    command = [
        sandbox_bin, "-p", seatbelt_profile(), executable, "exec",
        "--ephemeral", "--ignore-user-config", "--ignore-rules",
        "--sandbox", "read-only", "--skip-git-repo-check",
        "--model", model, "-c", f'model_reasoning_effort="{reasoning}"',
        "-c", 'web_search="disabled"', "--json", "-C", str(workspace),
        build_prompt(packet, model, workspace, manifest),
    ]
    environment = os.environ.copy()
    environment["PWD"] = str(workspace)
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False, timeout=timeout,
        cwd=workspace, env=environment)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(packet_path).stem
    raw_path = out_dir / f"{condition}__{stem}.jsonl"
    raw_path.write_text(completed.stdout)
    if completed.returncode != 0:
        error_path = out_dir / f"{condition}__{stem}.stderr.txt"
        error_path.write_text(completed.stderr)
        raise RuntimeError(f"codex exec 실패({completed.returncode}): {error_path}")
    trace = parse_trace_from_jsonl(completed.stdout)
    trace_path = out_dir / f"{condition}__{stem}.json"
    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2))
    scored = score_trace(trace)
    score_path = out_dir / f"{condition}__{stem}.score.json"
    score_path.write_text(json.dumps(scored, ensure_ascii=False, indent=2))
    audit = {
        "packet": str(packet_path), "workspace": str(workspace),
        "manifest": manifest, "isolation": isolation,
        "model": model, "reasoning": reasoning,
        "trace": str(trace_path), "score": str(score_path),
    }
    (out_dir / f"{condition}__{stem}.audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2))
    return audit, scored


def select_packet_paths(packets_dir, conditions, attempts=None):
    paths = []
    suffixes = None if attempts is None else {f"__{attempt:02d}" for attempt in attempts}
    for condition in conditions:
        condition_dir = Path(packets_dir) / condition
        if not condition_dir.is_dir():
            raise FileNotFoundError(f"packet condition 디렉터리 부재: {condition_dir}")
        candidates = sorted(condition_dir.glob("*.json"))
        if suffixes is not None:
            candidates = [path for path in candidates
                          if any(path.stem.endswith(suffix) for suffix in suffixes)]
        paths.extend(candidates)
    return paths


def run_batch(packets_dir, out_dir, conditions, model="gpt-5.6-terra",
              reasoning="medium", resume=False, max_runs=None, attempts=None):
    paths = select_packet_paths(packets_dir, conditions, attempts=attempts)
    if max_runs is not None:
        paths = paths[:max_runs]
    rows = []
    for index, packet_path in enumerate(paths, 1):
        condition = packet_path.parent.name
        trace_path = Path(out_dir) / f"{condition}__{packet_path.stem}.json"
        if resume and trace_path.exists():
            rows.append({"packet": str(packet_path), "status": "skipped_existing"})
            print(f"[{index}/{len(paths)}] skip {condition}/{packet_path.name}", flush=True)
            continue
        try:
            audit, scored = run_packet(
                packet_path, out_dir, model=model, reasoning=reasoning)
            rows.append({"packet": str(packet_path), "status": "completed",
                         "valid": scored.get("valid"), "passed": scored.get("passed"),
                         "audit": audit})
            print(f"[{index}/{len(paths)}] done {condition}/{packet_path.name}", flush=True)
        except Exception as error:  # batch는 실패 기록 후 다음 packet을 계속한다.
            rows.append({"packet": str(packet_path), "status": "error",
                         "error": f"{type(error).__name__}: {error}"})
            print(f"[{index}/{len(paths)}] error {condition}/{packet_path.name}: {error}",
                  flush=True)
    summary = {
        "packets": len(paths),
        "completed": sum(row["status"] == "completed" for row in rows),
        "skipped_existing": sum(row["status"] == "skipped_existing" for row in rows),
        "errors": sum(row["status"] == "error" for row in rows),
        "rows": rows,
    }
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "batch-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def summarize_usage(traces_dir):
    totals = {}
    for path in sorted(Path(traces_dir).glob("*.jsonl")):
        condition = path.name.split("__", 1)[0]
        bucket = totals.setdefault(condition, {
            "turns": 0, "input_tokens": 0, "cached_input_tokens": 0,
            "output_tokens": 0, "reasoning_output_tokens": 0})
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "turn.completed":
                continue
            usage = event.get("usage", {})
            bucket["turns"] += 1
            for field in ("input_tokens", "cached_input_tokens", "output_tokens",
                          "reasoning_output_tokens"):
                bucket[field] += usage.get(field, 0)
    return totals


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--condition", required=True, choices=["raw", "advisory"])
    smoke = sub.add_parser("run")
    smoke.add_argument("--packet", required=True)
    smoke.add_argument("--out-dir", required=True)
    smoke.add_argument("--model", default="gpt-5.6-terra")
    smoke.add_argument("--reasoning", default="medium")
    batch = sub.add_parser("batch")
    batch.add_argument("--packets-dir", required=True)
    batch.add_argument("--out-dir", required=True)
    batch.add_argument("--condition", action="append", required=True,
                       choices=["raw", "advisory"])
    batch.add_argument("--model", default="gpt-5.6-terra")
    batch.add_argument("--reasoning", default="medium")
    batch.add_argument("--resume", action="store_true")
    batch.add_argument("--max-runs", type=int)
    batch.add_argument("--attempt", action="append", type=int)
    usage = sub.add_parser("usage")
    usage.add_argument("--traces-dir", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        workspace, manifest = prepare_condition_workspace(args.condition)
        isolation = verify_project_denied(workspace)
        print(json.dumps({"workspace": str(workspace), "manifest": manifest,
                          "isolation": isolation}, ensure_ascii=False, indent=2))
        return 0 if isolation["passed"] else 1
    if args.command == "usage":
        print(json.dumps(summarize_usage(args.traces_dir), ensure_ascii=False, indent=2))
        return 0
    if args.command == "run":
        audit, scored = run_packet(
            args.packet, args.out_dir, model=args.model, reasoning=args.reasoning)
        print(json.dumps({"audit": audit, "scored": scored}, ensure_ascii=False, indent=2))
        return 0 if scored.get("valid") else 1
    summary = run_batch(
        args.packets_dir, args.out_dir, args.condition,
        model=args.model, reasoning=args.reasoning,
        resume=args.resume, max_runs=args.max_runs, attempts=args.attempt)
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"},
                     ensure_ascii=False, indent=2))
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
