#!/usr/bin/env python3
"""Score a candidate regex against a labelled set of positive and negative strings.

Autoclaw passes the regex as --pattern. A hypothesis that fails to compile, or
that matches more than a few milliseconds per string, scores zero. Precision,
recall and F1 come from matching against data.jsonl in the same directory.
"""
import argparse
import json
import pathlib
import re
import time


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", required=True, help="Regex to evaluate.")
    ap.add_argument("--flags", default="", help="One or more of i, m, s, x.")
    ap.add_argument("--output-dir", default=".")
    args, _unknown = ap.parse_known_args()  # tolerate extra params

    flag_bits = 0
    for f in args.flags.lower():
        flag_bits |= {"i": re.I, "m": re.M, "s": re.S, "x": re.X}.get(f, 0)

    try:
        pattern = re.compile(args.pattern, flag_bits)
    except re.error as exc:
        print(json.dumps({"f1": 0.0, "compile_error": str(exc)}))
        return

    data_path = pathlib.Path(__file__).with_name("data.jsonl")
    tp = fp = fn = tn = 0
    slow = 0
    start = time.perf_counter()
    for line in data_path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        s, want = row["text"], bool(row["match"])
        t0 = time.perf_counter()
        try:
            got = pattern.search(s) is not None
        except re.error:
            got = False
        if time.perf_counter() - t0 > 0.01:  # 10 ms per string = catastrophic backtracking
            slow += 1
            got = False
        if got and want:
            tp += 1
        elif got and not want:
            fp += 1
        elif not got and want:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    elapsed_ms = (time.perf_counter() - start) * 1000

    print(json.dumps({
        "f1": round(f1, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "false_positives": fp,
        "false_negatives": fn,
        "slow_matches": slow,  # strings over 10 ms — redos or awful alternations
        "elapsed_ms": round(elapsed_ms, 1),
    }))


if __name__ == "__main__":
    main()
