# ProtoFlow

**Natural language → validated, executable application schema**

ProtoFlow is a multi-agent AI pipeline that takes a plain-English description of an application and produces a complete, cross-validated JSON schema covering every layer of the stack — database, REST API, UI, authentication, and business logic.

---

## What it does

You type: *"Build a CRM with contacts, deals, role-based access, and a premium analytics plan"*

ProtoFlow runs a 10-agent pipeline and returns:

- **Database schema** — normalised tables, columns, foreign keys, indexes, soft-delete
- **REST API schema** — full CRUD endpoints, request/response bodies mapped to DB columns, auth requirements
- **UI schema** — pages, components, forms, navigation, role-gated views
- **Auth schema** — JWT strategy, roles, permissions matrix, premium plan gates
- **Validation report** — cross-layer consistency check across all 12 rules
- **Runtime report** — simulated CRUD flow proving the schema is executable
- **Mermaid diagrams** — pipeline flow, ER diagram, API sequence diagram

---

## Architecture

```
User Prompt
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  Stage 1: Intent Extraction          (HITL always-on)   │
│  Stage 2: Architecture Design                           │
│  Stage 3: DB + API + UI + Auth       (parallel)         │
│  Stage 4: Cross-layer Validation                        │
│  Stage 5: Surgical Repair Loop       (max 3 attempts)   │
│  Stage 6: Runtime Simulation                            │
│  Stage 7: Logging + Mermaid Diagrams                    │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Complete FinalOutput JSON + SSE stream to frontend
```

**Tech stack:**
- Backend: Python, FastAPI, CrewAI 1.14.5, Groq (llama-3.3-70b-versatile)
- Frontend: React, Vite, TypeScript, Tailwind CSS, Lucide icons
- LLM routing: Groq free tier — 1K RPM, 300K TPM, no rate limit issues

---

## Project structure

```
compiler/
├── src/compiler/
│   ├── config/
│   │   ├── agents.yaml        # All 10 agent definitions (Groq, max_rpm=5)
│   │   └── tasks.yaml         # All 10 task definitions with HITL and async flags
│   ├── eval/
│   │   ├── runner.py          # Eval router — 20 test prompts, auto-metrics
│   │   ├── recorder.py        # Records pipeline metrics to eval_results.json
│   │   └── prompts.json       # 20 prompts: 10 real-world, 10 edge cases
│   ├── schemas/
│   │   └── contracts.py       # Pydantic models for all pipeline schemas
│   ├── tools/
│   │   ├── json_repair_tool.py    # Strips markdown fences, extracts JSON
│   │   ├── schema_diff_tool.py    # Before/after diff for repair agent
│   │   ├── mermaid_generator_tool.py  # Generates Mermaid diagram strings
│   │   └── llm_cache.py           # In-process LRU cache for LLM responses
│   ├── crew.py                # Pipeline orchestrator, repair loop, HITL, SSE
│   └── main.py                # FastAPI app — all routes
├── frontend/
│   ├── src/
│   │   ├── pages/             # HomePage, GeneratePage, ResultsPage
│   │   ├── components/        # StageCard, PipelineProgress, HITLModal, etc.
│   │   ├── hooks/             # useSSE — SSE connection with auto-reconnect
│   │   └── api/               # client.ts, types.ts
│   └── ...
├── .env                       # Real keys (gitignored)
├── .env.example               # Template
└── pyproject.toml
```

---

## Setup

### Prerequisites
- Python 3.10–3.13
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) — `pip install uv`
- Free Groq API key — [console.groq.com](https://console.groq.com)

### 1. Clone and install backend

```bash
git clone https://github.com/Lokesh-916/ProtoFlow.git
cd ProtoFlow
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY=your_key_here
```

### 3. Install frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
# VITE_API_URL=http://localhost:8000 is already set
```

---

## Running

**Terminal 1 — Backend:**
```bash
uv run uvicorn compiler.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**

---

## API routes

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/generate` | Start pipeline, returns `session_id` |
| `GET`  | `/stream/{session_id}` | SSE stream of all pipeline events |
| `POST` | `/clarify` | Resume pipeline after HITL input |
| `GET`  | `/result/{session_id}` | Full FinalOutput JSON |
| `GET`  | `/logs/{session_id}` | Markdown log as plain text |
| `GET`  | `/health` | Health check |
| `GET`  | `/eval/prompts` | List all 20 eval prompts with status |
| `POST` | `/eval/run/{id}` | Run a specific eval prompt (skips HITL) |
| `GET`  | `/eval/results` | Aggregated eval results and stats |

Interactive docs: **http://localhost:8000/docs**

---

## Testing with curl

```bash
# Start a pipeline run
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "CRM with contacts, deals, roles, and analytics"}'
# Returns: {"session_id": "..."}

# Run eval prompt #1 (no HITL, auto-records metrics)
curl -X POST http://localhost:8000/eval/run/1
```

---

## SSE event types

| Event | When |
|-------|------|
| `stage_update` | After each stage starts, completes, fails, or triggers repair |
| `hitl_required` | Pipeline paused — user input needed |
| `log_update` | New log entry from progress_logger |
| `pipeline_complete` | All stages done — includes final schema and Mermaid diagrams |
| `pipeline_failed` | Unrecoverable error |

---

## LLM configuration

All 10 agents use **Groq — llama-3.3-70b-versatile** (free tier).

| Limit | Value | Pipeline usage |
|-------|-------|----------------|
| RPM | 1,000 | ~15-20 calls per run |
| TPM | 300,000 | ~50-100K tokens per run |

`max_rpm: 5` is set in `agents.yaml` as a conservative throttle. A single Groq key handles the full pipeline without hitting limits.

---

## Eval framework

ProtoFlow includes a built-in evaluation framework with 20 prompts:
- 10 real-world prompts (CRM, e-commerce, healthcare, SaaS, etc.)
- 10 edge cases (empty intent, contradictions, extreme scope, ambiguity)

Run all 20 via the `/eval/run/{id}` endpoint. Results are recorded to `src/compiler/eval/eval_results.json` with auto-metrics (latency, tokens, repair count, HITL triggers) and support for human judgment annotations.

---

## Built by

Lokesh — [github.com/Lokesh-916](https://github.com/Lokesh-916)
