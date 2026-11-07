#!/usr/bin/env python3
"""Time a SQL rewrite against a fixed SQLite benchmark and score the speedup.

Autoclaw passes the candidate SQL as --sql (optionally with --indexes, a
semicolon-joined list of CREATE INDEX statements it may add). The script
loads db.sql into an in-memory SQLite database, applies the indexes,
EXPLAINs the query, runs it a few times, verifies the rows match the
baseline's rows, and prints speedup + correctness as JSON.
"""
import argparse
import json
import pathlib
import re
import sqlite3
import sys
import time

HERE = pathlib.Path(__file__).parent


def load_db(conn: sqlite3.Connection) -> None:
    conn.executescript((HERE / "db.sql").read_text())


def load_baseline() -> dict:
    return json.loads((HERE / "baseline.json").read_text())


def time_query(conn: sqlite3.Connection, sql: str, runs: int = 5) -> tuple[list, float]:
    rows = []
    best = float("inf")
    for _ in range(runs):
        t0 = time.perf_counter_ns()
        cur = conn.execute(sql)
        rows = cur.fetchall()
        best = min(best, (time.perf_counter_ns() - t0) / 1_000)  # µs
    return rows, best


def forbidden(sql: str, indexes: str) -> str:
    """Returns an error string if the hypothesis cheats or does something unsafe."""
    joined = sql + " ;; " + indexes
    bad = re.search(r"\b(ATTACH|DETACH|DROP|DELETE|UPDATE|INSERT|REPLACE|PRAGMA|VACUUM)\b", joined, re.I)
    return bad.group(1).lower() if bad else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql", required=True, help="Rewritten SELECT.")
    ap.add_argument("--indexes", default="", help="Semicolon-joined CREATE INDEX statements.")
    ap.add_argument("--output-dir", default=".")
    args, _unknown = ap.parse_known_args()

    cheat = forbidden(args.sql, args.indexes)
    if cheat:
        print(json.dumps({"speedup": 0.0, "correct": False, "error": f"forbidden statement: {cheat.upper()}"}))
        return

    baseline = load_baseline()
    conn = sqlite3.connect(":memory:")
    load_db(conn)
    for stmt in filter(None, (s.strip() for s in args.indexes.split(";"))):
        try:
            conn.execute(stmt)
        except sqlite3.Error as exc:
            print(json.dumps({"speedup": 0.0, "correct": False, "error": f"index: {exc}"}))
            return

    try:
        rows, us = time_query(conn, args.sql)
    except sqlite3.Error as exc:
        print(json.dumps({"speedup": 0.0, "correct": False, "error": f"query: {exc}"}))
        return

    want = [tuple(r) for r in baseline["rows"]]
    got = [tuple(r) for r in rows]
    correct = want == got

    speedup = (baseline["baseline_us"] / us) if us > 0 else 0.0
    if not correct:
        speedup = 0.0

    print(json.dumps({
        "speedup": round(speedup, 3),
        "correct": correct,
        "query_us": round(us, 1),
        "baseline_us": baseline["baseline_us"],
        "rows_returned": len(rows),
        "rows_expected": len(want),
    }))


if __name__ == "__main__":
    sys.exit(main())
