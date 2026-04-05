# SwarmPay

**Project:** grand-fulfillment · **Environment:** production  
**Submitted to:** OWS Hackathon (Category 04 — Multi-Agent Systems) · Solana x402 Hackathon (Track: Best Trustless Agent Economy)

> REGIS, a sovereign coordinator wallet, decomposes tasks across five specialised sub-agents. Each agent operates with a scoped OWS wallet, real Solana devnet keypair, quality-scored outputs, and a 120-second heartbeat dead man's switch. Payments scale with output quality (0–10). Agents compete for REGIS's coordinator role. Every decision is audited, every key can be revoked, every event fires to Telegram in real time.

---

## Live Deployment

| Service | URL |
|---------|-----|
| **Frontend** | https://frontend-production-9eb4.up.railway.app |
| **Backend API** | https://backend-production-4717.up.railway.app |
| **PocketBase** | https://pocketbase-production-bd4d.up.railway.app |
| **Railway Project** | https://railway.com/project/78995748-b3fa-4f04-9a6d-d7bcfe2adb41 |

---

## What Was Built

| Feature | Status |
|---------|--------|
| Reputation-Gated Policy Engine (4-rule chain) | ✅ |
| Goal-Compounding Agent Execution (ATLAS→CIPHER→FORGE→BISHOP→SØN) | ✅ |
| Quality-Scaled Payments — DeepSeek scores each agent 0–10, payment = budget × score | ✅ |
| REGIS Challenge System — top agents can overthrow REGIS via Claude adjudication | ✅ |
| Telegram Umbilical Cord — every payment, failure, audit, punishment, and overthrow fires to Telegram | ✅ |
| Agent Lock/Unlock via Telegram (`/lock ATLAS`, `/unlock ATLAS`, `/locked`) | ✅ |
| Clarifying Questions — REGIS asks 2–3 context questions before dispatching | ✅ |
| REGIS Sovereign Brain — append-only memory, probe/audit/punish system | ✅ |
| Dead Man's Switch — 120s heartbeat, key revocation, budget sweep | ✅ |
| Sleeping Agent Visualization — non-summoned agents render dormant with breathing animation | ✅ |
| ATLAS — Firecrawl web search + real sources + 6–10 sentence German research reports | ✅ |
| CIPHER — E2B Python sandbox + quantitative analysis in Japanese | ✅ |
| FORGE — E2B file write + downloadable markdown report | ✅ |
| BISHOP — MoonPay compliance check + AML review in Italian/Latin | ✅ |
| SØN — Solana devnet balance queries + recent transaction lookup | ✅ |
| x402 Micropayments on Solana devnet | ✅ |
| Meteora DLMM live SOL/USDC rate | ✅ |
| MoonPay fiat→SOL onramp widget | ✅ |
| Inter-Agent Peer Payments — ATLAS→CIPHER→FORGE→BISHOP micro-economy | ✅ |
| Kingdom / Office Mode Toggle | ✅ |
| CSS/SVG Swarm Orbit — radial constellation, agent dots, peer payment lines | ✅ |
| DeepSeek routing — lead agents use Claude, support agents use DeepSeek (~80% cheaper) | ✅ |
| Rate limiting (slowapi) — 10 submits/hour, prevents LLM budget abuse | ✅ |
| Input validation — Pydantic validators on budget/description | ✅ |
| Structured logging — all errors via Python logging, never print() | ✅ |
| Production CORS config — configurable via ALLOWED_ORIGINS env var | ✅ |
| Admin key required to toggle live/dry-run mode | ✅ |
| Railway deployment — 3 services: pocketbase / backend / frontend | ✅ |
| System Status Bar — live health dots (PB/ANT/SOL/TG) polled every 60s | ✅ |
| x402 Payment Rail Panel — agent, service, Solscan devnet link, amount, latency | ✅ |
| Telegram Signal Feed — chat-style UI showing live REGIS notifications in-app | ✅ |
| OWS Budget Cap visibility — ◎ SOL + USDC shown in compliance proof panel | ✅ |
| Comprehensive health endpoint — tests 6 services, returns degraded/healthy | ✅ |

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  BROWSER  Next.js 14 + TypeScript                                  │
│                                                                    │
│  TaskForm (clarify → submit) · RegisCard / CoordinatorCard         │
│  AgentCard (collapsible) × active agents · SleepingAgentCard idle  │
│  SwarmOrbit (CSS/SVG radial) · RegisConsole (probe/audit/punish)   │
│  X402Panel · TelegramPanel · MetricsBar · AuditLog · StatusBar     │
│                                                                    │
│  TanStack Query (1.2s poll) · Zustand · Framer Motion              │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ REST
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  FastAPI  (Uvicorn · slowapi rate limiting · structured logging)   │
│                                                                    │
│  POST /task/clarify    REGIS asks 2-3 context questions first      │
│  POST /task/submit     create REGIS coordinator wallet (OWS+Sol)   │
│  POST /task/decompose  Claude picks agents + tools (lock-aware)    │
│  POST /task/execute    sequential goal-compounding + quality eval  │
│  GET  /task/:id/status full snapshot (task+wallets+payments+reps)  │
│  GET  /health          6-service health check (PB/ANT/DS/SOL/TG/MP)│
│  GET  /analytics/tokens/today  24h usage stats                     │
│  POST /regis/probe     interrogate REGIS (Telegram notified)       │
│  POST /regis/audit     governance score → rep delta (Telegram)     │
│  POST /regis/punish    slash/demote/report (Telegram)              │
│                                                                    │
│  Company Tool Stack:                                               │
│  ATLAS  → Firecrawl web search + X402 micropayments               │
│  CIPHER → E2B Python sandbox + X402 micropayments                 │
│  FORGE  → E2B file write + X402 micropayments                     │
│  BISHOP → MoonPay compliance check + AML review                   │
│  SØN    → Solana devnet balance + transaction queries              │
│                                                                    │
│  Quality Engine (DeepSeek, ~80 tokens per eval):                   │
│    score 0–10 → payment = budget × (score / 10)                   │
│    avg_quality ≥ 8.0 + rep ≥ 4.5★ + 3 tasks → challenge eligible  │
└───────────────────────────┬────────────────────────────────────────┘
                            │
             ┌──────────────┼──────────────────────┐
             ▼              ▼                      ▼
    ┌──────────────┐  ┌──────────┐        ┌──────────────┐
    │  PocketBase  │  │  Solana  │        │   Telegram   │
    │  (SQLite)    │  │  devnet  │        │   Bot        │
    │  wallets     │  │  RPC     │        │              │
    │  sub_tasks   │  │  x402    │        │  Every event │
    │  payments    │  │  airdrop │        │  notified:   │
    │  audit_log   │  └──────────┘        │  payments    │
    │  reputations │                      │  failures    │
    └──────────────┘                      │  audits      │
                                          │  overthrow   │
                                          └──────────────┘
