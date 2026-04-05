# SwarmPay — Architecture & Technical Reference

**Project:** grand-fulfillment  
**Environment:** production  
**Submission:** OWS Hackathon (CAT-04 Multi-Agent Systems) · Solana x402 Hackathon

---

## 1. System Overview

SwarmPay is a governed agent economy — a payment rail where AI agents earn, get blocked, compete for sovereignty, and challenge each other for the coordinator throne, all settled on-chain via x402 micropayments on Solana devnet.

```
User → REGIS (coordinator) → [ATLAS, CIPHER, FORGE, BISHOP, SØN]
                                     ↕ sequential goal-compounding
                              OWS policy engine gates every payment
                                     ↕ x402 on Solana
                              DeepSeek quality scores each output
                                     ↕
                              Sovereignty check after every signed payment
                              BISHOP emails + Telegram + ElevenLabs voice
```

---

## 2. Full Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  BROWSER  Next.js 14 + TypeScript                                            │
│                                                                              │
│  ┌─────────────────────────┐    ┌──────────────────────────────────────────┐│
│  │ LEFT PANEL (35%)        │    │ RIGHT PANEL (65%)                        ││
│  │                         │    │                                          ││
│  │ AuditLog (terminal feed)│    │ SovereigntyPanel (live leaderboard)      ││
│  │ live event stream       │    │ RegisCard / CoordinatorCard              ││
│  │ color-coded by type     │    │ SwarmOrbit (CSS/SVG radial)              ││
│  │ SOL amounts             │    │ AgentCard × N (collapsible)              ││
│  │                         │    │ SleepingAgentCard × idle agents          ││
│  │                         │    │ X402Panel (Solscan tx links)             ││
│  │                         │    │ TelegramPanel (chat feed)                ││
│  │                         │    │ MetricsBar                               ││
│  │                         │    │ RegisConsole + voice player              ││
│  │                         │    │ SkillsPanel                              ││
│  └─────────────────────────┘    └──────────────────────────────────────────┘│
│                                                                              │
│  StatusBar (health dots) · ModeToggle · DryRunBadge · TokenTicker           │
│  TanStack Query (1.2–5s poll) · Zustand · Framer Motion v12                 │
└────────────────────────────┬─────────────────────────────────────────────────┘
                             │ REST + base64 audio
                             ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  FastAPI (Uvicorn · slowapi · X-Forwarded-For rate limiting · Python 3.11)  │
│                                                                              │
│  Task Flow:                                                                  │
│  POST /task/clarify      REGIS asks 2–3 context questions                   │
│  POST /task/submit       create REGIS OWS wallet + Solana keypair           │
│  POST /task/decompose    DeepSeek selects agents + lead                      │
│  POST /task/execute      sequential goal-compounding background task        │
│  GET  /task/:id/status   full snapshot: task+wallets+payments+reps+brain    │
│                                                                              │
│  Governance:                                                                 │
│  POST /regis/probe       REGIS answers in character + ElevenLabs voice      │
│  POST /regis/audit       DeepSeek scores governance 0–100                   │
│  POST /regis/punish      slash/demote/report → REGIS responds in character  │
│                                                                              │
│  Sovereignty:                                                                │
│  GET  /sovereignty/status      current ruler, former rulers, challenger     │
│  GET  /sovereignty/leaderboard all agents ranked by lifetime_earnings       │
│  POST /sovereignty/test-overthrow  force-trigger (admin key required)       │
│                                                                              │
│  Platform:                                                                   │
│  GET  /health            6-service check (PB/ANT/DS/SOL/TG/MP)             │
│  GET  /analytics/tokens/today  24h usage stats                              │
│  GET  /regis/meteora     live SOL/USDC rate from CoinGecko                  │
│  GET  /mode · POST /mode/toggle  dry-run vs live (admin key guard)         │
│                                                                              │
│  Security: Pydantic validators · record ID regex · ValueError→400 guard    │
│  Rate limiting: 10/hr submit · 20/hr decompose/execute · 30/hr clarify     │
└────────────────────────┬─────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────────────┬──────────────┐
          ▼              ▼                      ▼              ▼
 ┌──────────────┐ ┌──────────────┐   ┌─────────────────┐ ┌──────────┐
 │  PocketBase  │ │  Solana      │   │   Notifications  │ │ElevenLabs│
 │  (SQLite)    │ │  devnet RPC  │   │                  │ │Voice TTS │
 │              │ │              │   │  Telegram bot    │ │          │
 │  wallets     │ │  x402        │   │  (every event)   │ │ REGIS    │
 │  tasks       │ │  airdrop     │   │                  │ │ probe    │
 │  sub_tasks   │ │  OWS sign    │   │  Resend email    │ │ farewells│
 │  payments    │ └──────────────┘   │  (governance     │ │ coronat. │
 │  audit_log   │                    │   moments only)  │ └──────────┘
 │  agent_rep.  │                    │                  │
 │  sovereignty │                    │  4 email triggers│
 └──────────────┘                    │  • task receipt  │
                                     │  • critical block│
                                     │  • treasury low  │
                                     │  • punishment    │
                                     │  • overthrow     │
                                     └─────────────────┘
