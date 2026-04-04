# SwarmPay

**Open Wallet Standard Hackathon · Category 04 — Multi-Agent Systems & Autonomous Economies**

> A coordinator wallet (REGIS) decomposes tasks across five specialised sub-agents, each operating with a scoped OWS wallet, reputation score, and 120-second heartbeat. Payments are signed or blocked by a four-rule policy engine. Every decision is audited, every key can be revoked.

---

## What Was Built

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Reputation-Gated Policy Engine (4-rule chain, live rep scores) | ✅ |
| 2 | Kingdom / Office Mode Toggle (dual persona system, 0.3 s fade) | ✅ |
| 3 | OWS Proof Panel — per-agent collapsible cryptographic audit | ✅ |
| 4 | Inter-Agent Peer Payments — ATLAS→CIPHER→FORGE micro-economy | ✅ |
| 5 | Swarm Intelligence Panel — economy health score + leaderboard | ✅ |
| + | Dead Man's Switch — 120 s heartbeat, key revocation, budget sweep | ✅ |
| + | Real Agent Tools — Firecrawl web search, E2B Python sandboxes | ✅ |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BROWSER  Next.js 14 + TypeScript                                       │
│                                                                         │
│  TaskForm ──▶ CoordinatorCard (REGIS)                                   │
│               AgentCard × 5                                             │
│               ├─ ⏱ countdown  · 🔧 tools used · ▶ OWS Proof           │
│               ├─ ⇄ peer badge · 📄 download report (FORGE)             │
│               └─ collapsible code block (CIPHER) · sources (ATLAS)     │
│               MetricsBar · AuditLog · SwarmPanel                        │
│               ModeToggle (⚔️ Kingdom  ↔  🏢 Office)                    │
│                                                                         │
│  TanStack Query (1.2 s poll) · Zustand (phase + mode) · Framer Motion  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ REST
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  FastAPI  port 8000                                                     │
│                                                                         │
│  POST /task/submit      create REGIS coordinator wallet (OWS)          │
│  POST /task/decompose   spawn 5 agent wallets in parallel              │
│  POST /task/execute     background: run agents + policy + payments      │
│  GET  /task/:id/status  full snapshot (task, wallets, payments, reps)  │
│  GET  /audit            chronological event stream                      │
│  GET  /swarm/stats      lifetime economy metrics + health score         │
│                                                                         │
│  ┌──────────────────┐  ┌────────────────────┐  ┌───────────────────┐  │
│  │   OWSService     │  │   AgentService     │  │  PolicyService    │  │
│  │  create_wallet   │  │  ATLAS Firecrawl   │  │  1. REP GATE      │  │
│  │  create_api_key  │  │  CIPHER E2B exec   │  │  2. BUDGET CAP    │  │
│  │  sign_payment    │  │  FORGE  E2B write  │  │  3. COORD AUTH    │  │
│  │  revoke_api_key  │  │  BISHOP/SØN Haiku  │  │  4. DOUBLE PAY    │  │
│  └──────────────────┘  └────────────────────┘  └───────────────────┘  │
│                                                                         │
│  Dead Man's Switch  asyncio.wait_for(run_agent, timeout=120 s)         │
│  → revoke OWS key → sweep budget → status: timed_out → audit           │
│                                                                         │
│  Peer Payments (post-settle):  ATLAS → CIPHER  0.005 ETH               │
│                                CIPHER → FORGE  0.003 ETH               │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ httpx
                                 ▼
                   ┌─────────────────────────┐
                   │  PocketBase  port 8090  │
                   │  wallets  tasks         │
                   │  sub_tasks  payments    │
                   │  audit_log              │
                   │  agent_reputation       │
                   └─────────────────────────┘
```

---

## Execution Flow

```
submit()
  └─▶ OWS: create coordinator wallet (REGIS)
  └─▶ PB:  persist task + wallet
  └─▶ audit: task_submitted

decompose()
  └─▶ Haiku: generate 5 persona sub-task descriptions
  └─▶ asyncio.gather() — all 5 bundles in parallel (~2 s vs ~10 s sequential)
       ├─ OWS: create_wallet + create_api_key(budget_cap)
       └─ PB:  wallet record + sub_task record
       └─▶ audit: agent_spawned × 5