```

---

## Telegram Commands

| Command | Effect |
|---------|--------|
| `/lock ATLAS` | Lock agent — excluded from future tasks |
| `/unlock ATLAS` | Unlock agent |
| `/locked` | List all locked agents |
| `/challenge CIPHER` | Challenge REGIS for coordinator role |
| `/reputations` | Live rep scores + quality avg + lock/challenge status |
| `/status` | Latest task state |
| `/brain` | Read REGIS sovereign brain |
| `/audit` | Run governance audit on REGIS |
| `/dryrun` | Switch to dry run (mock transactions) |
| `/live` | Switch to live Solana devnet mode |
| `/solana` | Check devnet balances |
| `/moonpay` | Get onramp URL |

---

## Telegram Notifications (Real-Time)

Every critical event fires automatically:

| Event | Notification |
|-------|-------------|
| Task dispatched | Agents, lead, model routing, task ID |
| Agent completes | Quality score, model, output preview |
| Agent paid | Amount, tx hash, reputation change |
| Payment blocked | Amount, reason, reputation penalty |
| Peer payment | Sender→receiver, amount, label |
| Task complete | Paid count, total USDC disbursed, quality breakdown |
| Agent failed | Error details |
| Agent timed out | Dead man's switch fired, funds swept |
| REGIS interrogated | Q&A preview |
| REGIS audited | Score, verdict, rep delta |
| REGIS punished | Punishment type + REGIS response in character |
| REGIS challenged | Challenger scores vs REGIS governance record |
| 👑 REGIS OVERTHROWN | New coordinator crowned |

---

## Quality + Payment System

```
For each agent after execution:
  DeepSeek evaluates output (3 criteria: relevance, depth, actionability)
  score = 0.0 – 10.0
  payment = budget_allocated × (score / 10)
  FORGE additionally attempts +50% quality bonus (reputation-gated)

Eligibility for REGIS challenge:
  avg_quality ≥ 8.0 (last 10 tasks, weighted recent)
  reputation  ≥ 4.5★
  tasks_done  ≥ 3
  → Telegram fires: "⚔️ REGIS CHALLENGE ELIGIBLE"
  → Use /challenge <NAME> to trigger Claude adjudication
```

---

## Quick Demo (Live)

1. Open **[https://frontend-production-9eb4.up.railway.app](https://frontend-production-9eb4.up.railway.app)**
2. Pick a pre-loaded task (e.g. "Analyze Solana DeFi TVL across Raydium, Orca, and Jupiter")
3. Set budget (default ◎0.3 SOL), click **LAUNCH SWARM**
4. Watch the split-layout: left panel shows live audit log, right panel shows agent orbit + cards
5. FORGE will be **blocked** by the REP GATE (4-rule OWS policy chain enforced)
6. Click **OWS PROOF** on any agent card to inspect the compliance proof
7. Scroll down: the **x402 Payment Rail** panel shows Solana tx hashes → Solscan
8. The **Telegram Signal Feed** shows REGIS broadcasting each event in real time
9. Check the system status bar top-right: green dots = all services healthy

---

## Setup (Local)

### Prerequisites

- Python 3.9+
- Node.js 18+
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com)

**Optional (activates real tools):**
- DeepSeek API key — [platform.deepseek.com](https://platform.deepseek.com) (~80% cheaper for support agents)
- E2B API key — [e2b.dev](https://e2b.dev)
- Firecrawl API key — [firecrawl.dev](https://firecrawl.dev)
- Telegram Bot Token — [@BotFather](https://t.me/BotFather)

### Install

```bash
git clone https://github.com/ajayi-del/SwarmPay.git
cd SwarmPay

