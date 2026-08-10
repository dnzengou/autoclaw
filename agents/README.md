# Agents — plan / validate / approve / execute / audit (Layer 4)

The AI OS is not a chatbot. It **does work**, safely.

## The 5-step loop

```
plan   ← LLM proposes an action (tool call + args + rationale)
validate ← check against policies.yaml (allow/deny by tool + arg patterns)
approve  ← if action is in the "human-approval" category, block until user Y/n
execute  ← run the tool; capture stdout/stderr/exit code
audit    ← append to .autoclaw/audit.jsonl (input, plan, decision, output)
```

Every action is auditable. Nothing sensitive fires without explicit approval.

## Agents

- **`research_agent.py`** — RAG-backed Q&A. Reads `context.md` + queries `rag/`,
  synthesizes a cited answer via BitNet. Read-only; no approval needed.
- **`ops_agent.py`** — inbox summarize + GitHub issues triage + web fetch. All
  external-write actions gated on approval.
- **`orchestrator.py`** — top-level dispatcher. Picks the right agent from the
  user's request, threads memory in, runs the 5-step loop.

## Files

- `orchestrator.py` — the 5-step loop + tool dispatch + audit sink
- `research_agent.py` — RAG-backed research
- `ops_agent.py` — connectors (email, github, web)
- `policies.yaml` — allow/deny rules (which tools require approval)
- `tools.py` — tool registry (name → callable + schema)
- `audit.py` — JSONL audit writer

## Quick start

```bash
# Research (no approval needed)
python agents/orchestrator.py research "what were the main findings in Q3 reports?"

# Ops (approval prompt on send-email / create-issue)
python agents/orchestrator.py ops "summarize unread email and draft replies to the vendor thread"

# Programmatic
python -c "
from agents.orchestrator import Orchestrator
o = Orchestrator()
print(o.run('research', 'What did we decide about the auth refactor?'))
"
```

## Policies

`policies.yaml` controls which tools can run auto vs need approval:

```yaml
auto:
  - rag.query
  - memory.get
  - memory.session-add
  - web.fetch
  - email.list_inbox
  - github.list_issues
approval:
  - email.send
  - github.create_issue
  - github.create_pr
  - shell.exec       # never, unless explicitly overridden
deny:
  - shell.rm_rf
  - shell.dd
```

Per-tool arg patterns can further restrict — e.g., `web.fetch` may be denied
for private-IP ranges. See `orchestrator.py::validate_action()`.

## Audit format

`.autoclaw/audit.jsonl` — one line per action:

```json
{"ts":"2026-08-10T15:00:00Z","agent":"ops","tool":"email.send","args":{...},"decision":"approved","approver":"user","exit":0,"stdout_hash":"sha256:..."}
```

Feed this into a SIEM (Splunk / Elastic / Datadog) for enterprise deployments.

## See also

- `../rag/` — knowledge engine used by research_agent
- `../connectors/` — email + web fetch (used by ops_agent)
- `../memory/` — persistent context threaded into every LLM call
- `../deals.go` — the Go-side approval pattern this Python loop mirrors
