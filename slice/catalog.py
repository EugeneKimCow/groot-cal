"""실행 가능한 metric domain pack을 로드하고 질문의 닫힌 지표 어휘를 해소한다."""
import copy
import json
import os
from pathlib import Path

from kernel import load_ledger


HERE = Path(__file__).parent


def _load_rows(data, base):
    """등록된 data loader만 실행한다. 미등록 loader·부재 backend는 명시 실패."""
    loader = data["loader"]
    if loader == "commerce_ledger":
        return load_ledger(base / data["path"])
    if loader == "duckdb":
        try:
            import duckdb
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "duckdb backend 필요 — 프로젝트 venv로 실행하세요 "
                "(.venv/bin/python3)") from error
        connection = duckdb.connect(str(base / data["path"]), read_only=True)
        try:
            cursor = connection.execute(
                f'SELECT * FROM "{data["table"]}" ORDER BY _seq')
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, values)) for values in cursor.fetchall()]
        finally:
            connection.close()
        for row in rows:
            row.pop("_seq", None)
        return rows
    raise ValueError(f"지원하지 않는 data loader: {loader}")


def load_metric_catalog(path=None):
    if path is None:
        path = os.environ.get("GROOT_CATALOG")
    catalog_path = (HERE / path if path and not Path(path).is_absolute()
                    else Path(path)) if path else HERE / "metric_catalog.json"
    catalog = json.loads(catalog_path.read_text())
    contexts = []
    for entry in catalog["entries"]:
        if "fixture_path" in entry:
            source = catalog_path.parent / entry["fixture_path"]
            fixture = json.loads(source.read_text())
            sem = {"metric": fixture["metric"], "dimensions": fixture["dimensions"]}
            rows = (_load_rows(entry["data"], catalog_path.parent)
                    if "data" in entry else fixture["rows"])
        else:
            source = catalog_path.parent / entry["semantic_path"]
            sem = json.loads(source.read_text())
            rows = _load_rows(entry["data"], catalog_path.parent)

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
