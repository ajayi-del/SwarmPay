# SwarmPay

**Open Wallet Standard Hackathon · Category 04: Multi-Agent Systems & Autonomous Economies**

A production-architecture demonstration of policy-gated, multi-agent economic coordination. A coordinator wallet (REGIS) decomposes tasks across five specialised sub-agents, each operating with a scoped OWS wallet and budget cap. Payments are signed or blocked in real time by a deterministic policy engine. Every event is streamed live to a terminal-aesthetic dashboard.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Agent Roster](#agent-roster)
3. [Policy Engine](#policy-engine)
4. [Demo Flow](#demo-flow)
5. [Tech Stack](#tech-stack)
6. [Project Structure](#project-structure)
7. [Prerequisites](#prerequisites)
8. [Installation](#installation)
9. [Environment Variables](#environment-variables)
10. [Running the Application](#running-the-application)
11. [API Reference](#api-reference)
12. [Database Schema](#database-schema)
13. [Frontend Architecture](#frontend-architecture)
14. [Key Design Decisions](#key-design-decisions)
15. [Hackathon Submission Notes](#hackathon-submission-notes)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                                │
│                    Next.js 14 + TypeScript                          │
│         TaskForm → Dashboard → AgentCards → MetricsBar              │
│              TanStack Query (1.2s poll) · Zustand store             │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ REST + SSE
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI (port 8000)                            │
│                                                                     │
│  POST /task/submit    →  create REGIS coordinator wallet            │
│  POST /task/decompose →  spawn 5 agent wallets (parallel)           │
│  POST /task/execute   →  run agents via Claude Haiku (parallel)     │
│  GET  /task/:id/status→  full task state snapshot                   │
│  GET  /task/:id/stream→  SSE live event stream                      │
│  GET  /audit          →  chronological audit log                    │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐    │
│  │ OWSService  │  │ AgentService │  │    PolicyService        │    │
│  │  (wallets,  │  │ (Claude Haiku│  │  3-rule chain:          │    │
│  │   signing)  │  │  per agent)  │  │  budget·auth·dedup      │    │
│  └─────────────┘  └──────────────┘  └────────────────────────┘    │
└──────────┬──────────────────────────────────────────────────────────┘
           │ httpx
           ▼
┌──────────────────────────┐
│   PocketBase (port 8090) │
│                          │
│  wallets   sub_tasks     │
│  tasks     payments      │
│  audit_log               │
└──────────────────────────┘
```

### Execution Flow

```
submit_task()
    └─▶ create REGIS wallet (OWS mock/real)
    └─▶ persist task + wallet to PocketBase
    └─▶ write audit: task_submitted

decompose_task()
    └─▶ Claude Haiku: generate 5 persona-specific sub-task descriptions
    └─▶ asyncio.gather() — all 5 agent bundles in parallel:
         ├─ create OWS wallet per agent
         ├─ create PocketBase wallet record
         └─ create PocketBase sub_task record
    └─▶ write audit: agent_spawned × 5

execute_task()  [background]
    └─▶ asyncio.gather() — all 5 agents in parallel:
         ├─ Claude Haiku: respond in agent's native language
         ├─ measure latency, store output as {text, ms}
         └─ _process_payment():
              ├─ PolicyService.evaluate_payment()  ← 3-rule chain
              ├─ if ALLOW → OWS.sign_payment() → status: signed
              └─ if DENY  → status: blocked + policy_reason logged
    └─▶ write audit: work_started / work_complete / payment_signed|blocked × 5
    └─▶ update task status: complete
```

---

## Agent Roster

| Agent | Flag | City | Language | Role | Budget Share | Rep |
|-------|------|------|----------|------|-------------|-----|
| **REGIS** | 🇬🇧 | London | English | Monarch (Coordinator) | Full treasury | ★★★★★ |
| **ATLAS** | 🇩🇪 | Berlin | Deutsch | Researcher | 10.31% | ★★★★☆ |
| **CIPHER** | 🇯🇵 | Tokyo | 日本語 | Analyst | 10.31% | ★★★★★ |
| **FORGE** | 🇳🇬 | Lagos | English/Yorùbá | Synthesizer | 10.31% | ★★★★☆ |
| **BISHOP** | 🇻🇦 | Vatican | Latin/Italiano | Bishop | 12.37% | ★★★★☆ |
| **SØN** | 🇸🇪 | Stockholm | Svenska | Heir | 5.15% | ★★★☆☆ |

Each agent responds in their native language via Claude Haiku. FORGE always attempts a +50% quality bonus payment, which trips the budget-cap policy rule — demonstrating the policy engine live during the demo.

### Budget Breakdown (0.97 ETH default)

```
REGIS  treasury:  0.97 ETH  (manages full budget)
├─ ATLAS   cap:   0.10 ETH  → paid  0.10 ETH  ✓ SIGNED
├─ CIPHER  cap:   0.10 ETH  → paid  0.10 ETH  ✓ SIGNED
├─ FORGE   cap:   0.10 ETH  → attempted 0.15 ETH  ✗ BLOCKED
├─ BISHOP  cap:   0.12 ETH  → paid  0.12 ETH  ✓ SIGNED
└─ SØN     cap:   0.05 ETH  → paid  0.05 ETH  ✓ SIGNED

Spent: 0.37 ETH  |  Blocked: 0.15 ETH  |  Efficiency: 71%
```

---

## Policy Engine

Three deterministic rules evaluated in sequence. First failure short-circuits evaluation and returns a human-readable reason.

```python
# Rule 1 — Budget Cap
if payment_amount > sub_task.budget_allocated:
    BLOCK: "Policy violation: amount {x} exceeds cap {y}"

# Rule 2 — Coordinator Authorization
if from_wallet.role != "coordinator":
    BLOCK: "Unauthorized signer: only coordinator can pay"

# Rule 3 — Double Payment Guard
if sub_task.status == "paid":
    BLOCK: "Double payment attempt blocked by policy engine"
```

All decisions — allow and deny — are written to the `audit_log` collection with full metadata.

---

## Demo Flow

The full demo completes in approximately **8–12 seconds** depending on Claude API latency.

```
1. User enters task description + 0.97 ETH budget
2. REGIS coordinator wallet created (OWS)
3. Five agent wallets spawned in parallel (~2s vs ~10s sequential)
4. Claude Haiku decomposes task into 5 persona-specific sub-tasks
5. All 5 agents work simultaneously:
   - ATLAS  → responds in German
   - CIPHER → responds in Japanese
   - FORGE  → responds in English/Yorùbá
   - BISHOP → responds in Italian with Latin phrases
   - SØN    → responds in Swedish
6. Policy engine evaluates each payment:
   - ATLAS:  0.10 ETH → ✓ SIGNED   (tx hash generated)
   - CIPHER: 0.10 ETH → ✓ SIGNED
   - BISHOP: 0.12 ETH → ✓ SIGNED
   - SØN:    0.05 ETH → ✓ SIGNED
   - FORGE:  0.15 ETH → ✗ BLOCKED  (exceeds 0.10 cap)
7. Dashboard updates live — audit log streams every event
8. MetricsBar finalises: 71% efficiency, budget fill animation
```

---

## Tech Stack

### Backend

| Package | Version | Purpose |
|---------|---------|---------|
| FastAPI | 0.115.12 | REST API framework |
| Uvicorn | 0.34.0 | ASGI server with hot reload |
| Anthropic SDK | 0.49.0 | Claude Haiku API client |
| httpx | 0.28.1 | Sync HTTP client for PocketBase |
| Pydantic | 2.11.1 | Request/response validation |
| python-dotenv | 1.1.0 | Environment variable loading |
| aiofiles | 24.1.0 | Async file I/O |

### Frontend

| Package | Version | Purpose |
|---------|---------|---------|
| Next.js | 14.2.35 | React framework (App Router) |
| TypeScript | ^5 | Type safety |
| TanStack Query | ^5.96.2 | Server state + polling |
| Zustand | ^5.0.12 | Client state (phase, taskId) |
| Framer Motion | ^12.38.0 | Animations (skill unlock, card entry) |
| Tailwind CSS | ^3.4.1 | Utility-first styling |

### Infrastructure

| Component | Version | Purpose |
|-----------|---------|---------|
| PocketBase | 0.22.20 | SQLite-backed persistence + REST API |
| Python | 3.13 | Runtime (3.9+ required for asyncio.to_thread) |
| Node.js | 18+ | Frontend runtime |

### Fonts

- **Bricolage Grotesque** — display text, headings, body
- **JetBrains Mono** — wallet addresses, numeric data, status labels

---

## Project Structure

```
SwarmPay/
├── backend/
│   ├── main.py                    # FastAPI app, CORS, router mounting
│   ├── requirements.txt
│   ├── .env.example               # Environment variable template
│   ├── setup_pocketbase.py        # One-shot collection creation script
│   ├── routers/
│   │   ├── tasks.py               # /task/* endpoints + background execution
│   │   └── audit.py               # /audit, /wallets endpoints
│   └── services/
│       ├── agent_service.py       # Claude Haiku + AGENT_PERSONAS config
│       ├── ows_service.py         # OWS wallet creation + payment signing
│       ├── policy_service.py      # 3-rule policy evaluation chain
│       └── pocketbase.py          # PocketBase HTTP client wrapper
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx             # Root layout, font imports
│   │   ├── page.tsx               # Main page: form / dashboard split
│   │   ├── providers.tsx          # TanStack Query provider
│   │   └── globals.css            # CSS vars, Bricolage + JetBrains Mono
│   ├── components/
│   │   ├── TaskForm.tsx           # Task submission form
│   │   ├── Dashboard.tsx          # Orchestrates all cards + metrics
│   │   ├── CoordinatorCard.tsx    # REGIS full-width card
│   │   ├── AgentCard.tsx          # Per-agent card (sparkline, skills, output)
│   │   ├── MetricsBar.tsx         # Swarm efficiency + budget fill bar
│   │   └── AuditLog.tsx           # Real-time event stream
│   └── lib/
│       ├── api.ts                 # Typed fetch wrappers + interfaces
│       ├── personas.ts            # Agent persona config + status label map
│       └── store.ts               # Zustand store (taskId, phase)
│
└── pocketbase/
    ├── pb_migrations/             # Auto-generated collection migrations
    └── setup_collections.py       # Alternative Python setup script
```

---

## Prerequisites

- **Python 3.13** (3.9+ minimum for `asyncio.to_thread`)
- **Node.js 18+**
- **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com)
- ~500 MB disk space (PocketBase binary + node_modules)

---

## Installation

### 1. Clone

```bash
git clone https://github.com/ajayi-del/SwarmPay.git
cd SwarmPay
```

### 2. Python virtual environment

```bash
python3.13 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 3. Environment variables

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set your Anthropic API key:

```env
ANTHROPIC_API_KEY=sk-ant-...
POCKETBASE_URL=http://localhost:8090
ENVIRONMENT=development
```

### 4. PocketBase

Download the binary for your platform from [pocketbase.io/docs](https://pocketbase.io/docs) and place it at `pocketbase/pocketbase` (already done if cloning from a machine that ran setup). Then:

```bash
cd pocketbase && ./pocketbase serve
```

On first run, create the admin account and collections:

```bash
# In a second terminal (from project root):
source .venv/bin/activate
python backend/setup_pocketbase.py
```

This creates the admin at `admin@swarmpay.local / password123456` and all five collections.

### 5. Frontend dependencies

```bash
cd frontend && npm install
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `ANTHROPIC_API_KEY` | — | **Yes** | Claude Haiku API key |
| `POCKETBASE_URL` | `http://localhost:8090` | No | PocketBase base URL |
| `OWS_DAEMON_URL` | `http://localhost:8080` | No | OWS daemon (falls back to mock) |
| `ENVIRONMENT` | `development` | No | Runtime environment label |

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | FastAPI backend URL |

---

## Running the Application

Open three terminal tabs from the project root:

```bash
# Terminal 1 — PocketBase
cd pocketbase && ./pocketbase serve

# Terminal 2 — FastAPI backend
source .venv/bin/activate
cd backend && python3 main.py

# Terminal 3 — Next.js frontend
cd frontend && npm run dev
```

Open **http://localhost:3000** in your browser.

### Production build (frontend)

```bash
cd frontend && npm run build && npm start
```

---

## API Reference

Base URL: `http://localhost:8000`

### `POST /task/submit`

Create a task and initialise the REGIS coordinator wallet.

**Request**
```json
{
  "description": "Analyse cross-chain liquidity for DeFi protocols",
  "budget": 0.97
}
```

**Response**
```json
{
  "task_id": "q5x9fq35qefcklk",
  "coordinator_wallet": {
    "id": "rcnrnzjk2hjk65a",
    "name": "REGIS-9a36fa",
    "role": "coordinator",
    "eth_address": "0xfa1a4ff600000000000000000000000000000000",
    "budget_cap": 0.97,
    "balance": 0.97
  }
}
```

---

### `POST /task/decompose`

Decompose the task into 5 sub-tasks and spawn agent wallets in parallel.

**Request**
```json
{ "task_id": "q5x9fq35qefcklk" }
```

**Response**
```json
{
  "sub_tasks": [
    {
      "id": "hjisp671m23o8s8",
      "agent_id": "ATLAS",
      "description": "Research DeFi liquidity sources across chains",
      "budget_allocated": 0.1,
      "status": "spawned",
      "wallet_id": "rf0qel0ay66nlib"
    }
    // ... 4 more
  ],
  "agent_wallets": [ /* wallet records */ ]
}
```

---

### `POST /task/execute`

Start parallel agent execution in the background. Returns immediately.

**Request**
```json
{ "task_id": "q5x9fq35qefcklk" }
```

**Response**
```json
{ "status": "running" }
```

---

### `GET /task/{task_id}/status`

Full task snapshot including coordinator wallet, all sub-tasks, and payments.

**Response**
```json
{
  "task": {
    "id": "q5x9fq35qefcklk",
    "description": "...",
    "total_budget": 0.97,
    "status": "complete",
    "coordinator_wallet_id": "rcnrnzjk2hjk65a"
  },
  "coordinator_wallet": { /* wallet record */ },
  "sub_tasks": [
    {
      "agent_id": "FORGE",
      "status": "blocked",
      "output": "{\"text\": \"Ẹ jẹ ká! The synthesis...\", \"ms\": 225}",
      "budget_allocated": 0.1
    }
    // ...
  ],
  "payments": [
    {
      "amount": 0.15,
      "status": "blocked",
      "policy_reason": "Policy violation: amount 0.15 exceeds cap 0.1",
      "to_wallet_id": "..."
    }
    // ...
  ]
}
```

---

### `GET /task/{task_id}/stream`

Server-Sent Events stream. Emits the full task snapshot on every state change, closes when task reaches `complete` or `failed`.

```
Content-Type: text/event-stream

data: {"task": {...}, "sub_tasks": [...], "payments": [...]}

data: {"task": {...}, "sub_tasks": [...], "payments": [...]}
```

---

### `GET /audit?limit=50`

Chronological audit log (newest first).

**Response**
```json
{
  "logs": [
    {
      "id": "cqelktxeioczlsp",
      "event_type": "payment_blocked",
      "entity_id": "payment_abc123",
      "message": "Payment abc123 BLOCKED ✗ 0.1500 ETH — Policy violation: amount 0.15 exceeds cap 0.1",
      "metadata": { "from": "...", "to": "...", "amount": 0.15 },
      "created": "2026-04-04T03:16:11.711Z"
    }
    // ...
  ]
}
```

### Event Types

| Event | Trigger |
|-------|---------|
| `task_submitted` | User submits a task |
| `agent_spawned` | Sub-agent wallet + record created |
| `work_started` | Agent begins Claude Haiku call |
| `work_complete` | Agent output received |
| `payment_signed` | Policy approved, OWS signed |
| `payment_blocked` | Policy rejected, reason logged |
| `task_complete` | All agents settled |

---

## Database Schema

All collections managed by PocketBase. Auto-fields: `id` (15-char), `created`, `updated`.

### `wallets`

| Field | Type | Notes |
|-------|------|-------|
| `name` | text | e.g. `REGIS-9a36fa`, `atlas-q5x9fq` |
| `role` | text | `coordinator` or `sub-agent` |
| `eth_address` | text | Mock or real OWS address |
| `sol_address` | text | Mock or real OWS address |
| `budget_cap` | number | ETH |
| `balance` | number | ETH |
| `api_key_id` | text | OWS scoped API key |

### `tasks`

| Field | Type | Notes |
|-------|------|-------|
| `description` | text | User-provided task |
| `total_budget` | number | ETH |
| `status` | text | `pending → decomposed → in_progress → complete | failed` |
| `coordinator_wallet_id` | text | FK → wallets.id |

### `sub_tasks`

| Field | Type | Notes |
|-------|------|-------|
| `task_id` | text | FK → tasks.id |
| `agent_id` | text | Persona name: `ATLAS`, `CIPHER`, etc. |
| `wallet_id` | text | FK → wallets.id |
| `description` | text | Haiku-generated or fallback |
| `budget_allocated` | number | ETH cap for this agent |
| `status` | text | `spawned → working → complete → paid | blocked | failed` |
| `output` | text | JSON: `{"text": "...", "ms": 235}` |

### `payments`

| Field | Type | Notes |
|-------|------|-------|
| `from_wallet_id` | text | Always REGIS coordinator |
| `to_wallet_id` | text | FK → wallets.id (sub-agent) |
| `amount` | number | Attempted payment in ETH |
| `chain_id` | text | `eip155:1` (Ethereum mainnet) |
| `status` | text | `signed` or `blocked` |
| `policy_reason` | text | Human-readable block reason |
| `tx_hash` | text | OWS mock tx hash (if signed) |

### `audit_log`

| Field | Type | Notes |
|-------|------|-------|
| `event_type` | text | See event types above |
| `entity_id` | text | ID of the affected record |
| `message` | text | Human-readable description |
| `metadata` | json | Structured context data |

---

## Frontend Architecture

### State Management

```
Zustand store (lib/store.ts)
  taskId: string | null       ← PocketBase task ID after submit
  phase: idle | submitted     ← Controls form ↔ dashboard transition
        | decomposed | running | done

TanStack Query (lib/api.ts)
  queryKey: ["task", taskId]  ← Polls /task/:id/status every 1.2s
  queryKey: ["audit"]         ← Polls /audit every 1.5s
  Auto-stops polling on task complete/failed
```

### Component Tree

```
page.tsx
├── TaskForm           (idle phase)
└── Dashboard          (active phase)
    ├── CoordinatorCard    REGIS · gold Monarch badge · treasury
    ├── AgentCard × 5      per sub-task (grid: 1/2/3 cols)
    │   ├── Header         flag · name · city · language | role badge
    │   ├── Stats row      ★★★★☆ · sparkline · tasks/success/avgSpeed
    │   ├── Skill badges   unlock animation: 2 → 3 on terminal state
    │   ├── StatusPill     persona-specific label (PRAYING, FORGING…)
    │   ├── Output area    native language text + latency + ~tokens
    │   ├── Wallet footer  budget cap · truncated wallet address
    │   └── PaymentOverlay signed/blocked with tx hash or policy reason
    └── MetricsBar
        ├── Spent / Blocked / Efficiency stats
        └── Animated budget fill bar (green signed + red blocked)
└── AuditLog           real-time event stream
```

### Persona Status Labels

Each agent has character-appropriate status labels instead of generic states:

| Agent | working | complete | blocked |
|-------|---------|----------|---------|
| ATLAS | WORKING | COMPLETE | BLOCKED ✗ |
| CIPHER | ANALYZING | SOLVED ✓ | BLOCKED ✗ |
| FORGE | FORGING | SMITHED | POLICY BLOCK ✗ |
| BISHOP | PRAYING | BLESSED ✓ | EXCOMMUNICATED |
| SØN | TRAINING | LEVELED UP | GROUNDED |
| REGIS | MANAGING | — | — |

---

## Key Design Decisions

**Why `asyncio.to_thread` instead of async PocketBase client?**
The existing `httpx.Client` (sync) is thread-safe. Wrapping calls in `asyncio.to_thread` gives true parallelism via the thread pool without requiring a full async rewrite. This cut wallet creation time from ~10s sequential to ~2s parallel for 5 agents.

**Why output stored as `{"text": "...", "ms": 1234}`?**
Embedding latency in the output field avoids a schema change to `sub_tasks` while delivering per-agent timing data to the frontend. The frontend parses with JSON.parse and falls back gracefully for any plain-text output.

**Why hardcoded budget shares instead of LLM-derived?**
Budget allocation is a financial policy decision, not a creative one. Hardcoding shares (ATLAS 10.31%, BISHOP 12.37%, SØN 5.15%) ensures the demo numbers are deterministic and the FORGE block fires reliably at exactly 0.15 ETH vs 0.10 cap regardless of LLM variance.

**Why PocketBase over PostgreSQL/Supabase?**
Single binary, zero config, auto-migrations, built-in REST API, and runs offline. Ideal for hackathon demos where infrastructure reliability is more important than horizontal scalability.

**Why no Inter / no Firebase / no Clerk?**
Design constraint from the hackathon brief. Bricolage Grotesque + JetBrains Mono gives a distinct terminal-infrastructure aesthetic that differentiates from generic web apps.

---

## Hackathon Submission Notes

**Category:** 04 — Multi-Agent Systems & Autonomous Economies

**Core OWS primitives demonstrated:**
- Wallet creation with scoped budget caps
- Policy-gated payment signing
- Coordinator-to-agent payment flows
- Audit trail for every signing decision

**What makes this different:**
- Agents operate with genuine economic constraints — they cannot be overpaid regardless of coordinator intent
- The policy engine is inspectable and its decisions are fully logged
- Multilingual agent outputs demonstrate that autonomous agents can operate across cultural contexts without central translation
- Parallel execution means the coordinator manages a real swarm, not a sequential queue

**Limitations / future work:**
- OWS wallet operations use a mock implementation (no on-chain settlement in demo)
- Policy rules are hardcoded; a production system would load them from a governance contract
- Agent reputation scores are static; a production system would update them based on task outcomes
- No authentication on the API (appropriate for demo, not production)

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

*Built for the Open Wallet Standard Hackathon · April 2026*
