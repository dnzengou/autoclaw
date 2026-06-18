# Autoclaw Diagrams

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AUTOCALW SYSTEM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐                                                           │
│   │    HUMAN     │◄─────────────────────────────────────────────────────┐    │
│   │   (Editor)   │                                                     │    │
│   └──────┬───────┘                                                     │    │
│          │ Edit context.md                                             │    │
│          ▼                                                             │    │
│   ┌────────────────────────────────────────────────────────────────┐   │    │
│   │                      CONTEXT ENGINE                             │   │    │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │    │
│   │  │   MISSION   │  │ CONSTRAINTS │  │    HYPOTHESIS QUEUE     │ │   │    │
│   │  │  (immutable)│  │ (immutable) │  │    (human-edited)       │ │   │    │
│   │  └─────────────┘  └─────────────┘  └─────────────────────────┘ │   │    │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │    │
│   │  │CURRENT STATE│  │  LEARNINGS  │  │         TOOLS           │ │   │    │
│   │  │(auto-update)│  │(AI-appended)│  │   (available actions)   │ │   │    │
│   │  └─────────────┘  └─────────────┘  └─────────────────────────┘ │   │    │
│   └────────────────────────────────────────────────────────────────┘   │    │
│          │                                                             │    │
│          │ Read context                                                │    │
│          ▼                                                             │    │
│   ┌────────────────────────────────────────────────────────────────┐   │    │
│   │                     CLAUDE HARNESS                              │   │    │
│   │                                                                 │   │    │
│   │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │   │    │
│   │  │  1. Generate    │───▶│  2. Generate    │───▶│  3. Apply   │ │   │    │
│   │  │   Hypothesis    │    │  Code Changes   │    │   Changes   │ │   │    │
│   │  └─────────────────┘    └─────────────────┘    └──────┬──────┘ │   │    │
│   │                                                       │        │   │    │
│   └───────────────────────────────────────────────────────┼────────┘   │    │
│                                                           │            │    │
│                                                           ▼            │    │
│   ┌────────────────────────────────────────────────────────────────┐   │    │
│   │                        AGENT LOOP                               │   │    │
│   │                                                                 │   │    │
│   │   for iteration in 0..max_iterations:                          │   │    │
│   │       experiment = run_experiment()                            │   │    │
│   │       result = evaluate(experiment)                            │   │    │
│   │       if result.is_improvement:                                │   │    │
│   │           git.commit(experiment)                               │   │    │
│   │           context.append_learning()                            │   │    │
│   │       else:                                                    │   │    │
│   │           git.revert()                                         │   │    │
│   │       check_triggers()                                         │   │    │
│   │                                                                 │   │    │
│   └────────────────────────────────────────────────────────────────┘   │    │
│          │                                                             │    │
│          │ Run experiment (300s budget)                                │    │
│          ▼                                                             │    │
│   ┌────────────────────────────────────────────────────────────────┐   │    │
│   │                      EVALUATION ENGINE                          │   │    │
│   │                                                                 │   │    │
│   │   score = Σ(criterion_score × weight) / Σ(weights)             │   │    │
│   │                                                                 │   │    │
│   │   Criteria:                                                     │   │    │
│   │   • validation_loss  (35%)  ──▶ lower_is_better                │   │    │
│   │   • training_speed   (10%)  ──▶ higher_is_better               │   │    │
│   │   • memory_efficiency(10%)  ──▶ range(0.7-0.95)                │   │    │
│   │   • code_quality     (10%)  ──▶ higher_is_better               │   │    │
│   │   • stability        (10%)  ──▶ exact_match                    │   │    │
│   │                                                                 │   │    │
│   └────────────────────────────────────────────────────────────────┘   │    │
│          │                                                             │    │
│          │ Commit / Revert                                             │    │
│          ▼                                                             │    │
│   ┌────────────────────────────────────────────────────────────────┐   │    │
│   │                       GIT OPERATIONS                            │   │    │
│   │                                                                 │   │    │
│   │   Branch: autoclaw-{uuid}                                       │   │    │
│   │                                                                 │   │    │
│   │   Commit Format:                                                │   │    │
│   │   ─────────────────────────────────────────                     │   │    │
│   │   autoclaw: iteration N - [improvement|experiment]              │   │    │
│   │                                                                 │   │    │
│   │   Score: X.XXXX                                                 │   │    │
│   │   Hypothesis: [text]                                            │   │    │
│   │   ─────────────────────────────────────────                     │   │    │
│   │                                                                 │   │    │
│   └────────────────────────────────────────────────────────────────┘   │    │
│          │                                                             │    │
│          │ Update learnings                                            │    │
│          └─────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  Human  │────▶│ Context │────▶│ Claude  │────▶│  Code   │────▶│  Eval   │
│  (Edit) │     │   .md   │     │  (API)  │     │ Changes │     │ (Score) │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └────┬────┘
     ▲                                                                │
     │                                                                │
     │         ┌─────────┐     ┌─────────┐     ┌─────────┐           │
     └─────────│ Learnings│◀────│   Git   │◀────│ Improved│◀──────────┘
               │ (Append) │     │ (Commit)│     │  Score  │
               └─────────┘     └─────────┘     └─────────┘
