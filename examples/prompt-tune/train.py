#!/usr/bin/env python3
"""Score an LLM classifier system prompt on a labelled set.

Autoclaw passes the prompt text as --prompt (and optional --model,
--temperature). The script sends each row of data.jsonl to the configured
LLM, parses the model's one-word answer, and prints accuracy / F1 as JSON.

Set ANTHROPIC_API_KEY, OPENAI_API_KEY or DEEPSEEK_API_KEY. The first one
set wins. With none set the script replies with a deterministic keyword
heuristic, so you can test the loop end-to-end without an account —
useful for CI, not for real prompt tuning.
"""
import argparse
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request


def _post_json(url: str, headers: dict, body: dict, timeout: int = 45) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={**headers, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def ask_anthropic(key: str, model: str, system: str, text: str, temperature: float) -> str:
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        {
            "model": model or "claude-haiku-5-5",
            "max_tokens": 16,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": text}],
        },
    )
    return data["content"][0]["text"]


def ask_openai_compat(base_url: str, key: str, model: str, system: str, text: str, temperature: float) -> str:
    data = _post_json(
        f"{base_url}/chat/completions",
        {"Authorization": f"Bearer {key}"},
        {
            "model": model,
            "temperature": temperature,
            "max_tokens": 16,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
        },
    )
    return data["choices"][0]["message"]["content"]


def classify(system: str, text: str, model: str, temperature: float) -> str:
    """Return the model's raw reply, or raise."""
    if key := os.getenv("ANTHROPIC_API_KEY"):
        return ask_anthropic(key, model, system, text, temperature)
    if key := os.getenv("OPENAI_API_KEY"):
        return ask_openai_compat("https://api.openai.com/v1", key, model or "gpt-4o-mini", system, text, temperature)
    if key := os.getenv("DEEPSEEK_API_KEY"):
        return ask_openai_compat("https://api.deepseek.com", key, model or "deepseek-chat", system, text, temperature)
    # No key: a keyword heuristic so the loop can run end-to-end for tests.
    lower = text.lower()
    hits = sum(w in lower for w in ("unsubscribe", "free", "winner", "click", "offer", "guarantee", "congratulations"))
    return "spam" if hits >= 2 or any(c in lower for c in ("$$$", "100% off", "act now")) else "ham"


LABEL_RE = re.compile(r"\b(spam|ham)\b", re.I)


def parse_label(raw: str) -> str:
    """Pick the first spam/ham token out of whatever the model said."""
    m = LABEL_RE.search(raw)
    return m.group(1).lower() if m else "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True, help="System prompt text.")
    ap.add_argument("--model", default="")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--output-dir", default=".")
    args, _unknown = ap.parse_known_args()

    data = [json.loads(line) for line in pathlib.Path(__file__).with_name("data.jsonl").read_text().splitlines() if line.strip()]
    tp = fp = fn = tn = 0
    errors = unknown = 0
    t0 = time.perf_counter()
    for row in data:
        text, want = row["text"], row["label"].lower()
        try:
            raw = classify(args.prompt, text, args.model, args.temperature)
        except (urllib.error.URLError, KeyError, IndexError) as exc:
            errors += 1
            raw = ""
        got = parse_label(raw)
        if got == "unknown":
            unknown += 1
        if got == "spam" and want == "spam":
            tp += 1
        elif got == "spam" and want == "ham":
            fp += 1
        elif got == "ham" and want == "spam":
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / len(data)

    print(json.dumps({
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "unknown_replies": unknown,
        "api_errors": errors,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
    }))


if __name__ == "__main__":
    main()
