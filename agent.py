#!/usr/bin/env python3
"""Autoclaw Agent Loop — self-improving AI experiment orchestrator.

Usage:
    python agent.py [--budget 300] [--model claude-3-opus] [--hypotheses 3]
                    [--port 8080] [--rubric rubric.json]

The loop:
    1. Read context.md (human goals)
    2. Read results.json (past experiments)
    3. Call LLM → generate N hypotheses
    4. For each hypothesis: run train.py → eval.py → git commit → log result
    5. Update dashboard via SSE
    6. Loop until budget exhausted
"""
import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
CONTEXT_FILE = BASE_DIR / "context.md"
RESULTS_FILE = BASE_DIR / "results.json"
RUBRIC_FILE = BASE_DIR / "rubric.json"
TRAIN_SCRIPT = BASE_DIR / "train.py"
EVAL_SCRIPT = BASE_DIR / "eval.py"
EXPERIMENTS_DIR = BASE_DIR / "experiments"

# SSE clients
sse_clients = []
sse_lock = threading.Lock()

# Experiment state
running = False
stop_flag = threading.Event()
results = []
next_exp_id = 1
budget_remaining = 0
start_time = 0
best_score = 0.0


# ─── LLM Harness ─────────────────────────────────────────────────────────────

def call_llm(prompt, model="claude-3-opus"):
    """Call an LLM API to generate hypotheses.

    Supports: Claude (Anthropic), GPT (OpenAI), or local models.
    Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or LOCAL_LLM_URL env vars.

    Falls back to a heuristic hypothesis generator if no API key is available.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")

    if api_key and os.environ.get("ANTHROPIC_API_KEY"):
        return _call_claude(prompt, model)
    elif api_key and os.environ.get("OPENAI_API_KEY"):
        return _call_openai(prompt, model)
    else:
        # Fallback always returns a JSON string so downstream parsers
        # can treat call_llm() as text uniformly.
        return json.dumps(_fallback_hypotheses())


def _call_claude(prompt, model):
    """Call Anthropic Claude API."""
    import urllib.request
    import urllib.error

    api_key = os.environ["ANTHROPIC_API_KEY"]
    data = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
            return body["content"][0]["text"]
    except Exception as e:
        print(f"[agent] Claude API error: {e}", file=sys.stderr)
        return json.dumps(_fallback_hypotheses())


def _call_openai(prompt, model):
    """Call OpenAI API."""
    import urllib.request
    import urllib.error

    api_key = os.environ["OPENAI_API_KEY"]
    data = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
            return body["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[agent] OpenAI API error: {e}", file=sys.stderr)
        return json.dumps(_fallback_hypotheses())


def _fallback_hypotheses():
    """Heuristic hypothesis generator when no LLM API is configured."""
    context = _read_context()
    past = _read_results()

    # Extract previous lr values tried
    tried_lrs = set()
    for r in past:
        params = r.get("params", {})
        if "lr" in params:
            tried_lrs.add(params["lr"])

    # Generate diverse hypotheses based on context
    hypotheses = []

    if 2e-5 not in tried_lrs:
        hypotheses.append({
            "hypothesis": "Try learning rate 2e-5 with linear warmup (10% of steps)",
            "params": {"lr": 2e-5, "warmup_ratio": 0.1, "batch_size": 16, "epochs": 3}
        })

    if 3e-5 not in tried_lrs:
        hypotheses.append({
            "hypothesis": "Increase learning rate to 3e-5 with cosine decay schedule",
            "params": {"lr": 3e-5, "scheduler": "cosine", "batch_size": 16, "epochs": 3}
        })

    if 1e-5 not in tried_lrs:
        hypotheses.append({
            "hypothesis": "Decrease learning rate to 1e-5 for more stable convergence",
            "params": {"lr": 1e-5, "batch_size": 16, "epochs": 4}
        })

    # Data augmentation hypothesis
    hypotheses.append({
        "hypothesis": "Add random word dropout augmentation (rate=0.1) during training",
        "params": {"lr": 2e-5, "batch_size": 16, "epochs": 3, "augmentation": "word_dropout", "aug_rate": 0.1}
    })

    # Batch size experiment
    hypotheses.append({
        "hypothesis": "Increase batch size to 32 for more stable gradient estimates",
        "params": {"lr": 2e-5, "batch_size": 32, "epochs": 3}
    })

    return hypotheses[:3]


# ─── Context & Results I/O ──────────────────────────────────────────────────

def _read_context():
    if CONTEXT_FILE.exists():
        return CONTEXT_FILE.read_text()
    return "# Context\n\n## Goal\nNo goal set.\n"


def _read_results():
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def _save_results(results_list):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results_list, f, indent=2)


def _read_rubric():
    if RUBRIC_FILE.exists():
        with open(RUBRIC_FILE) as f:
            return json.load(f)
    return {
        "primary_metric": "f1_score",
        "higher_is_better": True,
        "weights": {"f1_score": 1.0},
        "pass_threshold": 0.0,
        "fail_threshold": -0.05
    }


# ─── Git Operations ──────────────────────────────────────────────────────────

def git_init():
    """Init git repo if not already one."""
    if not (BASE_DIR / ".git").exists():
        subprocess.run(["git", "init"], cwd=BASE_DIR, capture_output=True)
        subprocess.run(["git", "config", "user.email", "autoclaw@local"], cwd=BASE_DIR, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Autoclaw Agent"], cwd=BASE_DIR, capture_output=True)
        # Initial commit
        subprocess.run(["git", "add", "-A"], cwd=BASE_DIR, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial state"], cwd=BASE_DIR, capture_output=True)


def git_commit(exp_id, hypothesis):
    """Commit experiment results."""
    result = subprocess.run(
        ["git", "add", "-A"],
        cwd=BASE_DIR, capture_output=True
    )
    msg = f"[{exp_id}] {hypothesis[:80]}"
    result = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=BASE_DIR, capture_output=True
    )
    return result.returncode == 0


def git_revert():
    """Revert last commit (for failed experiments)."""
    subprocess.run(["git", "revert", "--no-edit", "HEAD"], cwd=BASE_DIR, capture_output=True)


def git_tag(tag):
    """Tag current commit."""
    subprocess.run(["git", "tag", "-f", tag], cwd=BASE_DIR, capture_output=True)


def git_hash():
    """Get current commit hash."""
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=BASE_DIR, capture_output=True, text=True
    )
    return result.stdout.strip()


# ─── Experiment Runner ───────────────────────────────────────────────────────

def run_experiment(hypothesis, params, rubric, *,
                   parent_id=None, refinement_depth=0,
                   critique=None, refinement_strategy=None):
    """Run a single experiment: train → eval → score → commit.

    Optional lineage kwargs (all default to falsy → elided from result JSON):
      parent_id: the experiment this refines, if any
      refinement_depth: 0 for fresh hypotheses, N for the Nth refinement in a chain
      critique / refinement_strategy: LLM's rationale for the refinement
    """
    global best_score, next_exp_id

    exp_id = f"exp-{next_exp_id:03d}"
    next_exp_id += 1
    exp_dir = EXPERIMENTS_DIR / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    lineage_tag = f" (refines {parent_id}, depth {refinement_depth})" if parent_id else ""
    print(f"\n{'='*60}")
    print(f"[agent] Running {exp_id}{lineage_tag}: {hypothesis}")
    print(f"[agent] Params: {json.dumps(params)}")
    print(f"{'='*60}")

    # Build train command. Keep param names as-is — train scripts declare
    # them with underscores (e.g. --batch_size), so the previous underscore-
    # to-dash mangling produced flags the trainer didn't recognize.
    cmd = [sys.executable, str(TRAIN_SCRIPT), "--output_dir", str(exp_dir)]
    for k, v in params.items():
        cmd.append(f"--{k}")
        cmd.append(str(v))

    # Run training
    start = time.time()
    try:
        train_result = subprocess.run(
            cmd, cwd=BASE_DIR, capture_output=True, text=True, timeout=120
        )
        duration = time.time() - start
    except subprocess.TimeoutExpired:
        print(f"[agent] {exp_id}: TIMEOUT after 120s")
        return _make_result(exp_id, hypothesis, params, {"error": "timeout"}, 0.0,
                           "failed", duration=120,
                           parent_id=parent_id, refinement_depth=refinement_depth,
                           critique=critique, refinement_strategy=refinement_strategy)

    if train_result.returncode != 0:
        print(f"[agent] {exp_id}: train.py failed:\n{train_result.stderr[:500]}")
        return _make_result(exp_id, hypothesis, params, {"error": "train_failed"}, 0.0,
                           "failed", duration=time.time() - start,
                           parent_id=parent_id, refinement_depth=refinement_depth,
                           critique=critique, refinement_strategy=refinement_strategy)

    # Parse train output for metrics
    try:
        metrics = json.loads(train_result.stdout.strip())
    except json.JSONDecodeError:
        print(f"[agent] {exp_id}: Could not parse train output:\n{train_result.stdout[:500]}")
        metrics = {"error": "parse_failed"}

    # Save metrics to experiment dir
    with open(exp_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # Save params
    with open(exp_dir / "params.json", "w") as f:
        json.dump({"hypothesis": hypothesis, "params": params}, f, indent=2)

    # Run eval
    eval_result = subprocess.run(
        [sys.executable, str(EVAL_SCRIPT)],
        cwd=BASE_DIR, capture_output=True, text=True
    )

    score = 0.0
    if eval_result.returncode == 0:
        try:
            eval_data = json.loads(eval_result.stdout)
            score = eval_data.get("score", 0.0)
        except json.JSONDecodeError:
            pass

    # Compute fallback score if eval didn't produce one
    if score == 0.0 and "error" not in metrics:
        primary = rubric["primary_metric"]
        if primary in metrics:
            score = metrics[primary]

    status = "completed"
    if rubric.get("fail_threshold") is not None:
        if rubric["higher_is_better"] and score < best_score + rubric["fail_threshold"]:
            status = "reverted"
        elif not rubric["higher_is_better"] and score > best_score - rubric["fail_threshold"]:
            status = "reverted"

    result = _make_result(exp_id, hypothesis, params, metrics, score, status, duration,
                          parent_id=parent_id, refinement_depth=refinement_depth,
                          critique=critique, refinement_strategy=refinement_strategy)

    # Git operations
    git_commit(exp_id, hypothesis)
    result["git_hash"] = git_hash()

    if status == "reverted":
        print(f"[agent] {exp_id}: Score {score:.4f} below threshold, reverting")
        git_revert()
        result["git_hash"] = git_hash()

    if score > best_score:
        best_score = score
        git_tag(f"best-{exp_id}")
        print(f"[agent] {exp_id}: NEW BEST! Score: {score:.4f}")

    return result


def _make_result(exp_id, hypothesis, params, metrics, score, status, duration, *,
                 parent_id=None, refinement_depth=0,
                 critique=None, refinement_strategy=None):
    result = {
        "id": exp_id,
        "hypothesis": hypothesis,
        "params": params,
        "metrics": metrics,
        "score": round(score, 4),
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_hash": "",
        "duration_seconds": round(duration, 1)
    }
    # Lineage fields — elided when null/zero so old consumers stay unchanged.
    if parent_id:
        result["parent_id"] = parent_id
    if refinement_depth:
        result["refinement_depth"] = refinement_depth
    if critique:
        result["critique"] = critique
    if refinement_strategy:
        result["refinement_strategy"] = refinement_strategy
    return result


# ─── Iterative Refinement (Run → Evaluate → Improve → Run) ──────────────────

def _should_refine(experiment, best, budget_left, args):
    """MCTS-style gate: only expand promising branches."""
    if experiment["status"] in ("failed", "reverted"):
        return False
    if budget_left <= args.min_refinement_budget:
        return False
    # First-ever hypothesis (best is still 0.0) always earns a chance;
    # afterwards, prune branches that fall too far below the current best.
    if best > 0.0 and experiment["score"] < best - args.refinement_gap:
        return False
    return True


def _build_refinement_prompt(parent, rubric, best):
    context = _read_context()
    return f"""You are refining a previous experiment.

