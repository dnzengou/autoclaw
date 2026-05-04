# Autoclaw — Meta-Prompt

## Context

This meta-prompt generates an **Autoclaw-style self-improving AI automation loop** — a system where an AI agent autonomously iterates on training/optimization code while a human guides direction via a simple markdown file. Based on Karpathy's autoresearch pattern.

## Core Pattern

```
Human edits context.md → AI generates hypotheses → experiments run automatically → results feed back → loop repeats
```

## Architecture

```
Human (context.md) ←→ Agent (Rust/Python) ←→ LLM API ←→ train.py / optimize.py
       ↑                                                    ↓
       └────────────── Git History ←────────────────────────┘
```

### Components

| Component | Purpose |
|-----------|---------|
| **Agent Loop** | Core orchestration (Rust with Tokio, or Python) |
| **Context Engine** | Markdown parser — human-AI protocol via `context.md` |
| **Eval Engine** | JSON rubric — experiment scoring |
| **Git Ops** | Git CLI — every experiment is a commit; improvements kept, regressions reverted |
| **Dashboard** | Web UI — live metrics, charts, experiment tracking |
| **LLM Harness** | API integration — hypothesis generation |

## Data Model

Each experiment is a JSON object:

```json
{
  "id": "string — unique experiment ID (e.g. exp-001)",
  "hypothesis": "string — what the AI hypothesized to try",
  "metrics": {
    "accuracy": 0.0,
    "loss": 0.0,
    "training_time": 0.0,
    "budget_used": 0.0
  },
  "status": "running | completed | failed | reverted",
  "timestamp": "ISO 8601 timestamp",
  "git_hash": "string — commit hash",
  "context_snapshot": "string — context.md at time of experiment",
  "score": 0.0
}
```

## Features to Generate

### Core Loop
1. **Context-Driven** — Human writes goals/constraints in `context.md`; AI reads it to generate hypotheses
2. **Hypothesis Generation** — AI proposes N experiments based on context + past results
3. **Time-Budgeted Execution** — Each experiment runs for a fixed duration (configurable)
4. **Evaluation** — Experiments scored against a JSON rubric
5. **Git-Native** — Every experiment auto-commits; improvements kept, regressions reverted
6. **Feedback Loop** — Results feed back into context for next iteration

### Dashboard (Web UI)
- Live experiment tracking with real-time updates (SSE or WebSocket)
- Metrics charts (accuracy, loss over experiments)
- Experiment history table with sortable columns
- Context.md editor (in-browser)
- Run/stop controls
- Budget tracking (time/money spent)

### Configuration
- `--budget <seconds>` — total experiment budget
- `--skills <path>` — load specialized skill files
- `--model <model>` — LLM model to use
- `--eval-rubric <path>` — custom scoring criteria

## Visual Design Suggestions
- Dark theme (slate-900 background)
- Accent color: orange or teal
- Status badges: green (completed), yellow (running), red (failed), gray (reverted)
- Metric cards at top (total experiments, best score, budget remaining)
- Real-time sparkline charts

## Reusable Template Pattern

### Directory Structure
```
my-project/
├── context.md          # Human writes goals here
├── train.py            # Training/optimization script
├── eval.py             # Evaluation script
├── experiments/        # Auto-generated experiment outputs
│   ├── exp-001/
│   ├── exp-002/
│   └── ...
├── results.json        # Accumulated experiment results
├── rubric.json         # Scoring criteria
└── .git/               # Git history (auto-committed)
```

### Agent Loop Pseudocode
```
1. Read context.md
2. Read results.json (past experiments)
3. Call LLM with context + results → generate N hypotheses
4. For each hypothesis:
   a. Create experiment directory
   b. Run train.py with hypothesis params
   c. Run eval.py on output
   d. Score against rubric
   e. Git commit (message = hypothesis)
   f. Append to results.json
5. Update dashboard
6. GOTO 1 (until budget exhausted)
```

## How to Adapt for Other Domains

1. **Replace the training script** — swap `train.py` for any optimization target (e.g., hyperparameter tuning, prompt engineering, code generation, data pipeline tuning)
2. **Replace the rubric** — change scoring criteria to match your domain
3. **Replace the context format** — adapt `context.md` structure for your problem space
4. **Replace the dashboard** — swap metrics and charts to show relevant KPIs
5. **Replace the LLM harness** — swap Claude for GPT, Gemini, local models, etc.

## Prompt Template

```
Build a self-improving automation loop system based on the Autoclaw pattern.

Core concept: Human edits a context markdown file → AI generates hypotheses →
experiments run automatically → results feed back → loop repeats.

### System Requirements

1. **Agent Loop** — Core orchestration that:
   - Reads `context.md` (human-written goals/constraints)
   - Reads past experiment results from `results.json`
   - Calls an LLM API to generate N hypotheses based on context + history
   - Executes each hypothesis as an experiment (runs a training/optimization script)
   - Scores results against a JSON rubric
   - Git-commits each experiment (message = hypothesis)
   - Loops until budget is exhausted

2. **Context Engine** — Parse a markdown file where humans specify:
   - Goal: what to optimize
   - Constraints: time, compute, budget limits
   - Preferences: what to prioritize
   - Notes: observations from past experiments

3. **Eval Engine** — JSON rubric for scoring experiments:
   - Primary metric (e.g., accuracy, loss)
   - Secondary metrics
   - Weighting between metrics
   - Pass/fail thresholds

4. **Git Operations** — Auto-commit each experiment:
   - Improvements kept (merge to main)
   - Regressions reverted (auto-revert commit)
   - Experiment history preserved

5. **Dashboard** — Real-time web UI:
   - Live experiment feed (SSE/WebSocket)
   - Metrics charts (line chart of scores over experiments)
   - Experiment table (sortable: ID, hypothesis, score, status, timestamp)
   - Context.md editor
   - Run/stop controls
   - Budget timer

6. **Configuration**:
   - `--budget <seconds>` total experiment time budget
   - `--skills <path>` load specialized skill/knowledge files
   - `--model <model>` LLM model selection
   - `--eval-rubric <path>` custom scoring rubric

### Directory Structure
```
project/
├── context.md
├── train.py
├── eval.py
├── experiments/
├── results.json
├── rubric.json
└── .git/
```

### Data Model
Each experiment record:
- id: unique identifier
- hypothesis: what was tested
- metrics: { primary_metric, secondary_metrics }
- status: running/completed/failed/reverted
- timestamp: ISO 8601
- git_hash: commit reference
- score: numeric score from rubric

### Visual Design
- Dark theme
- Professional data dashboard aesthetic
- Status badges with colors
- Real-time updating
- Responsive layout

Generate the complete implementation: agent loop code, dashboard HTML with embedded CSS/JS, and configuration templates.
```
