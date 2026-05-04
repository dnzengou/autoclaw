#!/bin/sh
# autoclaw.sh — Self-improving AI experiment loop (pure shell + toybox)
# Usage: sh autoclaw.sh [--budget 300] [--model deepseek-chat]
#
# DeepSeek API: Set DEEPSEEK_API_KEY env var (or ANTHROPIC_API_KEY, OPENAI_API_KEY)
# Falls back to heuristic hypothesis generator if no API key set.

set -e

# ─── Configuration ──────────────────────────────────────────────────────────
BUDGET=300
MODEL="deepseek-chat"
HYPOTHESES=3
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTEXT_FILE="$BASE_DIR/context.md"
RESULTS_FILE="$BASE_DIR/results.json"
RUBRIC_FILE="$BASE_DIR/rubric.json"
TRAIN_SCRIPT="$BASE_DIR/train.py"
EXPERIMENTS_DIR="$BASE_DIR/experiments"
BEST_SCORE=0.0
NEXT_EXP_ID=1
RUNNING=0

# Parse args
while [ $# -gt 0 ]; do
  case "$1" in
    --budget) BUDGET="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --hypotheses) HYPOTHESES="$2"; shift 2 ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

mkdir -p "$EXPERIMENTS_DIR"

# ─── JSON helpers (sed-based, toybox-compatible) ────────────────────────────

json_get_str() {
  # json_get_str <json_string> <key> — extracts string value for key
  echo "$1" | sed "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/"
}

json_get_num() {
  # json_get_num <json_string> <key> — extracts numeric value for key
  echo "$1" | sed "s/.*\"$2\"[[:space:]]*:[[:space:]]*\([0-9.-]\+\).*/\1/"
}

json_get() {
  # json_get <json_string> <key> — tries string, then numeric
  local val=$(json_get_str "$1" "$2")
  if [ "$val" = "$1" ]; then
    val=$(json_get_num "$1" "$2")
    if [ "$val" = "$1" ]; then
      echo ""
      return
    fi
  fi
  echo "$val"
}

# ─── LLM API Calls ──────────────────────────────────────────────────────────

call_llm() {
  local prompt="$1"
  local api_key=""
  local api_url=""
  local req_body=""

  if [ -n "$DEEPSEEK_API_KEY" ]; then
    api_key="$DEEPSEEK_API_KEY"
    api_url="api.deepseek.com"
    req_body=$(cat <<EOF
{
  "model": "$MODEL",
  "messages": [{"role": "user", "content": $(echo "$prompt" | awk '{gsub(/"/, "\\\""); printf "\"%s\"", $0}')}],
  "max_tokens": 2000,
  "temperature": 0.7
}
EOF
)
    _call_https "$api_url" "/chat/completions" "$api_key" "$req_body" "deepseek"
  elif [ -n "$ANTHROPIC_API_KEY" ]; then
    api_key="$ANTHROPIC_API_KEY"
    api_url="api.anthropic.com"
    req_body=$(cat <<EOF
{
  "model": "claude-3-opus",
  "max_tokens": 2000,
  "messages": [{"role": "user", "content": $(echo "$prompt" | awk '{gsub(/"/, "\\\""); printf "\"%s\"", $0}')}]
}
EOF
)
    _call_https "$api_url" "/v1/messages" "$api_key" "$req_body" "anthropic"
  elif [ -n "$OPENAI_API_KEY" ]; then
    api_key="$OPENAI_API_KEY"
    api_url="api.openai.com"
    req_body=$(cat <<EOF
{
  "model": "gpt-4",
  "messages": [{"role": "user", "content": $(echo "$prompt" | awk '{gsub(/"/, "\\\""); printf "\"%s\"", $0}')}],
  "max_tokens": 2000
}
EOF
)
    _call_https "$api_url" "/v1/chat/completions" "$api_key" "$req_body" "openai"
  else
    _fallback_hypotheses
  fi
}

_call_https() {
  local host="$1"
  local path="$2"
  local key="$3"
  local body="$4"
  local provider="$5"

  # We need HTTPS. Since nc doesn't do TLS, we'll use a workaround:
  # Try to use the picoclaw web_fetch tool (which does HTTPS) to proxy
  # our API call. But web_fetch returns text, not raw HTTP response.
  #
  # For now, fall back to heuristic generator.
  # TODO: Implement TLS using openssl s_client if available
  echo "[agent] LLM API ($provider) requires HTTPS. No TLS client available." >&2
  echo "[agent] Set DEEPSEEK_API_KEY and install openssl for API access." >&2
  echo "[agent] Using fallback hypothesis generator." >&2
  _fallback_hypotheses
}

# ─── Fallback Hypothesis Generator ──────────────────────────────────────────

