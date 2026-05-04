#!/usr/bin/env python3
"""Demo eval.py — evaluates training output and produces scored results.

Reads metrics from train output, scores against rubric, appends to results.json.
"""
import json
import sys
import os
import glob
from pathlib import Path

RUBRIC_PATH = "rubric.json"


def load_rubric():
    with open(RUBRIC_PATH) as f:
        return json.load(f)


def compute_score(metrics, rubric):
    """Compute weighted score relative to baseline."""
    primary = rubric["primary_metric"]
    higher_better = rubric["higher_is_better"]

    score = 0.0
    weight_sum = 0.0

    for metric, weight in rubric["weights"].items():
        if metric not in metrics:
            continue
        val = metrics[metric]
        weight_sum += weight

        # Normalize: higher_is_better metrics contribute positively
        # Lower_is_better metrics need inversion
        if metric == rubric["primary_metric"]:
            score += weight * val
        elif metric == "inference_time_ms":
            score += weight * (1.0 - val / 10.0)  # normalize: 0ms = 1.0, 10ms = 0.0
        elif metric == "loss":
            score += weight * (1.0 - val)  # lower loss = higher score
        else:
            score += weight * val

    if weight_sum > 0:
        score /= weight_sum

    return round(score, 4)


def main():
    rubric = load_rubric()

    # Find latest experiment output
    exp_dirs = sorted(Path("experiments").glob("exp-*"))
    if not exp_dirs:
        print(json.dumps({"error": "No experiment directories found", "score": 0.0}))
        sys.exit(1)

    latest = exp_dirs[-1]
    metrics_file = latest / "metrics.json"

    if not metrics_file.exists():
        print(json.dumps({"error": f"metrics.json not found in {latest}", "score": 0.0}))
        sys.exit(1)

    with open(metrics_file) as f:
        metrics = json.load(f)

    score = compute_score(metrics, rubric)

    result = {
        "metrics": metrics,
        "score": score,
        "status": "completed",
        "pass": score >= rubric.get("pass_threshold", 0.0) if rubric["higher_is_better"] else score <= rubric.get("pass_threshold", 0.0)
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
