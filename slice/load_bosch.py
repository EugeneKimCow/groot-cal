"""Bosch Production Line Performance 원본을 DuckDB로 적재·파생한다.

원본: Kaggle 대회 데이터 (재배포 금지 — data/는 gitignore, 이 스크립트와
설명 문서만 저장소에 둔다). 열 이름 규약 L{line}_S{station}_{F|D}{n}을
이용해 스테이션 단위 파생 테이블을 만든다. 날짜 열의 값은 실제 달력이 아닌
익명화된 시간 단위임에 주의(원 대회 공지).

실행: ../.venv/bin/python3 load_bosch.py
"""
import csv
import re
import time
from pathlib import Path

import duckdb

DATA = Path(__file__).parent.parent / "data" / "bosch-production-line-performance"
DB = DATA / "bosch.duckdb"

BASE_TABLES = {
    "train_numeric": ("train_numeric.csv", "numeric"),
    "train_date": ("train_date.csv", "numeric"),
    "train_categorical": ("train_categorical.csv", "varchar"),
    "test_numeric": ("test_numeric.csv", "numeric"),
    "test_date": ("test_date.csv", "numeric"),
    "test_categorical": ("test_categorical.csv", "varchar"),
}


def header_of(path):
    with open(path, newline="") as handle:
        return next(csv.reader(handle))


def column_spec(path, family):
    spec = {}
    for name in header_of(path):
        if name == "Id":
            spec[name] = "BIGINT"
        elif name == "Response":
            spec[name] = "INTEGER"
        else:
            spec[name] = "DOUBLE" if family == "numeric" else "VARCHAR"
    return spec


def station_first_date_columns(path):
    """스테이션별 첫 date 열 — 방문·시각의 대표 열 (원 대회의 표준 기법)."""
    first = {}
    for name in header_of(path):
        match = re.fullmatch(r"L(\d+)_S(\d+)_D(\d+)", name)
        if not match:
            continue
        key = (int(match.group(1)), int(match.group(2)))
        if key not in first or int(match.group(3)) < first[key][1]:
            first[key] = (name, int(match.group(3)))
    return {key: value[0] for key, value in sorted(first.items())}


def load_base(connection):
    for table, (filename, family) in BASE_TABLES.items():
        started = time.time()
        spec = column_spec(DATA / filename, family)
        connection.execute(f'DROP TABLE IF EXISTS "{table}"')
        columns = ", ".join(f"'{name}': '{kind}'"
                            for name, kind in spec.items())
        connection.execute(
            f'CREATE TABLE "{table}" AS SELECT * FROM read_csv('
            f"'{DATA / filename}', header=true, nullstr='', "
            f"columns={{{columns}}})")
        count = connection.execute(
            f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        print(f"{table}: {count:,}행 × {len(spec)}열 "
              f"({time.time() - started:.0f}s)", flush=True)


def build_derived(connection, split):
    stations = station_first_date_columns(DATA / f"{split}_date.csv")
    date_columns = ", ".join(f'"{name}"' for name in stations.values())
    connection.execute(f'DROP TABLE IF EXISTS part_station_{split}')
    connection.execute(f"""
        CREATE TABLE part_station_{split} AS
        WITH long AS (
            UNPIVOT (SELECT Id, {date_columns} FROM {split}_date)
            ON {date_columns} INTO NAME date_column VALUE station_time)
        SELECT Id,
               CAST(regexp_extract(date_column, 'L(\\d+)_', 1) AS INTEGER)
                   AS line,
               CAST(regexp_extract(date_column, '_S(\\d+)_', 1) AS INTEGER)
                   AS station,
               station_time
        FROM long
    """)
    response = (", any_value(n.Response) AS response"
                if split == "train" else "")
    join = (f"LEFT JOIN {split}_numeric AS n USING (Id)"
            if split == "train" else "")
    connection.execute(f'DROP TABLE IF EXISTS part_summary_{split}')
    connection.execute(f"""
        CREATE TABLE part_summary_{split} AS
        SELECT s.Id,
               MIN(s.station_time) AS start_time,
               MAX(s.station_time) AS end_time,
               MAX(s.station_time) - MIN(s.station_time) AS duration,
               COUNT(*) AS n_stations,
               LIST(DISTINCT s.line ORDER BY s.line) AS lines_visited
               {response}
        FROM part_station_{split} AS s {join}
        GROUP BY s.Id
    """)
    print(f"part_station_{split} / part_summary_{split} 생성", flush=True)


def build_stats(connection):
    connection.execute("DROP TABLE IF EXISTS station_stats_train")
    connection.execute("""
        CREATE TABLE station_stats_train AS
        SELECT s.line, s.station,
               COUNT(*) AS parts,
               SUM(n.Response) AS failures,
               SUM(n.Response) * 1.0 / COUNT(*) AS failure_rate
        FROM part_station_train AS s
        JOIN train_numeric AS n USING (Id)
        GROUP BY s.line, s.station
        ORDER BY s.line, s.station
    """)
    connection.execute("DROP TABLE IF EXISTS line_stats_train")
    connection.execute("""
        CREATE TABLE line_stats_train AS
        SELECT s.line,
               COUNT(DISTINCT s.Id) AS parts,
               SUM(CASE WHEN n.Response = 1 THEN 1 ELSE 0 END) AS failure_visits,
               COUNT(DISTINCT CASE WHEN n.Response = 1 THEN s.Id END)
                   AS failed_parts
        FROM part_station_train AS s
        JOIN train_numeric AS n USING (Id)
        GROUP BY s.line ORDER BY s.line
    """)
    print("station_stats_train / line_stats_train 생성", flush=True)


def main():
    started = time.time()
    connection = duckdb.connect(str(DB))
    try:
        load_base(connection)
        for split in ("train", "test"):
            build_derived(connection, split)
        build_stats(connection)
        for row in connection.execute("""
            SELECT 'train 부품 수', COUNT(*) FROM train_numeric
            UNION ALL SELECT '불량(Response=1)',
                SUM(Response) FROM train_numeric
        """).fetchall():
            print(f"  {row[0]}: {row[1]:,}")
    finally:
        connection.close()
    print(f"완료 ({time.time() - started:.0f}s) → {DB}", flush=True)


if __name__ == "__main__":
    main()