execute()  [background]
  └─▶ asyncio.gather() — 5 agents + DMS wrappers in parallel:
       ├─ ATLAS:  Firecrawl.search() → feed real content to Haiku (German)
       ├─ CIPHER: Haiku writes Python → E2B sandbox executes → stdout captured
       ├─ FORGE:  Haiku writes report+summary → E2B writes .md → return content
       ├─ BISHOP: Haiku in Italian with Latin phrases
       └─ SØN:    Haiku in Swedish
       Per agent:
         reputation = PB.get_reputation(agent)
         policy     = PolicyService.evaluate_payment(amount, rep, sub_task)
         ALLOW  → OWS.sign_payment() → status: paid  → rep +0.1
         DENY   → status: blocked    → rep −0.2 → policy_reason logged
         TIMEOUT (120 s):
           OWS.revoke_api_key() → PB wallet: api_key_id = "REVOKED-<ts>"
           sweep payment (agent → coordinator)
           sub_task: status = timed_out
           audit: dead_mans_switch + reputation_updated (−0.3)
  └─▶ peer payments (post-settle):
       ATLAS wallet → CIPHER wallet  0.005 ETH  [research handoff]
       CIPHER wallet → FORGE wallet  0.003 ETH  [analysis delivery]
       audit: peer_payment × 2
  └─▶ task: status = complete
```

---

## Agent Roster

| Agent | Flag | City | Role | Budget | Rep | Live Tools |
|-------|------|------|------|--------|-----|------------|
| **REGIS** | 🇬🇧 | London | Monarch · Coordinator | Full treasury | ★★★★★ | — |
| **ATLAS** | 🇩🇪 | Berlin | Researcher | 10.31% | ★★★★☆ | Firecrawl web search |
| **CIPHER** | 🇯🇵 | Tokyo | Analyst | 10.31% | ★★★★★ | E2B Python sandbox |
| **FORGE** | 🇳🇬 | Lagos | Synthesizer | 10.31% | ★★★★☆ | E2B file write + download |
| **BISHOP** | 🇻🇦 | Vatican | Compliance | 12.37% | ★★★★☆ | — |
| **SØN** | 🇸🇪 | Stockholm | Heir | 5.15% | ★★★☆☆ | — |

### Budget Breakdown (0.97 ETH default)

```
REGIS  treasury  0.97 ETH
├─ ATLAS   0.10 ETH  →  paid  0.1000 ETH  ✓ SIGNED    (4★ limit: 0.12)
├─ CIPHER  0.10 ETH  →  paid  0.1000 ETH  ✓ SIGNED    (5★ limit: 0.20)
├─ FORGE   0.10 ETH  →  atmp  0.1500 ETH  ✗ REP BLOCK (4★ limit: 0.12)
├─ BISHOP  0.12 ETH  →  paid  0.1200 ETH  ✓ SIGNED    (4★ limit: 0.12)
└─ SØN     0.05 ETH  →  paid  0.0500 ETH  ✓ SIGNED    (3★ limit: 0.06)

Peer payments (post-settle):
  ATLAS  → CIPHER   0.005 ETH  [research handoff]
  CIPHER → FORGE    0.003 ETH  [analysis delivery]

Coordinator paid: 0.370 ETH  ·  Blocked: 0.150 ETH  ·  Peer: 0.008 ETH
Approval rate: 71%  ·  Economy health: ~82 / 100
```

---

## Policy Engine

Four deterministic rules evaluated in sequence. First failure short-circuits and returns a human-readable reason.

```python
# services/policy_service.py

_REP_TIERS = [(5.0, 0.20), (4.0, 0.12), (3.0, 0.06), (2.0, 0.02)]

def evaluate_payment(self, from_wallet, to_wallet, amount, sub_task, reputation=3.0):
    for check in (
        self._check_reputation_gate,   # Rule 1: rep score → spend limit
        self._check_budget_cap,        # Rule 2: coordinator allocation ceiling
        self._check_coordinator_auth,  # Rule 3: only coordinator wallet may sign
        self._check_double_payment,    # Rule 4: no duplicate settlement
    ):
        result = check(amount=amount, sub_task=sub_task,
                       from_wallet=from_wallet, reputation=reputation)
        if not result.allow:
            return result
    return PolicyResult(allow=True)
