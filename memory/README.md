# Memory — persistent user + session + org memory (Layer 2)

Three tiers, one SQLite file, stdlib only.

| Tier | Table | Lifetime | Example |
|---|---|---|---|
| **Personal** | `personal_memory` | Forever, per-user | Preferences, contact info, standing instructions |
| **Session** | `session_memory` | Per-conversation, summarized when >N turns | Current chat's rolling context |
| **Organizational** | `org_memory` | Team-shared, versioned | SOPs, decisions, contract terms, glossary |

## Quick start

```bash
python memory/manager.py add personal "user_name" "Eugene Nzengou"
python memory/manager.py add personal "tz" "Europe/Stockholm"
python memory/manager.py add org "escalation_policy" "SEV1 pages Bob; SEV2+ Slack #ops"

# Recall
python memory/manager.py get personal user_name
python memory/manager.py list org

# Session (used by chat loop; automatic rolling summary)
python memory/manager.py session-add "user said their name is Eugene"
python memory/manager.py session-context  # returns rolling summary
```

## Files

- `schema.sql` — three tables + indexes; single-file SQLite DB
- `manager.py` — CRUD API + rolling summarization when session exceeds threshold
- `memory.sqlite` — the store (gitignored)

## How the orchestrator uses it

`agents/orchestrator.py` prepends personal + org memory to every LLM call. The
session table gets appended after each turn; when it exceeds
`MEMORY_SESSION_MAX_TURNS` (default 20), the manager summarizes the oldest
N-half turns into one condensed entry and prunes them — bounded context, no
runaway growth.

## Privacy

All rows carry `owner` (defaults to `$USER`), `created_at`, and `updated_at`.
Set `AUTOCLAW_MEMORY_ENCRYPTED=1` to enable SQLCipher (requires
`pysqlcipher3`; off by default to keep zero-deps guarantee).

## See also

- `../rag/` — vector search over documents (episodic/semantic)
- `../agents/orchestrator.py` — how memory is threaded into every agent turn
- `../docs/PRIVATE_AI_OS.md`