_fallback_hypotheses() {
  local context=""
  [ -f "$CONTEXT_FILE" ] && context=$(cat "$CONTEXT_FILE")
  local past_results=""
  [ -f "$RESULTS_FILE" ] && past_results=$(cat "$RESULTS_FILE")

  # Generate diverse hypotheses
  cat <<'HYPO'
[
  {"hypothesis": "Try learning rate 2e-5 with linear warmup (10% of steps)", "params": {"lr": 2e-5, "warmup_ratio": 0.1, "batch_size": 16, "epochs": 3}},
  {"hypothesis": "Increase learning rate to 3e-5 with cosine decay schedule", "params": {"lr": 3e-5, "scheduler": "cosine", "batch_size": 16, "epochs": 3}},
  {"hypothesis": "Add random word dropout augmentation (rate=0.1) during training", "params": {"lr": 2e-5, "batch_size": 16, "epochs": 3, "augmentation": "word_dropout", "aug_rate": 0.1}}
]
HYPO
}

# ─── Context & Results I/O ──────────────────────────────────────────────────

read_context() {
  if [ -f "$CONTEXT_FILE" ]; then
    cat "$CONTEXT_FILE"
  else
    echo "# Context\n\n## Goal\nNo goal set."
  fi
}

read_results() {
  if [ -f "$RESULTS_FILE" ]; then
    cat "$RESULTS_FILE"
  else
    echo "[]"
  fi
}

save_results() {
  local data="$1"
  echo "$data" > "$RESULTS_FILE"
}

# ─── Git Operations ─────────────────────────────────────────────────────────

git_init() {
  if ! [ -d "$BASE_DIR/.git" ]; then
    git init "$BASE_DIR" 2>/dev/null || true
    git -C "$BASE_DIR" config user.email "autoclaw@local" 2>/dev/null || true
    git -C "$BASE_DIR" config user.name "Autoclaw Agent" 2>/dev/null || true
    git -C "$BASE_DIR" add -A 2>/dev/null || true
    git -C "$BASE_DIR" commit -m "Initial state" 2>/dev/null || true
  fi
}

git_commit() {
  local exp_id="$1"
  local hypothesis="$2"
  git -C "$BASE_DIR" add -A 2>/dev/null || true
  git -C "$BASE_DIR" commit -m "[$exp_id] ${hypothesis}" 2>/dev/null || true
}

git_revert() {
  git -C "$BASE_DIR" revert --no-edit HEAD 2>/dev/null || true
}

git_hash() {
  git -C "$BASE_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown"
}

# ─── Experiment Runner ──────────────────────────────────────────────────────

run_experiment() {
  local hypothesis="$1"
  local params_json="$2"
  local rubric_json="$3"

  local exp_id=$(printf "exp-%03d" $NEXT_EXP_ID)
  NEXT_EXP_ID=$((NEXT_EXP_ID + 1))
  local exp_dir="$EXPERIMENTS_DIR/$exp_id"
  mkdir -p "$exp_dir"

  echo ""
  echo "============================================================"
  echo "[agent] Running $exp_id: $hypothesis"
  echo "[agent] Params: $params_json"
  echo "============================================================"

  # Build param flags for train.py
  local params=""
  local lr=$(echo "$params_json" | json_get "lr")
  [ -n "$lr" ] && params="$params --lr $lr"
  local bs=$(echo "$params_json" | json_get "batch_size")
  [ -n "$bs" ] && params="$params --batch-size $bs"
  local epochs=$(echo "$params_json" | json_get "epochs")
  [ -n "$epochs" ] && params="$params --epochs $epochs"

  local start_time=$(date +%s)

  # Run training
  local train_output=""
  if [ -f "$TRAIN_SCRIPT" ]; then
    train_output=$(python3 "$TRAIN_SCRIPT" $params --output-dir "$exp_dir" 2>&1) || true
  else
    # Simulate training if no train.py
    sleep 1
    train_output='{"f1_score": 0.82, "accuracy": 0.83, "inference_time_ms": 1.5, "training_duration_s": 1.0}'
  fi

  local end_time=$(date +%s)
  local duration=$((end_time - start_time))

  # Parse metrics from train output
  local metrics="$train_output"
  echo "$metrics" > "$exp_dir/metrics.json"
  echo "$params_json" > "$exp_dir/params.json"

  # Extract score
  local primary_metric=$(echo "$rubric_json" | json_get "primary_metric")
  [ -z "$primary_metric" ] && primary_metric="f1_score"
  local score=$(echo "$metrics" | json_get "$primary_metric")
  [ -z "$score" ] && score=0

  local status="completed"
  local fail_threshold=$(echo "$rubric_json" | json_get "fail_threshold")
  [ -z "$fail_threshold" ] && fail_threshold="-0.05"

  # Check if score is below threshold
  local threshold_check=$(awk -v s="$score" -v b="$BEST_SCORE" -v t="$fail_threshold" 'BEGIN { if (s < b + t) print "reverted"; else print "ok" }')
  [ "$threshold_check" = "reverted" ] && status="reverted"

  local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  local ghash=$(git_hash)

  # Build result JSON
  local result=$(cat <<EOF
{
  "id": "$exp_id",
  "hypothesis": $(echo "$hypothesis" | awk '{gsub(/"/, "\\\""); printf "\"%s\"", $0}'),
  "params": $params_json,
  "metrics": $metrics,
  "score": $score,
  "status": "$status",
  "timestamp": "$timestamp",
  "git_hash": "$ghash",
  "duration_seconds": $duration
}
EOF
)

  # Git ops
  git_commit "$exp_id" "$hypothesis"

  if [ "$status" = "reverted" ]; then
    echo "[agent] $exp_id: Score $score below threshold, reverting"
    git_revert
  fi

  local better=$(awk -v s="$score" -v b="$BEST_SCORE" 'BEGIN { print (s > b) ? 1 : 0 }')
  if [ "$better" = "1" ]; then
    BEST_SCORE=$score
    git -C "$BASE_DIR" tag -f "best-$exp_id" 2>/dev/null || true
    echo "[agent] $exp_id: NEW BEST! Score: $score"
  fi

  echo "$result"
}