```

Block reasons are prefixed for frontend parsing:

```
REP BLOCK:     FORGE reputation 4.0★ insufficient for 0.1500 ETH (limit: 0.12 ETH)
BUDGET BLOCK:  requested 0.1500 ETH exceeds allocation 0.1000 ETH
AUTH BLOCK:    only coordinator wallet may sign payments
DOUBLE PAY:    sub-task already settled
SWEEP:         Dead man's switch — ATLAS
PEER:          research handoff
```

---

## Reputation System

Scores persist in PocketBase and update live after every outcome:

```python
# services/pocketbase.py — spend limits per tier mirror policy_service._REP_TIERS

_REP_DEFAULTS = {"ATLAS": 4.0, "CIPHER": 5.0, "FORGE": 4.0, "BISHOP": 4.0, "SØN": 3.0}

# payment signed    → +0.1  (capped   5.0)
# payment blocked   → −0.2  (floored  1.0)
# DMS timeout       → −0.3
# work exception    → −0.2
```

The live score is fetched before every policy call. Consecutive blocked payments reduce an agent's tier and tighten future spend limits — the system self-enforces over time.

---

## Dead Man's Switch

```python
# routers/tasks.py

async def run_agent_with_dms(sub_task):
    try:
        await asyncio.wait_for(run_agent(sub_task), timeout=120.0)
    except asyncio.TimeoutError:
        await _trigger_dead_mans_switch(sub_task, coordinator_wallet)

async def _trigger_dead_mans_switch(sub_task, coordinator_wallet):
    swept_at = datetime.now(timezone.utc).isoformat()

    # 1 — Revoke OWS API key
    ows.revoke_api_key(sub_task["wallet_id"])
    pb.update("wallets", sub_task["wallet_id"], {"api_key_id": f"REVOKED-{swept_at}"})

    # 2 — Sweep budget back to coordinator
    ows.sign_payment(sub_task["wallet_id"], coordinator_wallet["id"], budget_allocated)

    # 3 — Mark sub_task, embed revocation metadata in output JSON
    pb.update("sub_tasks", sub_task["id"], {
        "status": "timed_out",
        "output": json.dumps({"key_revoked": True, "key_revoked_at": swept_at, ...}),
    })

    # 4 — Audit + reputation penalty
    audit("dead_mans_switch",
          f"SECURITY: Dead man's switch triggered for {agent}. Funds swept to treasury.")
    pb.update_reputation(agent, -0.3)
```

The frontend shows a live countdown on each active card. At ≤ 30 s the pill pulses red — **DMS ARMED**.

---

## OWS Integration

```python
# services/ows_service.py  (SDK → subprocess → mock fallback chain)

# Create wallet
wallet = ows.create_wallet("atlas-a3f9b2")
# {"id": "...", "eth_address": "0x...", "sol_address": "..."}

# Scoped API key
api_key = ows.create_api_key(wallet["id"], budget_cap=0.10)
# "ows_mock_a3f9b2c1d4e5f6a7b8c9d0e1f2a3b4c5"

# Sign payment
tx = ows.sign_payment(from_id, to_id, amount, chain_id="eip155:1")
# {"status": "signed", "tx_hash": "0x4a3f...", "chain_id": "eip155:1"}

# Revoke key (Dead Man's Switch)
ows.revoke_api_key(wallet_id)
```

### OWS Proof Panel

Each terminal agent card has a collapsible **▶ OWS PROOF** section:

```
OWS-XXXX-XXXXXXXX          ← api_key_id derived from wallet_id
wallet_id  ab12cd34…ef78
sign_hash  0x4a3f…d9e2
revoked_at 14:23:07        ← only when DMS fires

Policy chain:
  ✓  1. REP GATE
  ✓  2. BUDGET CAP
  ✗  3. COORD AUTH     ← inline failure detail
  ·  4. DOUBLE PAY     ← skipped (short-circuit)