## Goal (from context.md)
{context}

## Rubric
Primary metric: {rubric['primary_metric']} (higher is better: {rubric['higher_is_better']})
Best score so far: {best:.4f}

## Previous experiment
Hypothesis: {parent['hypothesis']}
Params:     {json.dumps(parent['params'])}
Metrics:    {json.dumps(parent.get('metrics', {}))}
Score:      {parent['score']:.4f}
Depth:      {parent.get('refinement_depth', 0)}

## Your task
1. CRITIQUE the previous attempt in one sentence (what likely capped the score).
2. Propose ONE targeted refinement: change 1-2 params, keep the rest.
3. Explain in one sentence WHY this change should help.

Return ONLY valid JSON in this exact shape:
{{"critique": "...", "refinement_strategy": "...", "params": {{"lr": 2e-5, "batch_size": 16, "epochs": 3}}}}
"""


def _parse_refinement(text):
    """Extract {critique, refinement_strategy, params} from LLM output."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "params" not in data:
        return None
    return {
        "critique": str(data.get("critique", "")).strip(),
        "refinement_strategy": str(data.get("refinement_strategy", "")).strip(),
        "params": data["params"] if isinstance(data["params"], dict) else {},
    }


def _fallback_refinement(parent):
    """Heuristic refinement when no LLM API is configured.

    Perturb the numeric param with the largest current value up or down by 20%,
    alternating direction by parent depth. Enough to smoke-test the wiring.
    """
    params = dict(parent.get("params", {}))
    if not params:
        return None
    numeric = {k: v for k, v in params.items() if isinstance(v, (int, float))}
    if not numeric:
        return None
    target_key = max(numeric, key=lambda k: abs(numeric[k]))
    direction = 1 if parent.get("refinement_depth", 0) % 2 == 0 else -1
    old = numeric[target_key]
    new = old * (1 + 0.2 * direction)
    # Preserve int-ness for batch_size / epochs etc.
    if isinstance(old, int):
        new = max(1, int(round(new)))
    params[target_key] = new
    return {
        "critique": f"Score {parent['score']:.4f} suggests {target_key}={old} may be sub-optimal.",
        "refinement_strategy": f"Perturb {target_key}: {old} -> {new}",
        "params": params,
    }