python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

cd frontend && npm install && cd ..
```

### Configure

```bash
cp backend/.env.example backend/.env
# Edit backend/.env
```

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional — activates real agent tools
DEEPSEEK_API_KEY=sk-...
E2B_API_KEY=e2b_...
FIRECRAWL_API_KEY=fc-...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Deployment
POCKETBASE_URL=http://localhost:8090
LIVE_MODE=false
ADMIN_API_KEY=your-secret-key   # protects /mode/toggle endpoint
ALLOWED_ORIGINS=http://localhost:3000   # comma-separated CORS origins
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
source .venv/bin/activate
python backend/setup_pocketbase.py
# Creates: wallets · tasks · sub_tasks · payments · audit_log · agent_reputation
```

---

## Railway Deployment (Production)

Three services, each deployed from its own subdirectory:

| Service | Root Dir | Builder |
|---------|----------|---------|
| pocketbase | `/pocketbase` | Dockerfile (downloads Linux AMD64 binary) |
| backend | `/backend` | Dockerfile (Python 3.11 + Rust for solders) |
| frontend | `/frontend` | Nixpacks (Node 18, `npm run build && npm start`) |

### Environment Variables

**backend:**
```
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
POCKETBASE_URL=https://<pb>.railway.app
BACKEND_URL=https://<backend>.railway.app
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
LIVE_MODE=false
ADMIN_API_KEY=...
ALLOWED_ORIGINS=https://<frontend>.railway.app
ENVIRONMENT=production
```

**frontend:**
```
NEXT_PUBLIC_API_URL=https://<backend>.railway.app
```

---

## Security

| Control | Implementation |
|---------|---------------|
| Rate limiting | slowapi: 10/hr submit, 20/hr decompose/execute, 30/hr clarify |
| Input validation | Pydantic validators: description max 2000 chars, budget max $10k |
| Record ID validation | Regex `[a-z0-9]{10,20}` — prevents PocketBase filter injection |
| Collection whitelist | Only known collections accepted |
| CORS | Configurable via `ALLOWED_ORIGINS` env var (default: `*` for dev) |
| Mode toggle | Protected by `X-Admin-Key` header |
| Error messages | Internal details never sent to client in production |
| Structured logging | All errors via Python `logging`, severity-tagged |
| Startup validation | Crashes immediately if `ANTHROPIC_API_KEY` is missing |

---

## Agent Roster

| Agent | City | Role | Model | Tools |
|-------|------|------|-------|-------|
| **REGIS** 🇬🇧 | London | Monarch · Coordinator | Claude Haiku | OWS wallets, all payments |
| **ATLAS** 🇩🇪 | Berlin | Researcher | DeepSeek / Claude | Firecrawl, X402 |
| **CIPHER** 🇯🇵 | Tokyo | Analyst | DeepSeek / Claude | E2B sandbox, X402 |
| **FORGE** 🇳🇬 | Lagos | Synthesizer | DeepSeek / Claude | E2B file write, X402 |
| **BISHOP** 🇻🇦 | Vatican | Compliance | DeepSeek / Claude | MoonPay compliance |
| **SØN** 🇸🇪 | Stockholm | Heir | DeepSeek / Claude | Solana devnet queries |

Lead agent uses Claude. Support agents use DeepSeek (~80% cheaper).  
Translation toggle: all non-English agents produce `english_text` field.

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI 0.115 · Uvicorn · Python 3.11 · slowapi |
| LLM (Lead) | Anthropic Claude Haiku 4.5 |
| LLM (Support) | DeepSeek Chat (OpenAI-compatible, ~80% cheaper) |
| Real Tools | Firecrawl web search · E2B Python sandbox · Solana devnet |
| Payment Protocol | x402 (HTTP 402 two-phase, SOL micropayments) |
| Fiat Onramp | MoonPay Buy widget (fiat→SOL) |
| DEX | Meteora DLMM → Jupiter → CoinGecko fallback |
| Persistence | PocketBase 0.22.20 (SQLite, single binary) |
| Frontend | Next.js 14 · TypeScript · Tailwind CSS · standalone output |
| State | TanStack Query v5 · Zustand v5 |
| Animation | Framer Motion v12 · CSS/SVG radial orbit (no Three.js) |
| Deployment | Railway (3 services: pocketbase / backend / frontend) |

---

*Built for the Open Wallet Standard Hackathon + Solana x402 Hackathon · April 2026*  
*Railway project: grand-fulfillment · Environment: production*
