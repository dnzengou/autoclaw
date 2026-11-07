#!/usr/bin/env python3
"""Regenerate db.sql and baseline.json for the SQL speedup example.

Run once; the generated files are committed so experiments stay reproducible.
"""
import json
import pathlib
import random
import sqlite3
import time

HERE = pathlib.Path(__file__).parent
random.seed(2026)

BASELINE_QUERY = """
SELECT o.customer_id,
       COUNT(*) AS orders,
       SUM(o.amount_cents) AS total_cents
FROM   orders o
JOIN   customers c ON c.id = o.customer_id
WHERE  c.country = 'US'
  AND  o.created_at >= '2026-01-01'
GROUP BY o.customer_id
HAVING SUM(o.amount_cents) > 100000
ORDER BY total_cents DESC
LIMIT 20;
"""


def build_sql() -> str:
    lines = [
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, country TEXT NOT NULL, signed_up_at TEXT NOT NULL);",
        "CREATE TABLE orders   (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, amount_cents INTEGER NOT NULL, created_at TEXT NOT NULL);",
    ]
    countries = ["US", "GB", "DE", "FR", "JP", "BR", "IN", "CA", "AU", "NL"]
    for i in range(1, 2001):
        c = random.choices(countries, weights=[40, 10, 10, 8, 6, 6, 6, 5, 5, 4])[0]
        lines.append(f"INSERT INTO customers VALUES ({i}, '{c}', '2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}');")
    for oid in range(1, 25001):
        cid = random.randint(1, 2000)
        amt = random.randint(500, 50_000)
        y = 2026 if random.random() < 0.7 else 2025
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        lines.append(f"INSERT INTO orders VALUES ({oid}, {cid}, {amt}, '{y}-{month:02d}-{day:02d}');")
    return "\n".join(lines) + "\n"


def main() -> None:
    (HERE / "db.sql").write_text(build_sql())
    conn = sqlite3.connect(":memory:")
    conn.executescript((HERE / "db.sql").read_text())

    best = float("inf")
    rows = []
    for _ in range(10):
        t0 = time.perf_counter_ns()
        rows = conn.execute(BASELINE_QUERY).fetchall()
        best = min(best, (time.perf_counter_ns() - t0) / 1_000)

    (HERE / "baseline.json").write_text(json.dumps({
        "query": BASELINE_QUERY.strip(),
        "baseline_us": round(best, 1),
        "rows": [list(r) for r in rows],
    }, indent=2))
    print(f"baseline: {best:.1f} µs, {len(rows)} rows")


if __name__ == "__main__":
    main()
