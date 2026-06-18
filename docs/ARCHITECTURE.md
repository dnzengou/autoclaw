# Autoclaw Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           AUTOCALW SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────┐ │
│  │   Human     │───▶│   Context   │───▶│   Claude    │───▶│  Agent   │ │
│  │  (Editor)   │◀───│    (.md)    │◀───│  (Harness)  │◀───│  (Loop)  │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └────┬─────┘ │
│       ▲                                                        │       │
│       │                    ┌─────────────┐                      │       │
│       └────────────────────│   Git Ops   │◀─────────────────────┘       │
│                            │  (Version)  │                              │
│                            └──────┬──────┘                              │
│                                   │                                      │
│                            ┌──────▼──────┐                              │
│                            │   Eval      │                              │
│                            │  (Rubric)   │                              │
│                            └─────────────┘                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Agent Loop (`src/agent.rs`)

The heart of Autoclaw. Orchestrates the self-improvement cycle:

```rust
pub struct AgentLoop {
    config: AgentConfig,
    context: Arc<RwLock<ContextEngine>>,
    eval: Arc<EvalEngine>,
    git: Arc<GitOps>,
    harness: Arc<ClaudeHarness>,
    // ...
}
```

**Flow:**
1. Load context from `context.md`
2. Generate hypothesis via Claude
3. Generate code changes
4. Apply changes to `train.py`
5. Run evaluation (time-budgeted)
6. Score result against rubric
7. Commit if improved, revert if regressed
8. Update context with learnings
9. Repeat

### 2. Context Engine (`src/context.rs`)

Manages human-AI communication via `context.md`:

**Sections:**
- `MISSION` - What we're building (immutable)
- `CONSTRAINTS` - Rules and limits (immutable)
- `CURRENT STATE` - Latest metrics (auto-updated)
- `HYPOTHESIS QUEUE` - What to try next (human-edited)
- `LEARNINGS` - Accumulated knowledge (AI-appended)
- `TOOLS` - Available capabilities

**Token Management:**
- Auto-compresses when context exceeds limit
- Summarizes old learnings
- Prioritizes recent experiments

### 3. Eval Engine (`src/eval.rs`)

Multi-dimensional scoring system:

**Default Criteria:**
| Criterion | Weight | Target | Type |
|-----------|--------|--------|------|
| validation_loss | 0.35 | 2.0 | lower_is_better |
| training_speed | 0.10 | 10000 | higher_is_better |
| memory_efficiency | 0.10 | 0.85 | range(0.7-0.95) |
| code_quality | 0.10 | 0.9 | higher_is_better |
| stability | 0.10 | 1.0 | exact_match |

**Scoring:**
```rust
score = Σ(criterion_score × weight) / Σ(weights)
```

### 4. Git Ops (`src/git.rs`)

Version control for experiments:

**Features:**
- Auto-create feature branches (`autoclaw-*`)
- Commit improvements with metadata
- Revert regressions automatically
- Experiment history tracking
- Diff generation

**Commit Format:**
```
autoclaw: iteration N - [improvement|experiment]

Score: X.XXXX
Hypothesis: [hypothesis text]
```

### 5. Claude Harness (`src/harness.rs`)

Claude API integration:

**Prompts:**
1. **Hypothesis Generation** - Given context, propose testable hypothesis
2. **Code Generation** - Given hypothesis, generate minimal code changes
3. **Result Analysis** - Given experiment history, suggest next steps

**Tools Available:**
- `read_file` - Read file contents
- `write_file` - Write file contents
- `execute_shell` - Run shell commands
- `git_commit` - Commit changes

### 6. State Manager (`src/state.rs`)

Persistence layer:

**Stored:**
- Last iteration number
- Best experiment ID and score
- Total runtime
- Current git branch
- Custom metadata

**Location:** `.autoclaw/state.json`

### 7. Trigger Engine (`src/triggers.rs`)

Event-based automation:

