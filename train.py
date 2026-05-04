#!/usr/bin/env python3
"""Demo train.py — simulates training a DistilBERT sentiment classifier.

Replaces with real training script for production use.
Accepts experiment parameters via command-line flags and writes metrics to stdout JSON.
"""
import json
import random
import sys
import time
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--output_dir", type=str, default="./output")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # Simulate training time
    duration = random.uniform(10, 30)
    time.sleep(min(duration, 5))  # cap for demo speed

    # Simulate metrics with baseline around 0.82 + small random variation
    # Better params get slightly better results
    lr_bonus = 0.0
    if 1e-5 <= args.lr <= 3e-5:
        lr_bonus = 0.01
    elif args.lr > 1e-4:
        lr_bonus = -0.05

    dropout_bonus = 0.0
    if 0.1 <= args.dropout <= 0.2:
        dropout_bonus = 0.005

    epoch_bonus = min(args.epochs * 0.003, 0.015)

    base_f1 = 0.82 + lr_bonus + dropout_bonus + epoch_bonus
    noise = random.gauss(0, 0.015)
    f1 = max(0.5, min(0.99, base_f1 + noise))

    metrics = {
        "f1_score": round(f1, 4),
        "accuracy": round(f1 + random.gauss(0, 0.01), 4),
        "inference_time_ms": round(random.uniform(1.2, 2.5), 2),
        "training_duration_s": round(duration, 1)
    }

    print(json.dumps(metrics))

if __name__ == "__main__":
    main()
