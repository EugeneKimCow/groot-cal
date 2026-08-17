"""기존 fixture(CSV·JSON)를 단일 DuckDB 저장소로 적재한다.

data backend port(E-006·unresolved #12)의 첫 실물이다. 값·행 순서를 원본과
정확히 보존해 input snapshot hash가 바뀌지 않게 한다 — 저장소 교체는
parity 게이트로 검증되는 증분이지, 데이터 변경이 아니다.

실행: ../.venv/bin/python3 build_duckdb.py
"""
import json
from pathlib import Path

import duckdb

from kernel import load_ledger

HERE = Path(__file__).parent
DB_PATH = HERE / "store" / "groot.duckdb"

CHALLENGE_TABLES = {
    "operating_profit": "challenges/operating_profit.json",
    "loss_ratio": "challenges/loss_ratio.json",
    "inventory_balance": "challenges/inventory_balance.json",
    "active_customers": "challenges/active_customers.json",
    "seattle_weather": "onboarded/seattle_weather.json",  # E-026 실데이터
}


def _column_type(rows, name):
    values = [row.get(name) for row in rows if row.get(name) is not None]
    if values and all(isinstance(v, int) and not isinstance(v, bool)
                      for v in values):
        return "BIGINT"
    if values and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                      for v in values):
        return "DOUBLE"
    return "VARCHAR"


def _create_and_fill(con, table, rows):
    columns = list(rows[0].keys())
    decls = ", ".join(f'"{name}" {_column_type(rows, name)}' for name in columns)
    con.execute(f'DROP TABLE IF EXISTS "{table}"')
    con.execute(f'CREATE TABLE "{table}" (_seq BIGINT, {decls})')
    placeholders = ", ".join("?" for _ in range(len(columns) + 1))
    con.executemany(
        f'INSERT INTO "{table}" VALUES ({placeholders})',
        [[index] + [row.get(name) for name in columns]
         for index, row in enumerate(rows)])
    return len(rows)


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    counts = {"sales_ledger": _create_and_fill(
        con, "sales_ledger", load_ledger())}
    for table, fixture_path in CHALLENGE_TABLES.items():
        rows = json.loads((HERE / fixture_path).read_text())["rows"]
        counts[table] = _create_and_fill(con, table, rows)
    con.close()
    for table, count in counts.items():
        print(f"{table}: {count}행")
    print(f"→ {DB_PATH}")


if __name__ == "__main__":
    main()
