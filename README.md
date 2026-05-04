# Autoclaw

> No-code self-improving automation loop for Claude Cowork. Based on Karpathy's autoresearch pattern.

## Quick Start

```bash
# Install
curl -fsSL https://autoclaw.dev/install.sh | sh

# Initialize project
autoclaw init my-project
cd my-project

# Edit context (your job)
vim context.md

# Start loop (AI's job)
autoclaw run

# Check results
autoclaw status
```

## How It Works

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Human      │─────▶│   Claude    │─────▶│   Agent     │
│  (context)  │      │   (harness) │      │   (code)    │
└─────────────┘      └─────────────┘      └──────┬──────┘
       ▲                                          │
       └──────────────────────────────────────────┘
                    (results feedback)
```

1. **Human** edits `context.md` - sets mission, constraints, hypotheses
2. **Claude** generates hypothesis and code changes
3. **Agent** runs experiment within time budget
4. **Eval** scores result against rubric
5. **Git** commits improvements, reverts regressions
6. **Loop** repeats indefinitely

## Core Concepts

### Context-Driven
Human controls direction via `context.md`:
- **MISSION**: What we're building
- **CONSTRAINTS**: Rules and limits
- **HYPOTHESIS QUEUE**: What to try next
- **LEARNINGS**: Accumulated knowledge (AI appends)

### Time-Budgeted
Every experiment runs for fixed time (default 300s):
- Comparable across hardware
- Prevents runaway experiments
- ~12 experiments/hour

### Metric-Driven
Single primary metric (lower validation loss = better):
- Fair comparison of all changes
- Architecture-agnostic
- Easy to understand

## Installation

### From Source (Rust)
```bash
git clone https://github.com/autoclaw/autoclaw
cd autoclaw
cargo build --release
sudo cp target/release/autoclaw /usr/local/bin
```

### Docker
```bash
docker run -p 8080:8080 autoclaw/autoclaw:latest
```

### Homebrew
```bash
brew install autoclaw/tap/autoclaw
```

## Usage

### CLI

```bash
# Initialize project
autoclaw init

# Start agent loop
autoclaw run --context context.md --budget 300

# Start API server
autoclaw server --port 8080

# Deploy
autoclaw deploy fly
```

### Configuration

Environment variables:
```bash
ANTHROPIC_API_KEY=sk-ant-...
AUTOCALW_BUDGET=300
AUTOCALW_CONTEXT=context.md
RUST_LOG=info
```

### Context Template

```markdown
# AUTOCALW CONTEXT

## MISSION
Build self-improving automation.

## CONSTRAINTS
- Time budget: 300s
- Metric: lower val_bpb

## CURRENT STATE
- Best: 2.45
- Iterations: 42

## HYPOTHESIS QUEUE
1. Increase learning rate
2. Add dropout

## LEARNINGS
<!-- AI appends here -->
```

## Architecture

### Components

| Component | Purpose | Language |
|-----------|---------|----------|
| `agent` | Main loop orchestration | Rust |
| `context` | Context.md management | Rust |
| `eval` | Scoring and rubrics | Rust |
| `git` | Version control | Rust |
| `harness` | Claude API integration | Rust |
| `server` | HTTP API + dashboard | Rust |
| `triggers` | Event-based automation | Rust |

### Data Flow

```
context.md → Claude → code changes → train.py → eval → git commit/rollback
```

## API

### REST Endpoints

```
GET  /api/status           - Agent status
POST /api/start            - Start agent
POST /api/stop             - Stop agent
GET  /api/experiments      - List experiments
GET  /api/experiments/:id  - Get experiment
GET  /api/metrics          - Metrics snapshot
GET  /api/best             - Best result
GET  /api/context          - Get context
POST /api/context          - Update context
WS   /ws                   - Real-time updates
```

### WebSocket Events

```json
{"type": "experiment_start", "data": {"id": "..."}}
{"type": "experiment_complete", "data": {"..."}}
{"type": "improvement", "data": {"score": 2.1}}
{"type": "metrics_update", "data": {"..."}}
```

## Deployment

### Fly.io
```bash
autoclaw deploy fly
```

### Docker
```bash
autoclaw deploy docker
docker run -p 8080:8080 autoclaw:latest
```

### Railway
```bash
autoclaw deploy railway
```

## Metrics & Analytics

### Adoption
- Activation Rate: 60% target
- FTTV: < 5 minutes

### Retention
- Day-1: 55%
- Day-7: 35%
- Day-30: 20%

### Monetization
- Free → Paid: 8-12%
- LTV/CAC: 3:1

## Comparison

| Feature | Autoclaw | Karpathy | Manus |
|---------|----------|----------|-------|
| No-code | ✓ | ✗ | Partial |
| Self-hosted | ✓ | ✓ | ✗ |
| Claude integration | ✓ | ✓ | ✗ |
| Git versioning | ✓ | ✓ | ? |
| Web dashboard | ✓ | ✗ | ✓ |
| Open source | ✓ | ✓ | ✗ |

## Roadmap

- [x] Core agent loop
- [x] Git integration
- [x] Web dashboard
- [x] Claude harness
- [ ] Multi-agent support
- [ ] Distributed training
- [ ] Plugin system
- [ ] Mobile app

## Contributing

```bash
git clone https://github.com/autoclaw/autoclaw
cd autoclaw
cargo test
cargo build
```

## License

MIT

## Credits

- Inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch)
- Built for [Claude Cowork](https://claude.ai)
- Powered by Rust + Tokio