```

---

## 3. Autonomous Operation Flow

When all API keys are wired in, SwarmPay runs fully autonomously:

### Step 1 — Task Intake
```
User submits description + ◎ SOL budget
  → REGIS (Claude Haiku) asks 2–3 clarifying questions
  → User answers or skips
  → Budget converted: SOL × Meteora rate = USDC
  → OWS wallet created for REGIS coordinator
  → Solana keypair generated and airdropped (devnet)
  → Task record created in PocketBase
```

### Step 2 — Decomposition
```
REGIS (DeepSeek) analyzes task description
  → Selects 2–5 agents from available roster (lock-aware)
  → Assigns lead agent (uses Claude) and support agents (use DeepSeek)
  → Budget split proportionally by agent budget_share
  → Sub-task records created with per-agent descriptions
  → OWS wallets created for each sub-agent
```

### Step 3 — Sequential Execution (Goal-Compounding)
```
Agents run in priority order: ATLAS → CIPHER → FORGE → BISHOP → SØN
For each agent:
  1. 120s dead man's switch timer starts
  2. Agent executes with full context of all previous agents' outputs
  3. DeepSeek evaluates output quality (0–10 score, 3 criteria)
  4. payment = budget_allocated × (quality_score / 10)
  5. FORGE attempts +50% quality bonus (blocked by REP GATE demo)
  6. OWS 4-rule policy engine evaluates payment:
     Rule 1: REP GATE — reputation ≥ threshold for amount
     Rule 2: BUDGET CAP — never exceed coordinator allocation
     Rule 3: COORD AUTH — only REGIS coordinator can sign
     Rule 4: DOUBLE PAY — idempotency check
  7. Signed: OWS generates Solana x402 tx → payment record created
     Blocked: funds stay in treasury → audit + reputation penalty
  8. Sovereignty update: agent earnings + REGIS distributed tracked
  9. Overthrow check: if any agent earned > REGIS distributed → succession
 10. BISHOP email: critical block alert if blocked amount > 0.1 SOL
```

### Step 4 — Peer Payments (Inter-Agent Micro-Economy)
```
After all agents settle:
  ATLAS  → CIPHER  0.005 USDC  (research handoff fee)
  CIPHER → FORGE   0.003 USDC  (analysis delivery fee)
  FORGE  → BISHOP  0.002 USDC  (compliance review fee)
Peer payments bypass the coordinator policy engine.
```

### Step 5 — Settlement & Notifications
```
REGIS brain updated (append-only memory file)
Meteora rate logged at treasury close
Task marked complete in PocketBase
Telegram: full summary (paid/blocked/quality scores)
BISHOP email: task receipt (P&L, Solscan tx links, treasury remaining)
Treasury low check: if remaining < 0.1 SOL → alert email
REGIS challenge check: agents with avg_quality ≥ 8.0 + rep ≥ 4.5★ + 3 tasks
  → Telegram: "CHALLENGE ELIGIBLE — /challenge AGENTNAME"
