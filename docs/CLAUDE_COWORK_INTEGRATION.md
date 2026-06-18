# Claude Cowork Integration

## Overview
Autoclaw integrates with Claude Cowork (Claude Code) to provide a no-code self-improving automation loop.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Claude Cowork  │────▶│  Autoclaw API   │────▶│  Agent Loop     │
│  (Human UI)     │◀────│  (Orchestrator) │◀────│  (AI Worker)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  context.md     │     │  Git Repository │     │  train.py       │
│  (Human edits)  │     │  (Versioning)   │     │  (AI edits)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Integration Points

### 1. Context Sync
Claude Cowork reads/writes `context.md` for human-AI communication:

```typescript
// Claude Cowork extension
interface AutoclawContext {
  readContext(): Promise<string>;
  updateSection(section: string, content: string): Promise<void>;
  appendLearning(learning: string): Promise<void>;
}
```

### 2. Agent Control
Start/stop agent loops from Claude Cowork:

```typescript
interface AutoclawAgent {
  start(config: AgentConfig): Promise<string>; // Returns runId
  stop(runId: string): Promise<void>;
  getStatus(runId: string): Promise<AgentStatus>;
  getExperiments(runId: string): Promise<Experiment[]>;
}
```

### 3. Real-time Updates
WebSocket connection for live experiment updates:

```typescript
interface AutoclawEvents {
  onExperimentStart: (exp: Experiment) => void;
  onExperimentComplete: (exp: Experiment) => void;
  onImprovement: (exp: Experiment) => void;
  onError: (error: string) => void;
}
```

## Claude Cowork Commands

### `/autoclaw init`
Initialize new Autoclaw project in current directory.

### `/autoclaw start`
Start agent loop with current context.

### `/autoclaw status`
Show current agent status and recent experiments.

### `/autoclaw stop`
Stop running agent loop.

### `/autoclaw context <section>`
Edit specific context section (mission, constraints, hypotheses).

### `/autoclaw best`
Show best experiment result and diff.

### `/autoclaw deploy <target>`
Deploy to fly/docker/railway/render.

## Configuration

Create `.claude/autoclaw.json`:

```json
{
  "apiUrl": "http://localhost:8080",
  "defaultBudget": 300,
  "autoCommit": true,
  "notifications": {
    "onImprovement": true,
    "onError": true,
    "onComplete": false
  }
}
```

## MCP Server

Autoclaw exposes an MCP (Model Context Protocol) server:

```typescript
// tools/list
{
  "tools": [
    {
      "name": "autoclaw_start",
      "description": "Start Autoclaw agent loop",
      "inputSchema": { ... }
    },
    {
      "name": "autoclaw_status", 
      "description": "Get agent status",
      "inputSchema": { ... }
    },
    {
      "name": "autoclaw_update_context",
      "description": "Update context.md section",
      "inputSchema": { ... }
    }
  ]
}
```

## Example Workflow

1. **Initialize**: `/autoclaw init`
2. **Edit Context**: `/autoclaw context mission`
3. **Start Loop**: `/autoclaw start --budget 300`
4. **Monitor**: Watch experiments in real-time
5. **Review**: `/autoclaw best` to see top result
6. **Iterate**: Update context based on learnings
7. **Deploy**: `/autoclaw deploy fly`

## Security

- API key stored in Claude Cowork secrets
- Git credentials via SSH agent
- No code execution on host (sandboxed)