def refine_experiment(parent, rubric, args):
    """Produce and run one refinement of `parent`. Returns the new experiment
    or None if the LLM/heuristic declines or output can't be parsed.
    """
    prompt = _build_refinement_prompt(parent, rubric, best_score)
    model = args.refinement_model or args.model

    have_api_key = bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
    )
    refinement = None
    if have_api_key:
        llm_out = call_llm(prompt, model)
        # call_llm may return a list (fallback hypotheses) or a str (LLM text).
        if isinstance(llm_out, str):
            refinement = _parse_refinement(llm_out)

    if refinement is None:
        refinement = _fallback_refinement(parent)
    if refinement is None:
        return None

    hypothesis = f"[refine {parent['id']}] {refinement['refinement_strategy']}"
    return run_experiment(
        hypothesis,
        refinement["params"],
        rubric,
        parent_id=parent["id"],
        refinement_depth=parent.get("refinement_depth", 0) + 1,
        critique=refinement["critique"],
        refinement_strategy=refinement["refinement_strategy"],
    )


# ─── Main Loop ───────────────────────────────────────────────────────────────

def main_loop(args):
    """Main experiment loop — runs until budget exhausted or stop signal."""
    global running, results, budget_remaining, start_time, best_score

    rubric = _read_rubric()
    results = _read_results()
    budget_remaining = args.budget
    start_time = time.time()

    # Find best score from past results
    if results:
        best_score = max(r.get("score", 0.0) for r in results)
    else:
        best_score = 0.0

    # Initialize git
    git_init()

    iteration = 0
    while not stop_flag.is_set() and budget_remaining > 0:
        iteration += 1
        context = _read_context()

        # Build LLM prompt
        past_summary = _summarize_results(results[-10:])  # last 10
        prompt = f"""You are an AI research scientist running experiments to optimize a model.

## Context (human's goals and constraints)
{context}

## Past Experiment Results (last {len(results)} experiments)
{past_summary}

## Current Best Score: {best_score:.4f}

Generate {args.hypotheses} distinct hypotheses for the next experiments.
Each hypothesis must include specific parameter changes.

Return ONLY a JSON array of objects with keys: "hypothesis" (string) and "params" (dict).
Example:
[
  {{"hypothesis": "Increase learning rate to 3e-5 with cosine decay", "params": {{"lr": 3e-5, "scheduler": "cosine", "batch_size": 16, "epochs": 3}}}},
  {{"hypothesis": "Add dropout of 0.3 to prevent overfitting", "params": {{"lr": 2e-5, "dropout": 0.3, "batch_size": 16, "epochs": 3}}}}
]

Generate {args.hypotheses} hypotheses now:"""

        print(f"\n[agent] Iteration {iteration} — Generating hypotheses...")
        llm_output = call_llm(prompt, args.model)

        # Parse hypotheses
        hypotheses = _parse_hypotheses(llm_output)
        if not hypotheses:
            print(f"[agent] Could not parse hypotheses from LLM output, stopping.")
            break

        print(f"[agent] Generated {len(hypotheses)} hypotheses")

        # Run each hypothesis
        for h in hypotheses:
            if stop_flag.is_set() or budget_remaining <= 0:
                break

            exp_start = time.time()
            result = run_experiment(
                h.get("hypothesis", "Unknown"),
                h.get("params", {}),
                rubric
            )

            # Update budget
            elapsed = time.time() - exp_start
            budget_remaining -= elapsed
            result["budget_remaining"] = round(budget_remaining, 1)

            # Append to results
            results.append(result)
            _save_results(results)

            # Push to dashboard
            _broadcast_sse(result)

            print(f"[agent] {result['id']}: score={result['score']:.4f}, "
                  f"status={result['status']}, budget_left={budget_remaining:.1f}s")

            # Iterative refinement chain: Run → Evaluate → Improve → Run again.
            # Selective / MCTS-style — only expand branches that pass _should_refine.
            current = result
            prev_score = None
            for depth in range(1, args.max_refinement_depth + 1):
                if stop_flag.is_set() or budget_remaining <= 0:
                    break
                if current["score"] >= args.target_score:
                    print(f"[agent] {current['id']}: target {args.target_score} reached, ending chain")
                    break
                if not _should_refine(current, best_score, budget_remaining, args):
                    break
                if prev_score is not None and abs(current["score"] - prev_score) < args.plateau_tolerance:
                    print(f"[agent] {current['id']}: score plateaued (delta<{args.plateau_tolerance}), ending chain")
                    break
                prev_score = current["score"]

                refine_start = time.time()
                refined = refine_experiment(current, rubric, args)
                if refined is None:
                    print(f"[agent] {current['id']}: refinement declined, ending chain")
                    break
                budget_remaining -= (time.time() - refine_start)
                refined["budget_remaining"] = round(budget_remaining, 1)

                results.append(refined)
                _save_results(results)
                _broadcast_sse(refined)

                print(f"[agent] {refined['id']} (depth {depth}): "
                      f"score={refined['score']:.4f}, status={refined['status']}, "
                      f"budget_left={budget_remaining:.1f}s")
                current = refined

        # Brief pause before next iteration
        time.sleep(1)

    running = False
    total_duration = time.time() - start_time
    print(f"\n[agent] Loop finished. {len(results)} experiments in {total_duration:.1f}s")
    _broadcast_sse({"type": "done", "total_experiments": len(results), "duration": total_duration})


