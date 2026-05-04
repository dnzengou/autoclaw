# Autoclaw Project Summary

## Overview

Autoclaw is a **no-code self-improving automation loop** for Claude Cowork, built in Rust and inspired by Karpathy's autoresearch pattern. It enables AI agents to autonomously iterate on code while humans guide the direction through a simple markdown context file.

## Key Features

### Core Capabilities
- **Human-AI Loop**: Human edits `context.md`, AI edits `train.py`
- **Time-Budgeted Experiments**: Fixed 300s per run for fair comparison
- **Git Integration**: Auto-commit improvements, revert regressions
- **Multi-dimensional Evaluation**: Configurable rubric with weighted scoring
- **Real-time Dashboard**: Web UI with live updates via WebSocket
- **Event Triggers**: Automated actions based on experiment results

### No-Code Interface
- Context editor with syntax highlighting
- One-click start/stop for agent loops
- Visual experiment history and metrics
- Real-time score charts
- Hypothesis queue management

## Project Structure

```
autoclaw/
├── src/                          # Rust core
│   ├── main.rs                   # CLI entry point
│   ├── lib.rs                    # Module exports
│   ├── agent.rs                  # Agent loop orchestration
│   ├── context.rs                # Context.md management
│   ├── eval.rs                   # Evaluation engine
│   ├── git.rs                    # Git operations
│   ├── harness.rs                # Claude API integration
│   ├── metrics.rs                # Metrics collection
│   ├── server.rs                 # HTTP API + dashboard
│   ├── state.rs                  # Persistence
│   ├── triggers.rs               # Event automation
│   ├── telemetry.rs              # Logging
│   ├── init.rs                   # Project initialization
│   └── deploy.rs                 # Deployment helpers
├── ui/                           # React dashboard
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── MetricsCard.tsx
│   │   │   ├── ExperimentList.tsx
│   │   │   ├── ContextEditor.tsx
│   │   │   └── Chart.tsx
│   │   └── hooks/
│   │       └── useWebSocket.ts
│   ├── package.json
│   ├── vite.config.ts
│   └── index.html
├── templates/                    # Starter templates
│   ├── CONTEXT_TEMPLATE.md
│   ├── CONTEXT_CAVEMAN.md
│   └── EVAL_RUBRIC.json
├── docs/                         # Documentation
│   ├── ARCHITECTURE.md
│   ├── CLAUDE_COWORK_INTEGRATION.md
│   └── ADOPTION_RETENTION_MONETIZATION.md
├── Cargo.toml                    # Rust dependencies
├── Dockerfile                    # Container build
├── docker-compose.yml            # Full stack deployment
├── fly.toml                      # Fly.io config
├── railway.json                  # Railway config
├── render.yaml                   # Render config
├── prometheus.yml                # Metrics scraping
└── README.md                     # Main documentation
```

## Quick Start

```bash
# Install
curl -fsSL https://autoclaw.dev/install.sh | sh

# Initialize
autoclaw init my-project
cd my-project

# Edit context (your job)
vim context.md

# Start loop (AI's job)
autoclaw run

# View dashboard
autoclaw server
open http://localhost:8080
```

## Architecture Highlights

### Agent Loop Flow
```
1. Load context.md
2. Generate hypothesis (Claude)
3. Generate code changes (Claude)
4. Apply changes to train.py
5. Run evaluation (300s budget)
6. Score against rubric
7. Commit if improved / Revert if regressed
8. Update context with learnings
9. Repeat
```

### Key Design Decisions

1. **Single File Target** (`train.py`)
   - Keeps scope manageable
   - Diffs are reviewable
   - Reduces cognitive load

2. **Fixed Time Budget** (300s)
   - Experiments comparable across hardware
   - Prevents runaway training
   - ~12 experiments/hour

3. **Context-Driven**
   - Human controls direction
   - AI accumulates learnings
   - Token-efficient (Caveman Talks style)

4. **Git-Native**
   - Every experiment is a commit
   - Easy rollback
   - Full history

## Metrics & Growth

### Adoption Targets
- Signup Conversion: ≥ 50%
- First Loop Completion: ≥ 40%
- Activation Rate: ≥ 15%
- FTTV: < 5 minutes

### Retention Targets
- Day-1: 55%
- Day-7: 35%
- Day-30: 20%

### Monetization Targets
- Free → Paid: 8-12%
- LTV/CAC: 3:1
- Gross Margin: ≥ 70%

## Deployment Options

### Docker Compose (Recommended)
```bash
docker-compose up -d
```
Includes: Autoclaw + Prometheus + Grafana

### Fly.io
```bash
autoclaw deploy fly
```

### Railway
```bash
autoclaw deploy railway
```

### Render
```bash
autoclaw deploy render
```

## API Reference

### REST Endpoints
```
GET  /api/status
POST /api/start
POST /api/stop
GET  /api/experiments
GET  /api/metrics
GET  /api/best
GET  /api/context
POST /api/context
WS   /ws
```

### WebSocket Events
```json
{ "type": "experiment_start", "data": {...} }
{ "type": "experiment_complete", "data": {...} }
{ "type": "improvement", "data": {...} }
{ "type": "metrics_update", "data": {...} }
```

## Caveman Talks Context Format

Ultra-minimal token usage:

```markdown
# AUTOCALW

## MISSION
Self-improving loop. Human: context. AI: code. Repeat.

## CONSTRAINTS
- Budget: 300s
- Metric: val_bpb ↓
- Target: train.py

## STATE
- Best: N/A
- Iter: 0

## HYPOTHESES
1. lr 0.001→0.003
2. dropout 0.1

## LEARNINGS
<!-- AI adds -->

## WIN
- val_bpb < 2.0
- 10 iter no crash
```

## Comparison

| Feature | Autoclaw | Karpathy | Manus |
|---------|----------|----------|-------|
| No-code UI | ✓ | ✗ | Partial |
| Self-hosted | ✓ | ✓ | ✗ |
| Claude integration | ✓ | ✓ | ✗ |
| Git versioning | ✓ | ✓ | ? |
| Web dashboard | ✓ | ✗ | ✓ |
| Open source | ✓ | ✓ | ✗ |
| Rust performance | ✓ | ✗ | ? |

## Roadmap

### Completed
- [x] Core agent loop
- [x] Git integration
- [x] Web dashboard
- [x] Claude harness
- [x] Eval rubric system
- [x] Event triggers
- [x] Docker deployment

### In Progress
- [ ] Multi-agent support
- [ ] Plugin system
- [ ] Mobile app

### Future
- [ ] Distributed training
- [ ] Auto-context optimization
- [ ] Community leaderboard

## Credits

- Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch)
- Built for [Claude Cowork](https://claude.ai)
- Powered by Rust + Tokio + React

## License

MIT