```

## Deployment Options

### Docker Compose (Full Stack)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Network                            │
│                                                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────────┐ │
│  │   Autoclaw    │  │   Prometheus  │  │      Grafana        │ │
│  │    Server     │  │    (Metrics)  │  │    (Dashboard)      │ │
│  │   :8080       │  │    :9090      │  │     :3000           │ │
│  │               │  │               │  │                     │ │
│  │ ┌───────────┐ │  │               │  │                     │ │
│  │ │  Agent    │ │  │               │  │                     │ │
│  │ │  Loop     │ │  │               │  │                     │ │
│  │ └───────────┘ │  │               │  │                     │ │
│  │ ┌───────────┐ │  │               │  │                     │ │
│  │ │  Context  │ │  │               │  │                     │ │
│  │ │  Engine   │ │  │               │  │                     │ │
│  │ └───────────┘ │  │               │  │                     │ │
│  │ ┌───────────┐ │  │               │  │                     │ │
│  │ │   Eval    │ │  │               │  │                     │ │
│  │ │  Engine   │ │  │               │  │                     │ │
│  │ └───────────┘ │  │               │  │                     │ │
│  └───────┬───────┘  └───────┬───────┘  └─────────┬───────────┘ │
│          │                  │                    │             │
│          └──────────────────┴────────────────────┘             │
│                     (Shared Volumes)                            │
└─────────────────────────────────────────────────────────────────┘
```

### Fly.io (Single Container)