KEY  REVOKED            ← ACTIVE / SUSPENDED / REVOKED
⚠ OWS key revoked · budget swept to coordinator vault
```

---

## Real Agent Tools

All tool integrations degrade gracefully — absent API key produces `tools: []`, the card renders unchanged.

### ATLAS — Firecrawl Web Search

```python
# FIRECRAWL_API_KEY required
from firecrawl import FirecrawlApp
result = FirecrawlApp(api_key=key).search(task_description, limit=3)
# → real source URLs and markdown content fed into Claude prompt
```

ATLAS's card shows source URLs under the output. The Haiku analysis is grounded in actual scraped content.

### CIPHER — E2B Python Execution

```python
# E2B_API_KEY required
from e2b_code_interpreter import Sandbox

# Step 1: Haiku writes analysis code
code = haiku("Write 8-12 lines of Python to analyze: " + description)

# Step 2: Execute in sandbox
with Sandbox(api_key=key) as sbx:
    execution = sbx.run_code(code)
stdout = "\n".join(execution.logs.stdout)
```

CIPHER's card shows "Executed in E2B sandbox: 1240ms" and a collapsible dark code block with stdout.

### FORGE — E2B File Write + Download

```python
# Single Haiku call produces summary + full markdown report (split on ---)
# Report is base64-encoded and written to E2B sandbox:
write_code = f'''
import base64
content = base64.b64decode("{encoded}").decode("utf-8")
with open("/home/user/swarm_report.md", "w") as f:
    f.write(content)
'''
with Sandbox(api_key=key) as sbx:
    sbx.run_code(write_code)
```

FORGE's card shows a **📄 Download Report** button. The report is embedded in the output JSON and downloaded client-side via `URL.createObjectURL` — no additional API endpoint.

---

## Mode Toggle

Two complete presentation layers over identical live data:

| Element | ⚔️ Kingdom | 🏢 Office |
|---------|-----------|----------|
| REGIS role | Monarch | Chief Treasury Officer |
| Treasury label | Royal Vault | Operating Budget |
| ATLAS dept | Researcher | Research Dept · LEVEL 4 |
| Blocked payment | ✗ BLOCKED | ✗ COMPLIANCE REJECTED |
| Metrics: spend | Spent | Disbursed |
| Metrics: block | Blocked | Held |
| Efficiency label | Swarm Efficiency | Clearance Rate |
| Agents label | Active Agents | Active Staff |
| OWS panel label | OWS PROOF | COMPLIANCE PROOF |
| DMS key status | SUSPENDED | ACCESS REVOKED |

Toggling applies `.office-mode` to `document.body` (CSS custom properties cascade), triggers 0.3 s AnimatePresence fade, and smooth colour transitions on all surfaces.

---

## Swarm Intelligence Panel

Visible once any task has run. Polls `/swarm/stats` every 5 s.

```
Economy Health  82/100    ← approval_rate × 65 + (avg_rep / 5) × 35
                          ← animated SVG ring, green ≥ 70, amber ≥ 40

Tasks Run: 3   Signed: 12   Rejected: 3   ETH Processed: 1.110
ETH Held: 0.450   Peer Transfers: 6 · 0.048 ETH

Agent Leaderboard:
  1. CIPHER  ★★★★★  5.0
  2. ATLAS   ★★★★☆  4.3
  3. BISHOP  ★★★★☆  4.1
  4. FORGE   ★★★½☆  3.6
  5. SØN     ★★★☆☆  3.0
```

---

## Setup

### Prerequisites

- Python 3.9+
- Node.js 18+
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com)

**Optional (real agent tools):**
- E2B API key — [e2b.dev](https://e2b.dev) (free tier)
- Firecrawl API key — [firecrawl.dev](https://firecrawl.dev) (free tier)

### Install

```bash
git clone https://github.com/ajayi-del/SwarmPay.git
cd SwarmPay

# Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

# Node dependencies
cd frontend && npm install && cd ..
```

### Configure

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — set at minimum ANTHROPIC_API_KEY
```

```env
ANTHROPIC_API_KEY=sk-ant-...
POCKETBASE_URL=http://localhost:8090

# Optional — activates real agent tools
E2B_API_KEY=e2b_...
FIRECRAWL_API_KEY=fc-...
```

