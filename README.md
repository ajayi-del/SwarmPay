# SwarmPay

## 🚀 Live Demo — Test It Now

> **[→ LAUNCH DEMO](https://frontend-production-9eb4.up.railway.app)** · Pick a task · Set budget · Watch 5 agents work and pay each other in real time on Solana devnet

| Service | Live URL |
|---------|----------|
| **🌐 Frontend (Demo)** | **[https://frontend-production-9eb4.up.railway.app](https://frontend-production-9eb4.up.railway.app)** |
| **⚙️ Backend API** | **[https://backend-production-4717.up.railway.app](https://backend-production-4717.up.railway.app)** |
| **📊 PocketBase DB** | [https://pocketbase-production-bd4d.up.railway.app](https://pocketbase-production-bd4d.up.railway.app) |
| **📖 API Docs** | [https://backend-production-4717.up.railway.app/docs](https://backend-production-4717.up.railway.app/docs) |
| **🚂 Railway Project** | [grand-fulfillment · production](https://railway.com/project/78995748-b3fa-4f04-9a6d-d7bcfe2adb41) |

```
Quick test (30 seconds):
1. Open https://frontend-production-9eb4.up.railway.app
2. Pick "Analyze DeFi TVL across Raydium, Orca, and Jupiter"
3. Click LAUNCH SWARM → watch FORGE get blocked by the REP GATE
4. Click OWS PROOF on any agent card → see the live compliance chain
5. Check the x402 Payment Rail → click any tx hash → opens Solscan devnet
```

---

**Project:** grand-fulfillment · **Environment:** production  
**Submitted to:** OWS Hackathon (Category 04 — Multi-Agent Systems) · Solana x402 Hackathon (Track: Best Trustless Agent Economy)

> REGIS, a sovereign coordinator wallet, decomposes tasks across five specialised sub-agents. Each agent operates with a scoped OWS wallet, real Solana devnet keypair, quality-scored outputs, and a 120-second heartbeat dead man's switch. Payments scale with output quality (0–10). Agents compete for REGIS's coordinator role through lifetime earnings. Every decision is audited, every key can be revoked, every event fires to Telegram and email in real time. The agent who earns more than REGIS distributes seizes the throne — complete with farewell and coronation speeches via ElevenLabs.

---

## Quick Demo (Live)

1. Open **https://frontend-production-9eb4.up.railway.app**
2. Pick a pre-loaded Solana task (e.g. "Analyze DeFi TVL across Raydium, Orca, and Jupiter")
3. Set budget (default ◎0.3 SOL), click **LAUNCH SWARM →**
4. Watch the split layout: left = live audit terminal, right = agent orbit + sovereignty race
5. **FORGE will be blocked** by the REP GATE (OWS 4-rule policy chain, live demo)
6. Click **OWS PROOF** on any agent card → compliance chain with ◎ SOL budget_cap
7. **x402 Payment Rail** panel shows Solana tx hashes → Solscan devnet links
8. **Telegram Signal Feed** shows REGIS broadcasting each event in real time
9. Check **StatusBar** (top right) — green dots = all 6 services healthy
10. Open **REGIS Console** → interrogate REGIS → hear the response via ElevenLabs voice
11. The **⚔️ Race to Sovereignty** panel shows the live earnings leaderboard

---

## What Was Built

| Feature | Status |
|---------|--------|
| Reputation-Gated Policy Engine (4-rule OWS chain) | ✅ |
| Goal-Compounding Agent Execution (ATLAS→CIPHER→FORGE→BISHOP→SØN) | ✅ |
| Quality-Scaled Payments — DeepSeek scores each agent 0–10, payment = budget × score | ✅ |
| REGIS Challenge System — top agents can overthrow REGIS via Claude adjudication | ✅ |
| Sovereignty System — agents earn throne by outearning REGIS's distributions | ✅ |
| ElevenLabs Voice — REGIS speaks probe answers; farewells and coronations on overthrow | ✅ |
| BISHOP Email System — 5 governance triggers via Resend (task receipt, block, treasury, punish, overthrow) | ✅ |
| Telegram Umbilical Cord — every payment, failure, audit, punishment, and overthrow fires to Telegram | ✅ |
| Agent Lock/Unlock via Telegram (`/lock ATLAS`, `/unlock ATLAS`, `/locked`) | ✅ |
| Clarifying Questions — REGIS asks 2–3 context questions before dispatching | ✅ |
| REGIS Sovereign Brain — append-only memory, probe/audit/punish system | ✅ |
| Dead Man's Switch — 120s heartbeat, key revocation, budget sweep | ✅ |
| Sleeping Agent Visualization — non-summoned agents render dormant | ✅ |
| ATLAS — Firecrawl web search + real sources + German research reports | ✅ |
| CIPHER — E2B Python sandbox + quantitative analysis in Japanese | ✅ |
| FORGE — E2B file write + downloadable markdown report | ✅ |
| BISHOP — MoonPay compliance check + AML review in Italian/Latin | ✅ |
| SØN — Solana devnet balance queries + recent transaction lookup | ✅ |
| x402 Micropayments on Solana devnet | ✅ |
| x402 Payment Rail Panel — agent, service, Solscan tx link, ◎ amount, latency | ✅ |
| Meteora DLMM live SOL/USDC rate | ✅ |
| MoonPay fiat→SOL onramp widget | ✅ |
| Inter-Agent Peer Payments — ATLAS→CIPHER→FORGE→BISHOP micro-economy | ✅ |
| Sovereignty Dashboard — live ⚔️ leaderboard, threshold line, succession history | ✅ |
| Kingdom / Office Mode Toggle | ✅ |
| CSS/SVG Swarm Orbit — radial constellation, agent dots, peer payment lines | ✅ |
| Telegram Signal Feed — Telegram-style chat UI in the dashboard | ✅ |
| System Status Bar — live PB/ANT/SOL/TG health dots, polls every 60s | ✅ |
| OWS Budget Cap visibility — ◎ SOL + USDC in compliance proof panel | ✅ |
| Comprehensive health endpoint — 6 services, returns healthy/degraded | ✅ |
| DeepSeek routing — all agents use DeepSeek (~80% cheaper than Claude) | ✅ |
| Rate limiting (slowapi) — per real client IP via X-Forwarded-For | ✅ |
| Input validation — Pydantic validators on budget/description | ✅ |
| Exception masking fixed — ValueError returns 400, not 500 | ✅ |
| Railway deployment — 3 services: pocketbase / backend / frontend | ✅ |

---

## Architecture

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for the full technical reference including:
- Complete system diagram
- Autonomous operation flow (7 phases)
- Safety measures table
- Technical debt register
- Database schema
- All environment variables

```
┌─────────────────────────────────────────────────────────────────┐
│  Next.js 14 — Split Layout (35% audit | 65% kingdom)            │
│  SovereigntyPanel · SwarmOrbit · AgentCard · X402Panel           │
│  TelegramPanel · RegisConsole (+ voice) · StatusBar              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST + base64 audio
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI — Task · Regis · Audit · Sovereignty routers            │
│  OWS policy engine · DeepSeek quality scoring                    │
│  Sovereignty service · Voice service · Email service             │
└──────────────┬────────────────────┬──────────┬──────────────────┘
               ▼                    ▼          ▼
        PocketBase          Solana devnet   Resend · ElevenLabs
        (7 collections)     x402 payments   Telegram Bot
```

---

## Sovereignty System

The crown is earned, not appointed. After every signed payment:

1. Agent's `lifetime_earnings_usdc` increments
2. REGIS's `lifetime_distributed_usdc` increments  
3. If any agent's earnings exceed REGIS's total distributions (and REGIS has distributed ≥ 0.5 USDC):
   - **Overthrow fires** — sovereignty transfers atomically in PocketBase
   - REGIS delivers a farewell speech via ElevenLabs
   - New ruler delivers a coronation speech via ElevenLabs
   - BISHOP sends succession email with full margin breakdown
   - Telegram fires `⚔️ OVERTHROW EVENT` with succession number
   - Brain file records `SUCCESSION_EVENT` permanently

Test it: `POST /sovereignty/test-overthrow` with `X-Admin-Key` header.

---

## BISHOP Email Triggers

| Email | Subject | When |
|-------|---------|------|
| Task Receipt | `⛪ DECREE — Task Complete` | Every completed task — full P&L, Solscan links |
| Critical Block | `🚨 CRITICAL BLOCK — {agent}` | Blocked payment > 0.1 SOL |
| Treasury Low | `⚠️ TREASURY LOW — ◎{balance}` | Treasury drops below threshold |
| Punishment | `⚔️ REGIS PENALIZED` | Any REGIS punishment applied |
| Overthrow | `⚔️ OVERTHROW — {agent} seizes throne` | Sovereignty succession |

Sent from `BISHOP <onboarding@resend.dev>` via Resend free tier.

---

## ElevenLabs Voice

| Moment | Agent | Text |
|--------|-------|------|
| Probe response | REGIS (Daniel — deep British) | Answer spoken aloud; `▶ voice` button in console |
| Overthrow farewell | Deposed ruler | LLM-generated 2-sentence farewell, in character |
| Coronation speech | New ruler | LLM-generated 2-sentence coronation, in character |

Voice is graceful-degradation: returns `null` when `ELEVENLABS_API_KEY` is absent — never blocks a response.

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
  → Telegram fires: "⚔️ CHALLENGE ELIGIBLE"
  → Use /challenge <NAME> to trigger Claude adjudication
```

---

## Setup (Local)

### Prerequisites
- Python 3.9+, Node.js 18+
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com)

**Optional (activates real tools):**
- DeepSeek API key — [platform.deepseek.com](https://platform.deepseek.com)
- E2B API key — [e2b.dev](https://e2b.dev)
- Firecrawl API key — [firecrawl.dev](https://firecrawl.dev)
- Telegram Bot Token — [@BotFather](https://t.me/BotFather)
- Resend API key — [resend.com](https://resend.com)
- ElevenLabs API key — [elevenlabs.io](https://elevenlabs.io)

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
# Edit backend/.env — see docs/ARCHITECTURE.md §8 for all variables
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
# Creates: wallets · tasks · sub_tasks · payments · audit_log · agent_reputation · sovereignty
```

---

## Railway Deployment (Production)

Three services, each deployed from its own subdirectory:

| Service | Root Dir | Builder |
|---------|----------|---------|
| pocketbase | `/pocketbase` | Dockerfile |
| backend | `/backend` | Dockerfile (Python 3.11 + Rust for solders) |
| frontend | `/frontend` | Dockerfile (Node 18, `--legacy-peer-deps`) |

### Environment Variables — backend (Railway)

```
ANTHROPIC_API_KEY · DEEPSEEK_API_KEY · POCKETBASE_URL · BACKEND_URL
TELEGRAM_BOT_TOKEN · TELEGRAM_CHAT_ID
RESEND_API_KEY · BISHOP_EMAIL_TO · BISHOP_EMAILS_ENABLED=true
ELEVENLABS_API_KEY
E2B_API_KEY · FIRECRAWL_API_KEY · MOONPAY_API_KEY
LIVE_MODE=false · ADMIN_API_KEY · ALLOWED_ORIGINS · ENVIRONMENT=production
```

**frontend:** `NEXT_PUBLIC_API_URL=https://<backend>.railway.app`

---

## Security

| Control | Implementation |
|---------|---------------|
| Rate limiting | slowapi per real client IP (X-Forwarded-For): 10/hr submit, 20/hr execute |
| Input validation | Pydantic: description ≤2000 chars, budget >0 and ≤10000 |
| Record ID validation | Regex `[a-z0-9]{10,20}` — prevents PocketBase filter injection |
| Exception masking fix | `except (HTTPException, ValueError): raise` before broad catch |
| Collection whitelist | Only 7 known collections accepted |
| CORS | `ALLOWED_ORIGINS` env var — production restricts to Railway frontend |
| Mode toggle | Protected by `X-Admin-Key` header |
| Error messages | Internal details never sent to client in production |
| Dead man's switch | 120s heartbeat → API key revoked → budget swept to treasury |
| Structured logging | All errors via Python `logging`, zero `print()` in prod paths |
| Startup validation | Crashes immediately if `ANTHROPIC_API_KEY` missing |

---

## Agent Roster

| Agent | City | Role | Model | Voice |
|-------|------|------|-------|-------|
| **REGIS** 🇬🇧 | London | Monarch · Coordinator | Claude Haiku | Daniel (ElevenLabs) |
| **ATLAS** 🇩🇪 | Berlin | Researcher | DeepSeek | Arnold (ElevenLabs) |
| **CIPHER** 🇯🇵 | Tokyo | Analyst | DeepSeek | Adam (ElevenLabs) |
| **FORGE** 🇳🇬 | Lagos | Synthesizer | DeepSeek | Josh (ElevenLabs) |
| **BISHOP** 🇻🇦 | Vatican | Compliance | DeepSeek | Callum (ElevenLabs) |
| **SØN** 🇸🇪 | Stockholm | Heir | DeepSeek | Sam (ElevenLabs) |

Lead agent uses Claude Haiku. Support agents use DeepSeek (~80% cheaper).

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI 0.115 · Uvicorn · Python 3.11 · slowapi |
| LLM (Lead) | Anthropic Claude Haiku 4.5 |
| LLM (All agents) | DeepSeek Chat (OpenAI-compatible, ~80% cheaper) |
| Real Tools | Firecrawl web search · E2B Python sandbox · Solana devnet |
| Payment Protocol | x402 (HTTP 402 two-phase, SOL micropayments) |
| Fiat Onramp | MoonPay Buy widget (fiat→SOL) |
| DEX Rate | Meteora DLMM → Jupiter → CoinGecko fallback |
| Voice | ElevenLabs eleven_multilingual_v2 |
| Email | Resend (BISHOP governance notifications) |
| Persistence | PocketBase 0.22.20 (SQLite, single binary, 7 collections) |
| Frontend | Next.js 14 · TypeScript · Tailwind CSS · standalone output |
| State | TanStack Query v5 · Zustand v5 |
| Animation | Framer Motion v12 · CSS/SVG radial orbit (no Three.js) |
| Deployment | Railway (3 services: pocketbase / backend / frontend) |

---

*Built for the Open Wallet Standard Hackathon + Solana x402 Hackathon · April 2026*  
*Railway project: grand-fulfillment · Environment: production*  
*Full technical reference: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)*
