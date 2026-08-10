# Private AI OS — the story

> "The biggest opportunity is not another chatbot. It's a private AI operating layer
> that sits above all software and becomes the primary interface to work."

Autoclaw v0.6 assembles that layer, on-device, on CPU, with no cloud dependency.

## Six layers, one binary

```
                    ┌─────────────────────────────────┐
Layer 6 Governance  │ policies.yaml · audit.jsonl · RBAC · encryption │
                    ├─────────────────────────────────┤
Layer 5 Connectors  │ email (IMAP) · web · github · files │
                    ├─────────────────────────────────┤
Layer 4 Agents      │ research · ops · orchestrator (plan→validate→approve→execute→audit) │
                    ├─────────────────────────────────┤
Layer 3 Knowledge   │ rag/ · nomic-embed / bge / e5 · sqlite vector store │
                    ├─────────────────────────────────┤
Layer 2 Memory      │ personal_memory · session_memory (rolling summary) · org_memory │
                    ├─────────────────────────────────┤
Layer 1 Runtime     │ BitNet.cpp · llama-server /v1/chat/completions │
                    └─────────────────────────────────┘
                                     ↕
                              User (CLI / voice / HTTP)
```

Every layer is optional and swappable. You can run:

- **Just Layer 1** — you already have this since v0.5 (BitNet as an LLM backend).
- **Layers 1+3** — RAG-augmented chat, no persistent memory. Good for prototyping.
- **Layers 1+2+3+4** — the AI OS proper. Ships in v0.6.
- **All 6** — enterprise deployment with Docker, systemd hardening, audit-to-SIEM.

## Quick start

```bash
# 1. Install runtime + models (from v0.5)
./bitnet/setup.sh                              # ~800 MB (BitNet 2B)
./bitnet/serve.sh &                            # LLM on :8081

# 2. Install RAG + embedding model (new in v0.6)
./rag/setup.sh                                 # ~90 MB (nomic-embed 137M)
./rag/serve.sh &                               # embeddings on :8082

# 3. Ingest your knowledge
python autoclaw_os.py ingest ~/Documents/reports

# 4. Set some memory
python autoclaw_os.py memory add personal user_name "Eugene"
python autoclaw_os.py memory add org escalation_policy "SEV1 pages Bob; SEV2+ #ops"

# 5. Ask
python autoclaw_os.py research "what were the main findings in Q3?"
python autoclaw_os.py ops "summarize unread email and flag urgent ones"

# 6. Status
python autoclaw_os.py status
```

Or fire the whole stack at once:

```bash
python autoclaw_os.py serve                    # BitNet + RAG + agents
```

## ROI crosswalk — from the strategy doc to autoclaw features

| Top-ROI category (10 / 9.8 / 9.5 / 9 in the doc) | Autoclaw feature that delivers it |
|---|---|
| **1. Private Enterprise AI OS** — 10/10 | The whole stack (Layers 1–6). `autoclaw_os.py` unifies it. Runs on-prem, no data egress. |
| **2. Offline AI for Edge Devices** — 9.8/10 | `Dockerfile.bitnet` + `Dockerfile.aios` are `docker save`-able for air-gap transfer. BitNet is CPU-only, no GPU dep. `mobile/` (Tauri) wraps for Android/iOS. |
| **3. Knowledge Search / RAG / Digital Memory** — 9.5/10 | `rag/` (Layer 3) + `memory/` (Layer 2). Local semantic search + persistent user/org memory. |
| **4. Voice-First AI Agents** — 9/10 | `voice/` (from v0.5): whisper.cpp → BitNet → Piper, ~2–4 s/turn offline. |

## Industry-fit matrix — from the strategy doc

| Tier | Industry | Layers that matter most | Autoclaw fit |
|---|---|---|---|
| T1 | Energy / Utilities | 1, 4 (ops agent), 5 (connectors), 6 (audit) | ✓ |
| T1 | Manufacturing | 1, 4 (quality/maintenance agents), 5 (SCADA — future connector) | Partial (custom connector needed) |
| T1 | Defense / Security | 1, 6 (governance), Docker air-gap | ✓ (Dockerfile.bitnet is designed for this) |
| T2 | Healthcare | 1, 2 (patient context), 3 (knowledge), 6 (HIPAA audit) | ✓ |
| T2 | Logistics / Transport | 1 (edge devices), 5 (fleet connectors — future) | Partial |
| T2 | Mining / Oil / Gas | 1 (edge), 4 (ops), 5 (industrial — future connectors) | Partial |
| T3 | Law | 1, 3 (contract corpus), 4 (research agent) | ✓ (RAG + research_agent is the killer combo) |
| T3 | Finance | 1, 3, 4, 6 (audit) | ✓ |
| T3 | Consulting | 1, 3 (knowledge base), 4 (research agent) | ✓ |

## Install as standalone app (v0.6)

### macOS / Linux
```bash
brew install autoclaw/tap/autoclaw          # or: curl -fsSL autoclaw.dev/install.sh | sh -s -- --with-ai-os
autoclaw install-bitnet                      # LLM + model
autoclaw install-rag                         # embedding model
autoclaw-os serve                            # all layers
```

### Windows
```powershell
scoop install autoclaw
autoclaw install-bitnet
autoclaw install-rag
autoclaw-os serve
```