```

### Step 6 — Governance Loop (Continuous)
```
Via Telegram commands:
  /lock ATLAS       → exclude from future tasks
  /unlock ATLAS     → restore
  /challenge CIPHER → Claude adjudicates → new REGIS crowned if challenger wins
  /audit            → DeepSeek scores REGIS 0–100 → rep delta applied
  /punish slash_treasury → 10% treasury slash → REGIS acknowledges in character
  /reputations      → live rep scores + quality avg + lock status
  /status           → latest task state
  /brain            → read REGIS sovereign brain

Via REST API:
  POST /regis/probe   → REGIS answers in character + ElevenLabs voice (audio_b64)
  POST /regis/audit   → governance score
  POST /regis/punish  → punishment + BISHOP email
```

### Step 7 — Sovereignty Succession (Automatic)
```
After every signed payment:
  sovereignty_service.update_earnings(agent, amount_usdc)
  sovereignty_service.update_distributed("REGIS", amount_usdc)
  check: if any agent.lifetime_earnings > REGIS.lifetime_distributed
         AND REGIS.lifetime_distributed > 0.5 USDC threshold:
    → execute_overthrow(winner)
    → brain_service.append_overthrow(...)
    → audit_log "overthrow" event
    → ElevenLabs: REGIS farewell speech (async, fire-and-forget)
    → ElevenLabs: new ruler coronation speech (async, concurrent)
    → BISHOP email: full succession record with margin
    → Telegram: ⚔️ OVERTHROW EVENT with kingdom succession number