### Run

```bash
# Terminal 1 — PocketBase
cd pocketbase && ./pocketbase serve

# Terminal 2 — Backend
source .venv/bin/activate && cd backend && python3 main.py

# Terminal 3 — Frontend
cd frontend && npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)**

### First run — create collections

```bash
# With PocketBase running:
source .venv/bin/activate
python backend/setup_pocketbase.py
# Creates admin@swarmpay.local / password123456
# Creates: wallets · tasks · sub_tasks · payments · audit_log · agent_reputation
```

---

## Project Structure

```
SwarmPay/
├── backend/
│   ├── main.py                    # FastAPI app, CORS, router mounting
│   ├── requirements.txt
│   ├── .env.example
│   ├── routers/
│   │   ├── tasks.py               # submit · decompose · execute · DMS · peer payments
│   │   └── audit.py               # audit log · wallets · /swarm/stats
│   └── services/
│       ├── agent_service.py       # ATLAS/CIPHER/FORGE tools + BISHOP/SØN Haiku
│       ├── ows_service.py         # wallet · api_key · sign · revoke (SDK→mock)
│       ├── policy_service.py      # 4-rule reputation-gated evaluation chain
│       └── pocketbase.py          # httpx wrapper + reputation CRUD
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # root page, .office-mode on body, SwarmPanel
│   │   ├── providers.tsx          # TanStack Query provider
│   │   └── globals.css            # CSS vars, .office-mode overrides, animations
│   ├── components/
│   │   ├── AgentCard.tsx          # countdown · tools · code block · download
│   │   ├── CoordinatorCard.tsx
│   │   ├── MetricsBar.tsx
│   │   ├── AuditLog.tsx
│   │   ├── OWSProofPanel.tsx      # policy chain · key status · revocation ts
│   │   ├── SwarmPanel.tsx         # health ring · leaderboard · lifetime stats
│   │   ├── ModeToggle.tsx
│   │   └── ErrorBoundary.tsx
│   └── lib/
│       ├── api.ts                 # typed fetch wrappers + interfaces
│       ├── personas.ts            # agent personas · office personas · status maps
│       ├── modeStore.ts           # Zustand: kingdom | office
│       └── store.ts               # Zustand: taskId · phase
│
└── pocketbase/
    ├── pb_migrations/
    └── setup_collections.py
```

---

## Key Design Decisions

**`asyncio.wait_for` for Dead Man's Switch** — atomic, cancellation-safe, no polling loop or separate process. `TimeoutError` surface is contained inside the existing gather.

**Graceful tool degradation** — Firecrawl and E2B keys are checked at module load time. Absent key → `tools: []` in the output JSON, the card renders unchanged. The demo works fully offline.

**`timed_out` as plain text status** — PocketBase `sub_tasks.status` is a `text` field with no enum constraint. No schema migration required.

**Client-side Blob download** — FORGE's report is embedded in the output JSON and downloaded via `URL.createObjectURL`. Zero additional API endpoint, works without a persistent file server.

**Single combined Claude call for FORGE** — a `---` separator in the prompt yields both the card summary and the full report in one Haiku call, halving latency and API cost.

**Peer payments bypass policy** — inter-agent micro-transactions are intentional. FORGE receives a peer payment from CIPHER even though the coordinator blocked FORGE's primary payment. Two distinct payment layers: policy-gated coordinator→agent and free-form agent→agent.

**`parseRevocation` reads `subTask.output` directly** — no prop drilling through Dashboard → AgentCard → OWSProofPanel. The panel already receives `subTask`.

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI 0.115 · Uvicorn · Python 3.9+ |
| LLM | Anthropic Claude Haiku (claude-3-haiku-20240307) |
| Real tools | e2b-code-interpreter · firecrawl-py |
| Persistence | PocketBase 0.22 (SQLite, single binary) |
| Frontend | Next.js 14 · TypeScript · Tailwind CSS |
| State | TanStack Query v5 · Zustand v5 |
| Animation | Framer Motion v12 |
| Fonts | Bricolage Grotesque · JetBrains Mono |

---

*Built for the Open Wallet Standard Hackathon · April 2026*