Register as a service:
```powershell
.\bitnet\windows\install-service.ps1        # BitNet as service
.\rag\windows\install-service.ps1           # RAG (same pattern; script pending)
```

### Docker (privacy edition — everything baked in)
```bash
docker build -f Dockerfile.aios -t autoclaw:aios .
docker run --rm -p 8080:8080 -p 8081:8081 -p 8082:8082 -p 8083:8083 \
  -v ~/aios-data:/data autoclaw:aios
```

Ports:
- `8080` — Go agent HTTP (dashboard + `/api/*` + `/events` SSE)
- `8081` — BitNet LLM (`/v1/chat/completions`)
- `8082` — RAG embeddings (`/v1/embeddings`)
- `8083` — Agent orchestrator HTTP (`/rag/ingest`, `/rag/query`, `/rag/status`)

Volume: `/data` holds `memory.sqlite`, `store.sqlite`, `audit.jsonl` — mount to
persist across restarts.

## Business model (from the strategy doc)

| Segment | Pricing | Deployment shape |
|---|---|---|
| **Consumer** — "your private executive assistant" | €10–30 / month | Brew install; runs on user's laptop |
| **SMB** — "AI Operating System for Teams" | €20–100 / user / month | Docker on office mini-PC or shared VM |
| **Enterprise** — "Private AI Infrastructure" | €100k–5M annual | Air-gapped Docker + Kubernetes; SIEM integration; SSO; custom connectors; support SLA |

The v0.6 codebase ships the technical foundation for all three tiers. What separates
them is deployment shape (personal / team / infra) and support / SSO / RBAC /
enterprise connectors — not core features.

## Roadmap (v0.7 and beyond)

**v0.7 — connector expansion**
- Microsoft Graph (Outlook, Teams, SharePoint, OneDrive) — OAuth flow
- Google Workspace (Gmail, Calendar, Drive)
- Slack (Web API)
- Salesforce (REST)

**v0.8 — governance & multi-tenant**
- RBAC via policy engine (per-user tool subsets)
- Audit-to-SIEM shippers (Splunk HEC, Elastic bulk, Datadog logs)
- Per-tenant model isolation (spawn one llama-server per tenant on demand)
- SQLCipher for `memory.sqlite` (opt-in)

**v0.9 — enterprise UI**
- Web UI for the AI OS (React shell already exists in `ui/`; extend for OS)
- Voice on the web UI (WebAssembly whisper.cpp)
- Meeting transcription + auto-ingest to RAG

**v1.0 — production hardening**
- Multi-node deployment (one node = one llama-server; orchestrator load-balances)
- gRPC internal API (currently HTTP)
- Formal security audit
- FIPS 140-3 build option for federal deployments

## Why this stack, not another one

- **Rust + Go + Python polyglot** — Go/Rust for the reliable server surface, Python for the AI glue where iteration speed wins.
- **BitNet.cpp over hosted APIs** — the 10× RAM, 4–7× CPU speedup, 82% energy saving unlocks segments cloud can't reach (per the ROI doc).
- **SQLite over Postgres/Qdrant** — single-file DB, zero-service ops, works on a Raspberry Pi. Swap in Qdrant/pgvector when scale demands.
- **Stdlib over frameworks** — no LangChain, no CrewAI, no FastAPI. Every dep is a future upgrade cost. The one exception is numpy for vector math.
- **Approval gates by default** — the ops loop asks before sending. No "AI sent an email that offended a customer" incidents by design.
- **Audit-first** — every action, every input, every decision written to `audit.jsonl`. Enterprise sales requires this from day one.

## Files added in v0.6

```
rag/
├── README.md          # design + quick start
├── models.json        # 3 embedding models (nomic / bge / e5)
├── setup.sh           # download embedding model
├── serve.sh           # llama-server --embedding on :8082
├── store.py           # SQLite vector store (stdlib + numpy)
├── ingest.py          # walk dir → extract → chunk → embed → store
├── query.py           # top-k cosine + citations
└── server.py          # HTTP /rag/ingest /rag/query /rag/status

memory/
├── README.md
├── schema.sql         # personal / session / org tables
└── manager.py         # CRUD + rolling summarization CLI

agents/
├── README.md
├── policies.yaml      # allow / approve / deny action rules
├── tools.py           # tool registry (rag / memory / web / email / github / files)
├── audit.py           # JSONL append-only sink
├── orchestrator.py    # plan / validate / approve / execute / audit loop
├── research_agent.py  # RAG-backed Q&A
└── ops_agent.py       # multi-step planner with approval gates

connectors/
├── README.md
├── email_imap.py      # read-only inbox summarization
└── web_fetch.py       # URL fetch + HTML→text

autoclaw_os.py         # unified CLI (status | ingest | research | ops | chat | memory | serve)
docs/PRIVATE_AI_OS.md  # this file
Dockerfile.aios        # everything baked in (BitNet + RAG + agents)
```

## See also

- [BITNET.md](BITNET.md) — Layer 1 (LLM runtime) install matrix + use cases
- [../rag/README.md](../rag/README.md) — Layer 3 design
- [../memory/README.md](../memory/README.md) — Layer 2 design
- [../agents/README.md](../agents/README.md) — Layer 4 design + approval model
- [../connectors/README.md](../connectors/README.md) — Layer 5 setup
- [../BLUEPRINT.md](../BLUEPRINT.md) — v0.6.0 changelog + roadmap