```

---

## 4. Safety Measures

| Layer | Mechanism | Code Location |
|-------|-----------|---------------|
| **Input validation** | Pydantic: description ≤2000 chars, budget >0, budget ≤10000 | `routers/tasks.py` Pydantic models |
| **Injection guard** | Record ID regex `[a-z0-9]{10,20}` · collection whitelist (7 names) | `services/pocketbase.py:_validate_record_id` |
| **Exception masking** | `except (HTTPException, ValueError): raise` before broad catch | `routers/tasks.py` submit/decompose/execute |
| **Rate limiting** | slowapi: 10/hr submit, 20/hr execute, 30/hr clarify — real client IP from X-Forwarded-For | `main.py:_real_client_ip` |
| **Error surface** | Global handler returns `{"detail": "Internal server error"}` — no stack traces to client | `main.py:global_exception_handler` |
| **Auth** | X-Admin-Key header guards mode toggle + test-overthrow | `main.py`, `routers/sovereignty.py` |
| **Payment integrity** | 4-rule OWS policy chain — REP/BUDGET/AUTH/DOUBLE-PAY | `services/policy_service.py` |
| **Dead man's switch** | 120s timeout → OWS key revoked → budget swept to coordinator | `routers/tasks.py:_trigger_dead_mans_switch` |
| **Dry-run default** | `LIVE_MODE=false` — mock signatures, no real Solana spend | `services/ows_service.py` |
| **CORS** | Configurable `ALLOWED_ORIGINS` — production restricts to Railway frontend URL | `main.py` |
| **Structured logging** | All errors via `logger.*` — zero `print()` in production paths | All services |
| **Startup crash-fast** | Missing `ANTHROPIC_API_KEY` → process exits at startup | `main.py:_validate_env` |
| **Non-blocking emails** | `asyncio.create_task(asyncio.to_thread(...))` — email failures never block task execution | `routers/tasks.py` |
| **Non-blocking voice** | ElevenLabs called fire-and-forget — TTS failure never blocks probe response | `routers/regis.py` |
| **Sovereignty isolation** | Overthrow check is thread-safe (`threading.Lock`) + idempotent | `services/sovereignty_service.py` |

---

## 5. Technical Debt Register

### Fixed This Session (Production-Grade)
| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| B1 | `except Exception` swallowed `ValueError`, returned 500 for injection attempts | Critical | `except (HTTPException, ValueError): raise` in submit/decompose/execute |
| B2 | `/execute` passed unvalidated task_id to background task | High | `_validate_record_id(body.task_id)` added before `add_task()` |
| B3 | `print()` in pocketbase.py (7 occurrences) bypassed structured logging | Medium | All replaced with `logger.error()` |
| B4 | Rate limiter used proxy IP — all clients shared one bucket on Railway | Medium | `_real_client_ip()` reads `X-Forwarded-For` header |

### Known Remaining Debts
| # | Issue | Severity | Impact |
|---|-------|----------|--------|
| B5 | `x402_payments` in agent output is LLM-generated, not verified on-chain | Medium | x402 panel shows unverified data in dry-run mode |
| B6 | `_FALLBACK_SOL_USDC_RATE = 79.0` hardcoded for email threshold conversions | Low | Email alerts use stale rate — clearly labeled, not used for settlement |
| B7 | Coordinator wallet `balance` field not decremented after payments | Low | Balance in DB is stale; Solana RPC is authoritative in live mode |
| B8 | PocketBase filter_params uses f-string interpolation (no parameterized queries) | Medium | Partially mitigated by record ID regex — PocketBase HTTP API has no parameterized query support |
| B9 | `brain_service.append()` called both directly and via `to_thread` inconsistently | Low | Brain writes should always go via `to_thread` since BrainService is file I/O |
| F1 | `StatusBar.tsx` duplicates `API_BASE` constant vs importing from `api.ts` | Low | `api.ts` doesn't export `API_BASE` — minor duplication |
| F2 | `useSolRate` singleton `_cachedRate` persists for page lifetime without TTL | Low | Stale rate after >1hr session; add `staleTime: 3_600_000` |
| F3 | `X402Panel` second filter condition `tx_hash.length > 10` matches all dry-run payments | Medium | Tighten: only show payments where policy_reason includes "x402" OR tx_hash is 88-char base58 |
| F4 | `SovereigntyPanel` threshold line position uses hardcoded `0.82` multiplier for inner width | Low | Should compute from actual DOM width — visual-only issue |

---

## 6. Service Inventory

| Service | File | Responsibility |
|---------|------|----------------|
| AgentService | `services/agent_service.py` | LLM execution per agent persona, tool dispatch |
| PolicyService | `services/policy_service.py` | 4-rule OWS payment gate |
| QualityService | `services/quality_service.py` | DeepSeek 0–10 output scoring |
| OWSService | `services/ows_service.py` | Wallet creation, payment signing |
| SolanaService | `services/solana_service.py` | Keypair generation, devnet airdrop |
| PocketBaseService | `services/pocketbase.py` | DB CRUD + record ID validation |
| BrainService | `services/brain_service.py` | Append-only REGIS memory file |
| ModelService | `services/model_service.py` | DeepSeek primary, Claude fallback |
| TelegramService | `services/telegram_service.py` | Bot polling + notification gate |
| MeteoraService | `services/meteora_service.py` | Live SOL/USDC rate |
| MoonPayService | `services/moonpay_service.py` | Fiat onramp info |
| EmailService | `services/email_service.py` | BISHOP governance emails via Resend |
| VoiceService | `services/voice_service.py` | ElevenLabs TTS for governance moments |
| SovereigntyService | `services/sovereignty_service.py` | Lifetime earnings, overthrow mechanics |
| AgentLockService | `services/agent_lock_service.py` | Lock/unlock agents via Telegram |

---

## 7. Database Schema (PocketBase / SQLite)

```
wallets          id, name, role, eth_address, sol_address, budget_cap, balance, api_key_id
tasks            id, description, total_budget, status, coordinator_wallet_id
sub_tasks        id, task_id, agent_id, wallet_id, description, budget_allocated, status, output, is_lead
payments         id, from_wallet_id, to_wallet_id, amount, chain_id, status, policy_reason, tx_hash
audit_log        id, event_type, entity_id, message, metadata (JSON)
agent_reputation id, agent_id, current_reputation, tasks_completed, tasks_failed
sovereignty      id, agent_id, lifetime_earnings_usdc, lifetime_distributed_usdc,
                    is_ruler, times_ruled, overthrow_count, ascended_at, deposed_at