**Default Triggers:**
| Trigger | Condition | Action |
|---------|-----------|--------|
| excellent_score | score > 0.9 | notify + checkpoint |
| no_improvement_50 | 50 iters no improvement | update context |
| checkpoint_hourly | every hour | save checkpoint |

**Custom Triggers:**
```json
{
  "id": "my_trigger",
  "trigger_type": "score_threshold",
  "threshold": 0.8,
  "actions": ["notify", "webhook"]
}
```

## Data Flow

```
1. Human edits context.md
          │
          ▼
2. Agent reads context
          │
          ▼
3. Claude generates hypothesis
          │
          ▼
4. Claude generates code changes
          │
          ▼
5. Agent applies changes to train.py
          │
          ▼
6. Agent runs evaluation (300s budget)
          │
          ▼
7. Eval engine scores result
          │
          ▼
8. If improved: git commit
   If regressed: git revert
          │
          ▼
9. Context updated with learnings
          │
          ▼
10. Loop repeats
```

## API Design

### REST Endpoints

```
GET  /api/status
→ { is_running: bool, total_experiments: int, best_score: float }

POST /api/start
← { context_path?, budget_seconds?, headless? }
→ { success: bool, message: string }

POST /api/stop
→ { success: bool }

GET  /api/experiments
→ { success: bool, data: Experiment[] }

GET  /api/experiments/:id
→ { success: bool, data: Experiment }

GET  /api/metrics
→ { success: bool, data: MetricsStorage }

GET  /api/metrics/prometheus
→ Prometheus format metrics

GET  /api/best
→ { success: bool, data: EvalResult }

GET  /api/context
→ { success: bool, data: { content: string } }

POST /api/context
← { content: string }
→ { success: bool }
```

### WebSocket Events

```json
// Experiment started
{ "type": "experiment_start", "data": { "id": "...", "iteration": 1 } }

// Experiment completed
{ "type": "experiment_complete", "data": { "id": "...", "score": 2.1 } }

// Improvement found
{ "type": "improvement", "data": { "id": "...", "score": 1.9, "previous": 2.1 } }

// Metrics update
{ "type": "metrics_update", "data": { "experiments_total": 10, ... } }

// Error
{ "type": "error", "data": { "message": "..." } }
```

## Deployment Architecture

### Single Node

```
┌─────────────────────────────────────┐
│           Autoclaw Server            │
│  ┌─────────┐  ┌─────────┐  ┌─────┐ │
│  │  API    │  │  Agent  │  │ Git │ │
│  └────┬────┘  └────┬────┘  └──┬──┘ │
│       │            │          │    │
│       └────────────┴──────────┘    │
│                   │                │
│              ┌────┴────┐           │
│              │  Files  │           │
│              └─────────┘           │
└─────────────────────────────────────┘
```

### Docker Compose

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Autoclaw   │  │  Prometheus │  │   Grafana   │
│   Server    │  │   Metrics   │  │ Dashboards  │
└─────────────┘  └─────────────┘  └─────────────┘
```

## Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| API Latency | < 100ms | p99 response time |
| WebSocket | < 50ms | Event propagation |
| Git Ops | < 500ms | Commit/revert |
| Eval | < 5s | Scoring (excl. training) |
| Memory | < 512MB | RSS at steady state |

## Security Model

1. **API Keys** - Stored in environment, never logged
2. **Git Credentials** - Via SSH agent, no passwords
3. **Sandbox** - Code execution isolated
4. **No Network** - Training code can't access internet

## Monitoring

**Metrics Exported:**
- `autoclaw_experiments_total` - Counter
- `autoclaw_experiments_successful` - Counter
- `autoclaw_experiments_failed` - Counter
- `autoclaw_current_iteration` - Gauge
- `autoclaw_experiment_score` - Histogram
- `autoclaw_experiment_duration_ms` - Histogram

**Alerts:**
- Error rate > 1%
- No experiments in 1 hour
- Memory usage > 1GB
