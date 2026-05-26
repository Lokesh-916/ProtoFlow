# ProtoFlow — AI-Powered Application Schema Compiler

> **Natural language → structured config → validated → executable → working application blueprint**

ProtoFlow is a multi-agent AI compiler that converts open-ended natural language instructions into strict, complete, and validated application configurations. It generates production-ready schemas for UI, API, Database, and Auth systems — then validates cross-layer consistency and repairs any conflicts automatically.

## ⚡ Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Stage Pipeline** | 10 specialized AI agents in sequence: Intent → Architecture → DB/API/UI/Auth (parallel) → Validation → Repair → Runtime Simulation → Logging |
| **Strict Schema Enforcement** | 25+ Pydantic models with typed fields, constraints, and cross-layer traceability |
| **Validation + Repair Engine** | 12-point cross-layer validation checklist with automatic surgical repair (max 3 attempts) |
| **Human-in-the-Loop (HITL)** | Always-on clarification at intent stage, with escalation after repair failures |
| **Real-Time Streaming** | Server-Sent Events (SSE) with per-stage status updates, latency, and confidence scores |
| **Mermaid Diagrams** | Auto-generated pipeline flow, ER diagram, and API sequence diagrams |
| **Evaluation Framework** | 20 test prompts (10 real, 10 adversarial) with metrics dashboard at `/eval` |
| **LLM Response Caching** | In-memory LRU cache to avoid redundant API calls across repair loops |

## 🏗️ Architecture

```
User Prompt
    │
    ▼
┌─────────────────────┐
│  Intent Extraction   │  ← HITL always-on (asks clarifying questions)
│  (qwen3-coder)       │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  System Architect    │  ← Entities, Relations, Business Rules
│  (deepseek-v4-flash) │
└─────────┬───────────┘
          │
    ┌─────┼─────┬─────┐
    ▼     ▼     ▼     ▼
  ┌───┐ ┌───┐ ┌───┐ ┌────┐
  │DB │ │API│ │UI │ │Auth│   ← Parallel fan-out via asyncio.gather
  └─┬─┘ └─┬─┘ └─┬─┘ └─┬──┘
    └─────┼─────┼─────┘
          ▼
┌─────────────────────┐
│  Cross-Layer         │  ← 12-point validation checklist
│  Validator           │
└─────────┬───────────┘
          │ (if errors)
          ▼
┌─────────────────────┐
│  Repair Agent        │  ← Surgical fixes, max 3 loops
│  + HITL escalation   │  ← Asks human after 2 failed attempts
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  Runtime Validator   │  ← Simulates full CRUD flows
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  Progress Logger     │  ← Mermaid diagrams + log entries
└─────────┬───────────┘
          ▼
    Final Schema Output
    (JSON + Mermaid + Metrics)
```

## 🚀 Quick Start

### Prerequisites
- Python ≥ 3.10, < 3.14
- Node.js ≥ 18
- [uv](https://docs.astral.sh/uv/) package manager

### Setup

1. **Clone and install Python dependencies:**
```bash
git clone <repo-url>
cd compiler
uv sync
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

3. **Install frontend dependencies:**
```bash
cd frontend
npm install
```

### Running

**Start the backend:**
```bash
uv run serve
```
The API server starts at `http://localhost:8000`. API docs available at `http://localhost:8000/docs`.

**Start the frontend (in a separate terminal):**
```bash
cd frontend
npm run dev
```
The UI opens at `http://localhost:5173`.

## 📁 Project Structure

```
compiler/
├── src/compiler/
│   ├── config/
│   │   ├── agents.yaml          # 10 agent definitions with roles & models
│   │   └── tasks.yaml           # 10 task definitions with prompts & schemas
│   ├── schemas/
│   │   └── contracts.py         # 25+ Pydantic models (707 lines)
│   ├── tools/
│   │   ├── json_repair_tool.py  # 4-step JSON extraction + repair
│   │   ├── schema_diff_tool.py  # Field-level before/after diffs
│   │   ├── mermaid_generator_tool.py # Pipeline, ER, API diagrams
│   │   └── llm_cache.py         # LRU response cache with TTL
│   ├── eval/
│   │   ├── prompts.json         # 20 evaluation test prompts
│   │   ├── runner.py            # Eval API routes
│   │   └── recorder.py          # Metrics + log recording
│   ├── crew.py                  # Pipeline orchestrator (914 lines)
│   └── main.py                  # FastAPI app + routes
├── frontend/
│   ├── src/
│   │   ├── pages/               # HomePage, GeneratePage, ResultsPage, EvalPage
│   │   ├── components/          # StageCard, SchemaViewer, MermaidDiagram, etc.
│   │   ├── api/                 # API client + SSE hook
│   │   └── index.css            # Tailwind + custom design system
│   └── tailwind.config.js       # Custom canvas/terra/sage palette
├── backend/logs/                # Runtime pipeline logs (gitignored)
├── .env.example                 # Environment variable template
└── pyproject.toml               # Python dependencies
```

## 🧪 Evaluation Framework

ProtoFlow includes a manual evaluation framework with 20 test prompts:

| Category | Count | Examples |
|----------|-------|---------|
| Real-world | 10 | CRM, E-commerce, Healthcare, SaaS, LMS, Project Management |
| Edge cases | 10 | Empty intent, self-contradictory auth, extreme scope, privacy contradictions |

### Running Evaluations
1. Start both backend and frontend
2. Navigate to `http://localhost:5173/eval`
3. Run prompts one at a time or use "Run All Unrun" for sequential execution
4. Judge each result as Pass / Partial / Fail with notes
5. Export results as JSON for analysis

### Dashboard Features
- Summary stat cards (pass rate, avg latency, avg tokens, HITL rate)
- Interactive charts (pass/fail donut, latency by difficulty, repair loops)
- Filterable prompts table with expandable details
- Judgment modal with failure categorization

## 🔧 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/generate` | Start a pipeline run |
| GET | `/stream/{session_id}` | SSE stream of pipeline events |
| POST | `/clarify` | Submit HITL answers |
| GET | `/result/{session_id}` | Full schema output JSON |
| GET | `/logs/{session_id}` | Pipeline log (markdown) |
| GET | `/health` | Health check |
| GET | `/eval/prompts` | List all 20 eval prompts |
| POST | `/eval/run/{prompt_id}` | Run pipeline for eval prompt |
| POST | `/eval/record/{prompt_id}` | Record human judgment |
| GET | `/eval/results` | Summary statistics |
| GET | `/eval/export` | Download eval_results.json |

## 🤖 Agent Model Configuration

All agents use free-tier models via [OpenRouter](https://openrouter.ai):

| Agent | Model | Role |
|-------|-------|------|
| Intent Extractor | qwen/qwen3-coder:free | Parse natural language → structured intent |
| System Architect | deepseek/deepseek-v4-flash:free | Design application architecture |
| DB Schema Agent | deepseek/deepseek-v4-flash:free | Generate database tables + relations |
| API Schema Agent | deepseek/deepseek-v4-flash:free | Generate REST API endpoints |
| UI Schema Agent | qwen/qwen3-coder:free | Generate pages + components + forms |
| Auth Agent | openai/gpt-oss-20b:free | Generate roles + permissions + plans |
| Validator | deepseek/deepseek-v4-flash:free | Cross-layer consistency checks |
| Repair Agent | qwen/qwen3-coder:free | Surgical schema fixes |
| Runtime Validator | openai/gpt-oss-20b:free | Simulate execution flows |
| Progress Logger | openai/gpt-oss-20b:free | Mermaid diagrams + logs |

## 📝 License

MIT
