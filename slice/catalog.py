"""실행 가능한 metric domain pack을 로드하고 질문의 닫힌 지표 어휘를 해소한다."""
import copy
import json
from pathlib import Path

from kernel import load_ledger


HERE = Path(__file__).parent


def load_metric_catalog(path=None):
    catalog_path = Path(path) if path else HERE / "metric_catalog.json"
    catalog = json.loads(catalog_path.read_text())
    contexts = []
    for entry in catalog["entries"]:
        if "fixture_path" in entry:
            source = catalog_path.parent / entry["fixture_path"]
            fixture = json.loads(source.read_text())
            sem = {"metric": fixture["metric"], "dimensions": fixture["dimensions"]}
            rows = fixture["rows"]
        else:
            source = catalog_path.parent / entry["semantic_path"]
            sem = json.loads(source.read_text())
            data = entry["data"]
            if data["loader"] != "commerce_ledger":
                raise ValueError(f"지원하지 않는 data loader: {data['loader']}")
            rows = load_ledger(catalog_path.parent / data["path"])

        sem = copy.deepcopy(sem)
        sem["question_defaults"] = {
            **catalog["defaults"], **sem.get("question_defaults", {})}
        sem["metric"].setdefault("aliases", [sem["metric"]["name"]])
        contexts.append({
            "sem": sem,
            "rows": rows,
            "execution_profile": entry["execution_profile"],
            "source_ref": str(source.relative_to(catalog_path.parent)),
        })
    return contexts


def resolve_metric(question, contexts=None):
    contexts = contexts or load_metric_catalog()
    matches = []
    for context in contexts:
        metric = context["sem"]["metric"]
        vocabulary = metric.get("aliases", [metric["name"]])
        if any(alias in question for alias in vocabulary):
            matches.append(context)

    candidates = [c["sem"]["metric"]["name"] for c in contexts]
    if not matches:
        return None, {
            "status": "x1",
            "reason": "지표 미확정 — 질문에서 등록된 지표를 찾지 못함",
            "candidates": candidates,
            "message": f"등록된 지표는 {candidates}입니다. 어느 지표를 물으시는 건가요?",
        }
    if len(matches) > 1:
        names = [c["sem"]["metric"]["name"] for c in matches]
        return None, {
            "status": "clarify", "reason": "복수 지표 지정",
            "candidates": names,
            "message": f"한 번에 한 지표를 지정해 주세요: {names}",
        }
    return matches[0], None


def context_by_metric_ref(metric_ref, contexts=None):
    contexts = contexts or load_metric_catalog()
    for context in contexts:
        metric = context["sem"]["metric"]
        if f"{metric['id']}@v{metric['version']}" == metric_ref:
            return context
    return None