```
┌─────────────────────────────────────┐
│           Fly.io App                 │
│                                      │
│  ┌─────────────────────────────┐    │
│  │      Autoclaw Server         │    │
│  │         :8080                │    │
│  │                              │    │
│  │  ┌─────┐ ┌─────┐ ┌───────┐  │    │
│  │  │Agent│ │Eval │ │Context│  │    │
│  │  └─────┘ └─────┘ └───────┘  │    │
│  │                              │    │
│  │  ┌───────────────────────┐  │    │
│  │  │     Persistent Disk    │  │    │
│  │  │   (context.md, git)    │  │    │
│  │  └───────────────────────┘  │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

## API Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      API SERVER (:8080)                          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  REST API                                               │    │
│  │  ─────────────────                                      │    │
│  │  GET    /api/status      → Agent status                 │    │
│  │  POST   /api/start       → Start agent                  │    │
│  │  POST   /api/stop        → Stop agent                   │    │
│  │  GET    /api/experiments → List experiments             │    │
│  │  GET    /api/metrics     → Metrics snapshot             │    │
│  │  GET    /api/best        → Best result                  │    │
│  │  GET    /api/context     → Get context.md               │    │
│  │  POST   /api/context     → Update context.md            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  WebSocket (/ws)                                        │    │
│  │  ─────────────────                                      │    │
│  │  experiment_start    → { id, iteration }                │    │
│  │  experiment_complete → { id, score, duration }          │    │
│  │  improvement         → { id, score, previous }          │    │
│  │  metrics_update      → { experiments_total, ... }       │    │
│  │  error               → { message }                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Prometheus Metrics                                     │    │
│  │  ─────────────────                                      │    │
│  │  GET /api/metrics/prometheus                            │    │
│  │  → autoclaw_experiments_total                           │    │
│  │  → autoclaw_experiments_successful                      │    │
│  │  → autoclaw_current_iteration                           │    │
│  │  → autoclaw_experiment_score_bucket                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Growth Funnel

```
┌─────────────────────────────────────────────────────────────────┐
│                        ADOPTION FUNNEL                           │
│                                                                  │
│  ┌─────────────┐                                                │
│  │  Discovery  │ 100%                                           │
│  │  (Traffic)  │                                                │
│  └──────┬──────┘                                                │
│         │ 60% conversion                                        │
│         ▼                                                       │
│  ┌─────────────┐                                                │
│  │   Signup    │ 60%                                            │
│  │ (GitHub OAuth)│                                              │
│  └──────┬──────┘                                                │
│         │ 40% conversion                                        │
│         ▼                                                       │
│  ┌─────────────┐                                                │
│  │ First Loop  │ 40%                                            │
│  │  (autoclaw  │                                                │
│  │   init &&   │                                                │
│  │   run)      │                                                │
│  └──────┬──────┘                                                │
│         │ 25% conversion                                        │
│         ▼                                                       │
│  ┌─────────────┐                                                │
│  │  First Win  │ 25%                                            │
│  │ (improvement │                                                │
│  │   found)    │                                                │
│  └──────┬──────┘                                                │
│         │ 15% conversion                                        │
│         ▼                                                       │
│  ┌─────────────┐                                                │
│  │ Activation  │ 15% ✓ TARGET MET                               │
│  │ (3+ loops)  │                                                │
│  └─────────────┘                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Retention Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                      RETENTION ENGINE                            │
│                                                                  │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐             │
│   │   Run    │─────▶│   See    │─────▶│  Update  │             │
│   │   Loop   │      │  Result  │      │ Context  │             │
│   └──────────┘      └──────────┘      └────┬─────┘             │
│        ▲                                   │                    │
│        │                                   │                    │
│        └───────────────────────────────────┘                    │
│                                                                  │
│   Habit Drivers:                                                 │
│   • Morning digest email                                         │
│   • Slack notification on improvement                            │
│   • Weekly progress report                                       │
│   • Monthly optimization suggestions                             │
│                                                                  │
│   Churn Prevention:                                              │
│   • Day 3: "Need help?"                                          │
│   • Day 7: Example contexts                                      │
│   • Day 14: Onboarding call offer                                │
│   • Day 30: Win-back discount                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Monetization Tiers

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRICING STRUCTURE                            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  FREE (Starter)                                         │    │
│  │  ─────────────                                          │    │
│  │  • 10 loops/month                                       │    │
│  │  • 1 project                                            │    │
│  │  • 300s budget                                          │    │
│  │  • Community support                                    │    │
│  │                                                         │    │
│  │  Conversion trigger: Limit hit                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼ 8-12% conversion                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  PRO ($29/month)                                        │    │
│  │  ───────────────                                        │    │
│  │  • Unlimited loops                                      │    │
│  │  • 5 projects                                           │    │
│  │  • 600s budget                                          │    │
│  │  • Priority support                                     │    │
│  │  • Advanced metrics                                     │    │
│  │  • Team sharing                                         │    │
│  │                                                         │    │
│  │  Conversion trigger: Team growth                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼ 20% upsell                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ENTERPRISE ($199/month)                                │    │
│  │  ───────────────────────                                │    │
│  │  • Unlimited everything                                 │    │
│  │  • Custom budgets                                       │    │
│  │  • Private infrastructure                               │    │
│  │  • SLA guarantee                                        │    │
│  │  • Dedicated support                                    │    │
│  │  • SSO/SAML                                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