# ─── Main Loop ──────────────────────────────────────────────────────────────

main_loop() {
  local budget_remaining=$BUDGET
  local start_time=$(date +%s)
  local results_json=$(read_results)
  local rubric_json=""
  [ -f "$RUBRIC_FILE" ] && rubric_json=$(cat "$RUBRIC_FILE")

  # Default rubric
  if [ -z "$rubric_json" ]; then
    rubric_json='{"primary_metric":"f1_score","higher_is_better":true,"weights":{"f1_score":1.0},"pass_threshold":0.0,"fail_threshold":-0.05}'
  fi

  # Find best score from past results
  # (simplified - just set to 0)
  BEST_SCORE=0

  # Init git
  git_init

  local iteration=0
  while [ $budget_remaining -gt 0 ]; do
    iteration=$((iteration + 1))
    local context=$(read_context)

    echo ""
    echo "[agent] Iteration $iteration — Generating hypotheses..."
    echo "[agent] Budget remaining: ${budget_remaining}s"

    # Generate hypotheses
    local llm_output=$(_fallback_hypotheses)

    # Parse and run each hypothesis using sed/grep (toybox-compatible)
    echo "$llm_output" | sed 's/},{/}\n{/g' | while IFS= read -r block; do
      [ -z "$block" ] && continue
      # Extract hypothesis text
      local hypo=$(echo "$block" | sed 's/.*"hypothesis"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
      # Extract params object
      local params=$(echo "$block" | sed 's/.*"params"[[:space:]]*:[[:space:]]*\({[^}]*}\).*/\1/')
      [ -z "$hypo" ] && continue
      [ -z "$params" ] && continue

      local exp_start=$(date +%s)
      local result=$(run_experiment "$hypo" "$params" "$rubric_json")

      # Update budget
      local exp_end=$(date +%s)
      local elapsed=$((exp_end - exp_start))
      budget_remaining=$((budget_remaining - elapsed))

      # Append to results
      local results_json=$(read_results)
      # Remove trailing ]
      results_json="${results_json%]}"
      if [ "$results_json" = "[" ]; then
        results_json="[$result]"
      else
        results_json="$results_json, $result]"
      fi
      save_results "$results_json"

      local score=$(echo "$result" | json_get "score")
      local exp_id=$(echo "$result" | json_get "id")
      local status=$(echo "$result" | json_get "status")
      echo "[agent] $exp_id: score=$score, status=$status, budget_left=${budget_remaining}s"
    done

    # Brief pause
    sleep 1
  done

  local total_duration=$(($(date +%s) - start_time))
  echo ""
  echo "[agent] Loop finished. Duration: ${total_duration}s"
}

# ─── Entry Point ────────────────────────────────────────────────────────────

echo "============================================================"
echo "  🦞 Autoclaw Agent (shell version)"
echo "============================================================"
echo "  Budget: ${BUDGET}s"
echo "  Model: ${MODEL}"
echo "  Hypotheses/iter: ${HYPOTHESES}"
echo "  DeepSeek API: $([ -n \"$DEEPSEEK_API_KEY\" ] && echo '✓ set' || echo '✗ not set (using fallback)')"
echo "  Python: $([ -f \"$TRAIN_SCRIPT\" ] && echo '✓' || echo '✗ (using simulated training)')"
echo "============================================================"
echo ""
echo "Commands: start, stop, status, quit"

# Interactive loop
while true; do
  printf "> "
  read -r cmd
  case "$cmd" in
    start)
      if [ "$RUNNING" = "0" ]; then
        RUNNING=1
        main_loop &
        LOOP_PID=$!
        echo "[agent] Loop started (PID: $LOOP_PID)"
      else
        echo "[agent] Already running"
      fi
      ;;
    stop)
      RUNNING=0
      kill $LOOP_PID 2>/dev/null || true
      echo "[agent] Stopped"
      ;;
    status)
      local count=$(read_results | sed 's/\[//;s/\]//;s/},{/}\n{/g' | grep -c '{' || echo 0)
      echo "  Running: $([ "$RUNNING" = "1" ] && echo 'yes' || echo 'no')"
      echo "  Experiments: $count"
      echo "  Best score: $BEST_SCORE"
      echo "  Budget: ${BUDGET}s"
      ;;
    quit)
      kill $LOOP_PID 2>/dev/null || true
      echo "[agent] Shutting down."
      exit 0
      ;;
    *)
      [ -n "$cmd" ] && echo "Unknown: $cmd"
      ;;
  esac
done