```

---

## 8. Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...         # Claude Haiku — REGIS reasoning + challenge adjudication

# Strongly recommended
DEEPSEEK_API_KEY=sk-...              # Primary LLM for all agents (~80% cheaper than Claude)
POCKETBASE_URL=https://...           # PocketBase instance URL

# Agent tools
E2B_API_KEY=e2b_...                  # CIPHER (Python sandbox) + FORGE (file write)
FIRECRAWL_API_KEY=fc-...             # ATLAS web search with real source URLs

# Notifications
TELEGRAM_BOT_TOKEN=...               # @BotFather
TELEGRAM_CHAT_ID=...                 # Your chat ID (/start to @userinfobot)
RESEND_API_KEY=re_...                # Resend.com — BISHOP governance emails
BISHOP_EMAIL_TO=you@domain.com       # Governance receipts destination
BISHOP_EMAILS_ENABLED=true

# Voice
ELEVENLABS_API_KEY=sk_...            # ElevenLabs TTS — REGIS probe + overthrow speeches

# Sovereignty thresholds
CRITICAL_BLOCK_THRESHOLD_SOL=0.1     # Email alert when blocked payment > this
TREASURY_LOW_THRESHOLD_SOL=0.1       # Email alert when treasury drops below this

# Solana
SOLANA_RPC_URL=https://api.devnet.solana.com

# Mode
LIVE_MODE=false                      # true = real Solana devnet transactions
ADMIN_API_KEY=change-me              # Guards /mode/toggle + /sovereignty/test-overthrow

# Deployment
ENVIRONMENT=production               # Hides /docs, strict error handling
ALLOWED_ORIGINS=https://...          # CORS origin whitelist
BACKEND_URL=https://...              # Self-reference for Telegram bot
```

---

## 9. Email Triggers (BISHOP)

| Trigger | Subject | Condition |
|---------|---------|-----------|
| Task Receipt | `⛪ DECREE — Task Complete: {task}` | Every task completion |
| Critical Block | `🚨 CRITICAL BLOCK — {agent} ◎{amount} SOL` | Blocked payment > 0.1 SOL |
| Treasury Low | `⚠️ TREASURY LOW — ◎{balance} SOL remaining` | Treasury < 0.1 SOL after settlement |
| Punishment | `⚔️ REGIS PENALIZED — {type}` | Any REGIS punishment applied |
| Overthrow | `⚔️ OVERTHROW — {agent} seizes the throne` | Sovereignty succession event |

All email calls are `asyncio.create_task(asyncio.to_thread(...))` — fire-and-forget. Email failure never blocks task execution.

---

## 10. Voice Triggers (ElevenLabs)

| Trigger | Agent | Text Source | API Endpoint |
|---------|-------|-------------|--------------|
| Probe response | REGIS | Probe answer (≤500 chars) | `POST /regis/probe` → `audio_b64` |
| Overthrow farewell | Deposed ruler | LLM-generated 2-sentence farewell | Fired via `notify_overthrow()` |
| Coronation speech | New ruler | LLM-generated 2-sentence coronation | Fired via `notify_overthrow()` |

Voice is enhancement-only: `speak()` returns `None` when `ELEVENLABS_API_KEY` unset.  
Frontend `▶ voice` button appears on REGIS messages only when `audio_b64` is non-null.

---

## 11. Sovereignty System

**Rule**: If any agent's `lifetime_earnings_usdc` > REGIS's `lifetime_distributed_usdc` (and REGIS has distributed ≥ 0.5 USDC), an overthrow fires.

**Lifecycle**:
```
1. Every signed payment → update_earnings(agent) + update_distributed("REGIS")
2. check_and_execute_overthrow() — thread-safe, idempotent
3. If triggered:
   a. Old ruler: is_ruler=false, overthrow_count++, deposed_at=now
   b. New ruler: is_ruler=true, times_ruled++, ascended_at=now
   c. Brain: SUCCESSION_EVENT appended
   d. Audit log: "overthrow" event created
   e. notify_overthrow(): telegram + email + voice (all concurrent, all fire-and-forget)
```

**Test**: `POST /sovereignty/test-overthrow` with `X-Admin-Key` sets target agent earnings just above threshold and runs the real check flow end-to-end.

---

*SwarmPay — April 2026 · Railway: grand-fulfillment · Built for OWS CAT-04 + Solana x402 Hackathons*
