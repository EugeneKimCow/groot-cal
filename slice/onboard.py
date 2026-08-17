"""실데이터 온보딩 킷 — CSV를 계약·저장소로 등록하는 계측된 경로.

온보딩 비용의 해부가 목적이다: 기계가 파생할 수 있는 것(열 형 추론·차원 값
열거·기간 범위·NULL 분포)과 사람이 선언해야 하는 것(지표 정체성·type·단위·
부호·집계 규칙·MECE 판정·별칭·window)을 분리한다 — ``scaffold_contract``의
키워드 인자 목록이 곧 지식 획득 비용의 계측표다. 검증은 기존 게이트가 한다:
온보딩이 끝났다는 판정은 문서가 아니라 evaluate_metric의 통과다.
"""
import argparse
import csv
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent


def profile_csv(path):
    """기계 파생 가능한 사실만 수집한다 — 의미 판단은 하지 않는다."""
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("빈 CSV는 온보딩할 수 없다")
    columns = {}
    for name in rows[0].keys():
        raw = [row.get(name) for row in rows]
        present = [value for value in raw if value not in (None, "")]
        kind = _infer_kind(present)
        distinct = sorted({value for value in present})
        columns[name] = {
            "kind": kind,
            "nulls": len(raw) - len(present),
            "distinct_count": len(distinct),
            "values": distinct if kind == "str" and len(distinct) <= 12 else None,
            "sample": distinct[:3],
        }
    date_columns = [name for name, info in columns.items()
                    if info["kind"] == "date"]
    span = None
    if date_columns:
        values = sorted(row[date_columns[0]] for row in rows
                        if row.get(date_columns[0]))
        span = {"column": date_columns[0], "first": values[0],
                "last": values[-1]}
    return {"path": str(path), "row_count": len(rows), "columns": columns,
            "date_columns": date_columns, "date_span": span}


def _infer_kind(values):
    if not values:
        return "empty"
    if all(_is_date(value) for value in values):
        return "date"
    if all(_is_int(value) for value in values):
        return "int"
    if all(_is_float(value) for value in values):
        return "float"
    return "str"


def _is_date(value):
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def _is_int(value):
    try:
        int(value)
        return "." not in str(value)
    except (TypeError, ValueError):
        return False


def _is_float(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def scaffold_contract(profile, *, metric_id, name, aliases, metric_type, unit,
                      value_field, sign, aggregation_rule="sum",
                      date_field=None, dimension_fields=(), mece_fields=(),
                      available_windows=("month",), extra_properties=None):
    """사람의 선언(키워드 인자)과 기계의 열거(profile)를 계약으로 조립한다."""
    columns = profile["columns"]
    for field in (value_field, *([date_field] if date_field else ()),
                  *dimension_fields):
        if field not in columns:
            raise ValueError(f"CSV에 없는 열: {field}")
    properties = {
        "additive_across_dims": True,
        "additive_across_time": True,
        "aggregation_rule": aggregation_rule,
        "sign": sign,
        "available_windows": list(available_windows),
        **(extra_properties or {}),
    }
    bindings = {"value_field": value_field}
    if date_field:
        bindings["date_field"] = date_field
    dimensions = {}
    for field in dimension_fields:
        values = columns[field]["values"]
        if not values:
            raise ValueError(
                f"{field}: 저카디널리티 문자열 열만 차원으로 열거 가능 "
                f"(distinct={columns[field]['distinct_count']})")
        dimensions[field] = {"type": "nominal", "values": values,
                             "mece": field in mece_fields}
    return {
        "metric": {
            "id": metric_id, "name": name, "aliases": list(aliases),
            "type": metric_type, "version": 1, "unit": unit,
            "properties": properties, "bindings": bindings,
            "generation": {"source": profile["path"],
                           "grain": "일별" if date_field else "행별"},
        },
        "dimensions": dimensions,
    }


def build_fixture(csv_path, sem, out_path):
    """CSV 행을 계약이 소비하는 fixture 형태로 정규화해 기록한다."""
    bindings = sem["metric"]["bindings"]
    value_field = bindings["value_field"]
    date_field = bindings.get("date_field")
    keep = [value_field, *([date_field] if date_field else ()),
            *sem["dimensions"].keys()]
    with open(csv_path, newline="") as handle:
        raw_rows = list(csv.DictReader(handle))
    # 수치 타입은 열 단위로 결정한다 — 값 단위 int/float 혼합은 저장소 왕복
    # (DuckDB DOUBLE)과 input hash를 어긋나게 한다 (E-026 발견).
    integral_column = all(float(raw.get(value_field)).is_integer()
                          for raw in raw_rows)
    rows = []
    for raw in raw_rows:
        row = {}
        for field in keep:
            value = raw.get(field)
            if field == value_field:
                number = float(value)
                row[field] = int(number) if integral_column else number
            else:
                row[field] = value if value not in (None, "") else None
        if date_field:
            row["month"] = row[date_field][:7]
            row["date"] = row.pop(date_field)
            if date_field != "date":
                sem["metric"]["bindings"]["date_field"] = "date"
        rows.append(row)
    fixture = {"metric": sem["metric"], "dimensions": sem["dimensions"],
               "rows": rows}
    Path(out_path).write_text(json.dumps(fixture, ensure_ascii=False, indent=1))
    return fixture


def load_fixture_into_duckdb(fixture, table, db_path):
    import duckdb
    rows = fixture["rows"]
    columns = list(rows[0].keys())

    def column_type(name):
        values = [row[name] for row in rows if row[name] is not None]
        if values and all(isinstance(v, int) for v in values):
            return "BIGINT"
        if values and all(isinstance(v, (int, float)) for v in values):
            return "DOUBLE"
        return "VARCHAR"

    connection = duckdb.connect(str(db_path))
    try:
        decls = ", ".join(f'"{n}" {column_type(n)}' for n in columns)
        connection.execute(f'DROP TABLE IF EXISTS "{table}"')
        connection.execute(f'CREATE TABLE "{table}" (_seq BIGINT, {decls})')
        placeholders = ", ".join("?" for _ in range(len(columns) + 1))
        connection.executemany(
            f'INSERT INTO "{table}" VALUES ({placeholders})',
            [[index] + [row[n] for n in columns]
             for index, row in enumerate(rows)])
    finally:
        connection.close()
    return len(rows)


def context_from_fixture(fixture_path, defaults=None):
    """온보딩된 fixture를 기존 catalog 컨텍스트 형태로 만든다."""
    from catalog import load_metric_catalog
    fixture = json.loads(Path(fixture_path).read_text())
    base = load_metric_catalog()
    question_defaults = defaults or base[0]["sem"]["question_defaults"]
    sem = {"metric": fixture["metric"], "dimensions": fixture["dimensions"],
           "question_defaults": dict(question_defaults)}
    sem["metric"].setdefault("aliases", [sem["metric"]["name"]])
    return {"sem": sem, "rows": fixture["rows"],
            "execution_profile": "typed_core",
            "source_ref": str(Path(fixture_path).name)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["profile"])
    parser.add_argument("csv_path")
    args = parser.parse_args()
    profile = profile_csv(args.csv_path)
    print(f"행: {profile['row_count']} · 기간: {profile['date_span']}")
    for name, info in profile["columns"].items():
        enumerated = (f" values={info['values']}" if info["values"] else "")
        print(f"  {name}: {info['kind']} distinct={info['distinct_count']}"
              f" nulls={info['nulls']}{enumerated}")


if __name__ == "__main__":
    main()