def _summarize_results(results_list):
    """Format results for LLM prompt."""
    if not results_list:
        return "No past experiments."
    lines = []
    for r in results_list[-10:]:
        score = r.get("score", 0.0)
        status = r.get("status", "unknown")
        hypo = r.get("hypothesis", "?")[:60]
        lines.append(f"  [{r['id']}] {hypo} → score={score:.4f} ({status})")
    return "\n".join(lines)


def _parse_hypotheses(text):
    """Extract hypothesis JSON from LLM output."""
    # Try to find JSON array
    match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Try parsing entire output as JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Fallback
    return []


# ─── SSE Dashboard Push ──────────────────────────────────────────────────────

def _broadcast_sse(data):
    """Push experiment result to all SSE dashboard clients."""
    with sse_lock:
        dead = []
        for client in sse_clients:
            try:
                client[0].write(f"data: {json.dumps(data)}\n\n".encode())
                client[0].flush()
            except Exception:
                dead.append(client)
        for d in dead:
            sse_clients.remove(d)


# ─── HTTP Server (Dashboard + API) ──────────────────────────────────────────

class AutoclawHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress logs

    def do_GET(self):
        if self.path == "/":
            self._serve_dashboard()
        elif self.path == "/events":
            self._handle_sse()
        elif self.path == "/api/results":
            self._serve_json(results)
        elif self.path == "/api/status":
            self._serve_status()
        elif self.path == "/api/context":
            self._serve_text(_read_context())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode() if content_len else ""

        if self.path == "/api/start":
            self._handle_start()
        elif self.path == "/api/stop":
            self._handle_stop()
        elif self.path == "/api/context":
            self._handle_update_context(body)
        elif self.path == "/api/reset":
            self._handle_reset()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_dashboard(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        dashboard_path = BASE_DIR / "dashboard.html"
        if dashboard_path.exists():
            self.wfile.write(dashboard_path.read_bytes())
        else:
            self.wfile.write(b"<html><body><h1>Dashboard not found</h1></body></html>")

    def _handle_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        client = (self.wfile, self)
        with sse_lock:
            sse_clients.append(client)

        # Send existing results
        for r in results:
            try:
                self.wfile.write(f"data: {json.dumps(r)}\n\n".encode())
                self.wfile.flush()
            except Exception:
                break

        # Keep connection open
        try:
            while not stop_flag.is_set():
                time.sleep(1)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with sse_lock:
                if client in sse_clients:
                    sse_clients.remove(client)

    def _serve_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _serve_status(self):
        status_data = {
            "running": running,
            "total_experiments": len(results),
            "best_score": best_score,
            "budget_remaining": round(budget_remaining, 1),
            "uptime": round(time.time() - start_time, 1) if start_time else 0
        }
        self._serve_json(status_data)

    def _serve_text(self, text):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(text.encode())

    def _handle_start(self):
        global running
        if not running:
            running = True
            stop_flag.clear()
            t = threading.Thread(target=main_loop, args=(args,), daemon=True)
            t.start()
            self._serve_json({"status": "started"})
        else:
            self._serve_json({"status": "already_running"})

    def _handle_stop(self):
        global running
        stop_flag.set()
        running = False
        self._serve_json({"status": "stopped"})

    def _handle_update_context(self, body):
        with open(CONTEXT_FILE, "w") as f:
            f.write(body)
        self._serve_json({"status": "updated"})

    def _handle_reset(self):
        global results, next_exp_id, best_score, budget_remaining
        results = []
        next_exp_id = 1
        best_score = 0.0
        budget_remaining = args.budget
        _save_results([])
        self._serve_json({"status": "reset"})


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    global args

    parser = argparse.ArgumentParser(description="Autoclaw Agent Loop")
    parser.add_argument("--budget", type=int, default=300,
                       help="Total experiment budget in seconds")
    parser.add_argument("--model", type=str, default="claude-3-opus",
                       help="LLM model for hypothesis generation")
    parser.add_argument("--hypotheses", type=int, default=3,
                       help="Hypotheses per iteration")
    parser.add_argument("--port", type=int, default=8080,
                       help="Dashboard HTTP port")
    parser.add_argument("--rubric", type=str, default="rubric.json",
                       help="Path to scoring rubric")
    parser.add_argument("--no-dashboard", action="store_true",
                       help="Run without dashboard server")
    # Iterative refinement (Run → Evaluate → Improve → Run again)
    parser.add_argument("--max-refinement-depth", type=int, default=3,
                       help="Max depth of the refinement chain per hypothesis (0 disables)")
    parser.add_argument("--plateau-tolerance", type=float, default=0.005,
                       help="Stop a refinement chain when |delta score| falls below this")
    parser.add_argument("--target-score", type=float, default=1.0,
                       help="Stop a refinement chain once this score is reached")
    parser.add_argument("--refinement-gap", type=float, default=0.03,
                       help="Only refine if experiment.score >= best_score - gap")
    parser.add_argument("--min-refinement-budget", type=float, default=5.0,
                       help="Skip refinement when budget_remaining <= this (seconds)")
    parser.add_argument("--refinement-model", type=str, default=None,
                       help="Optional model just for critique/refinement (defaults to --model)")
    args = parser.parse_args()

    # Ensure directories exist
    EXPERIMENTS_DIR.mkdir(exist_ok=True)

    # Load existing results
    global results
    results = _read_results()
    if results:
        global next_exp_id, best_score
        next_exp_id = max(int(r["id"].split("-")[1]) for r in results) + 1
        best_score = max(r.get("score", 0.0) for r in results)

    # Start dashboard server
    if not args.no_dashboard:
        server = HTTPServer(("0.0.0.0", args.port), AutoclawHTTPHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        print(f"[agent] Dashboard: http://localhost:{args.port}")
        print(f"[agent] SSE:       http://localhost:{args.port}/events")
        print(f"[agent] API:       http://localhost:{args.port}/api/results")

    print(f"[agent] Autoclaw Agent Loop ready")
    print(f"[agent] Budget: {args.budget}s | Model: {args.model} | Hypotheses/iter: {args.hypotheses}")
    print(f"[agent] Past experiments loaded: {len(results)}")
    print(f"[agent] Type 'start' to begin, 'stop' to halt, 'status' to check, 'quit' to exit.")

    # Interactive CLI
    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd == "start":
                if not running:
                    running = True
                    stop_flag.clear()
                    t = threading.Thread(target=main_loop, args=(args,), daemon=True)
                    t.start()
                    print("[agent] Loop started.")
                else:
                    print("[agent] Already running.")
            elif cmd == "stop":
                stop_flag.set()
                print("[agent] Stop signal sent.")
            elif cmd == "status":
                print(f"  Running: {running}")
                print(f"  Experiments: {len(results)}")
                print(f"  Best score: {best_score:.4f}")
                print(f"  Budget remaining: {budget_remaining:.1f}s")
            elif cmd == "quit":
                stop_flag.set()
                print("[agent] Shutting down.")
                break
            elif cmd:
                print(f"Unknown command: {cmd}")
    except (EOFError, KeyboardInterrupt):
        stop_flag.set()
        print("\n[agent] Shutting down.")


if __name__ == "__main__":
    main()
