"""
Task Router - Handles all task-related endpoints.

Rate limits (per IP):
  /task/submit   — 10/hour  (LLM cost protection)
  /task/decompose — 20/hour
  /task/execute  — 20/hour
  /task/clarify  — 30/hour
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.pocketbase import PocketBaseService, _validate_record_id, _safe_filter
from services.ows_service import OWSService
from services.agent_service import AgentService, AGENT_PERSONAS, EXECUTION_ORDER
from services.policy_service import PolicyService, get_rep_multiplier, is_probation
from services.brain_service import brain_service
from services.solana_service import solana_service
from services.agent_lock_service import filter_available, is_locked
from services.quality_service import evaluate_work, qualifies_for_challenge, run_regis_challenge
from services.email_service import (
    send_critical_block,
    send_task_receipt,
    send_treasury_low,
    CRITICAL_BLOCK_THRESHOLD_SOL,
    TREASURY_LOW_THRESHOLD_SOL,
)
from services.sovereignty_service import sovereignty_service, notify_overthrow
from services.uniblock_service import get_gas_price
from services.moonpay_service import get_live_sol_usdc_rate
from services.payment_verification_service import payment_verification_service, PaymentData
import time

# Safety limits for agent payouts
logger = logging.getLogger("swarmpay.tasks")
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/task", tags=["tasks"])


class TaskSubmitRequest(BaseModel):
    description: str
    budget: float

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("description cannot be empty")
        if len(v) > 2000:
            raise ValueError("description too long (max 2000 chars)")
        return v

    @field_validator("budget")
    @classmethod
    def budget_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("budget must be positive")
        if v > 10000:
            raise ValueError("budget exceeds maximum ($10,000 USDC)")
        return round(v, 6)

class TaskSubmitResponse(BaseModel):
    task_id: str
    coordinator_wallet: Dict[str, Any]

class TaskDecomposeRequest(BaseModel):
    task_id: str

class TaskDecomposeResponse(BaseModel):
    sub_tasks: List[Dict[str, Any]]
    agent_wallets: List[Dict[str, Any]]

class TaskExecuteRequest(BaseModel):
    task_id: str

class TaskExecuteResponse(BaseModel):
    status: str

pb = PocketBaseService()
ows = OWSService()
agent_service = AgentService()
policy_service = PolicyService()


async def _audit(event_type: str, entity_id: str, message: str, metadata: dict = None):
    """Fire-and-forget audit log write (non-blocking via thread pool)."""
    await asyncio.to_thread(pb.create, "audit_log", {
        "event_type": event_type,
        "entity_id": entity_id,
        "message": message,
        "metadata": metadata or {},
    })


class TaskClarifyRequest(BaseModel):
    description: str

class TaskClarifyResponse(BaseModel):
    questions: List[str]
    needs_clarification: bool
    suggested_budget: float

@router.post("/clarify", response_model=TaskClarifyResponse)
@limiter.limit("30/hour")
async def clarify_task(request: Request, body: TaskClarifyRequest):
    """
    REGIS asks 2-3 context questions before task starts.
    Returns empty list if task description is already clear enough.
    """
    try:
        from services.model_service import call_deepseek
        prompt = (
            f'Task description: "{body.description}"\n\n'
            "You are REGIS, SwarmPay coordinator. Analyze this task.\n"
            "Available services: OWS (wallets/payments), Solana (blockchain), "
            "MoonPay (fiat onramp), X402 (micropayments), Firecrawl (web search), E2B (code execution).\n\n"
            "Determine:\n"
            "1. Does this task need clarification? (missing: budget, target, deadline, specific metric?)\n"
            "2. If yes, write 2-3 SHORT clarifying questions (one line each)\n"
            "3. Suggest a USD budget based on complexity\n\n"
            "JSON only:\n"
            '{"needs_clarification": true, "questions": ["Q1", "Q2"], "suggested_budget": 5.0}'
        )
        raw = await asyncio.to_thread(call_deepseek, prompt, 300)
        s, e = raw.find("{"), raw.rfind("}") + 1
        if s != -1 and e > s:
            parsed = json.loads(raw[s:e])
            return TaskClarifyResponse(
                questions=parsed.get("questions", [])[:3],
                needs_clarification=bool(parsed.get("needs_clarification", False)),
                suggested_budget=float(parsed.get("suggested_budget", 5.0)),
            )
    except Exception as exc:
        logger.warning("[clarify] %s", exc)
    return TaskClarifyResponse(questions=[], needs_clarification=False, suggested_budget=5.0)


@router.post("/submit", response_model=TaskSubmitResponse)
@limiter.limit("10/hour")
async def submit_task(request: Request, body: TaskSubmitRequest):
    """Submit a new task and create REGIS coordinator wallet."""
    try:
        ows_wallet = await asyncio.to_thread(ows.create_wallet, f"REGIS-{uuid.uuid4().hex[:6]}")
        sol_wallet = await asyncio.to_thread(solana_service.generate_and_fund)

        wallet_record = await asyncio.to_thread(pb.create, "wallets", {
            "name": ows_wallet["name"],
            "role": "coordinator",
            "eth_address": ows_wallet["eth_address"],
            "sol_address": sol_wallet["pubkey"],
            "budget_cap": body.budget,
            "balance": body.budget,
            "api_key_id": f"regis_api_{uuid.uuid4().hex[:8]}",
        })
        solana_service.register(wallet_record["id"], sol_wallet["privkey_hex"])

        task_record = await asyncio.to_thread(pb.create, "tasks", {
            "description": body.description,
            "total_budget": body.budget,
            "status": "pending",
            "coordinator_wallet_id": wallet_record["id"],
        })

        await _audit(
            "task_submitted",
            task_record["id"],
            f"REGIS accepted task: {body.description[:60]}",
            {"budget": body.budget, "coordinator_wallet": wallet_record["id"]},
        )

        # Autonomous economy: create a bounty on the board for agent bidding
        try:
            from services.bounty_service import create_bounty
            await asyncio.to_thread(create_bounty, pb, task_record["id"], body.description, body.budget)
        except Exception:
            pass

        return TaskSubmitResponse(task_id=task_record["id"], coordinator_wallet=wallet_record)

    except (HTTPException, ValueError):
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")


@router.post("/decompose", response_model=TaskDecomposeResponse)
@limiter.limit("20/hour")
async def decompose_task(request: Request, body: TaskDecomposeRequest):
    """Deterministically decompose task — DeepSeek picks the right agents, not all 5."""
    try:
        _validate_record_id(body.task_id)
        task = await asyncio.to_thread(pb.get, "tasks", body.task_id)

        # Step 1: Claude analyzes task → picks which agents to spawn + who leads
        # Filter out locked agents before analysis
        from services.agent_service import ALL_AGENT_NAMES
        available = filter_available(ALL_AGENT_NAMES)
        analysis = await asyncio.to_thread(
            agent_service.analyze_task_for_agents, task["description"], available,
            float(task.get("total_budget", 0))
        )
        selected_agents = analysis["agents"]
        lead_agent      = analysis["lead"]
        subtask_descs   = analysis["subtasks"]

        # Step 2: Build sub-task data with customized descriptions
        sub_tasks_raw = await asyncio.to_thread(
            agent_service.decompose_task,
            task["description"], task["total_budget"],
            selected_agents, lead_agent,
        )
        # Inject Claude's per-agent descriptions
        for st in sub_tasks_raw:
            if st["name"] in subtask_descs:
                st["description"] = subtask_descs[st["name"]]

        async def _create_bundle(i: int, st_data: Dict) -> tuple:
            """Parallel: create OWS + Solana wallet + PocketBase record + sub_task."""
            persona = st_data["persona"]
            slug = body.task_id[-6:]

            ows_w, sol_w = await asyncio.gather(
                asyncio.to_thread(ows.create_wallet, f"{persona['name'].lower()}-{slug}"),
                asyncio.to_thread(solana_service.generate_and_fund),
            )
            api_key = await asyncio.to_thread(ows.create_api_key, ows_w["id"], st_data["budget_allocated"])

            wallet_rec = await asyncio.to_thread(pb.create, "wallets", {
                "name": ows_w["name"],
                "role": "sub-agent",
                "eth_address": ows_w["eth_address"],
                "sol_address": sol_w["pubkey"],
                "budget_cap": st_data["budget_allocated"],
                "balance": 0,
                "api_key_id": api_key,
            })
            solana_service.register(wallet_rec["id"], sol_w["privkey_hex"])

            st_rec = await asyncio.to_thread(pb.create, "sub_tasks", {
                "task_id": body.task_id,
                "agent_id": persona["name"],          # "ATLAS", "CIPHER", …
                "wallet_id": wallet_rec["id"],
                "description": st_data["description"],
                "budget_allocated": st_data["budget_allocated"],
                "status": "spawned",
                "is_lead": st_data.get("is_lead", False),
            })

            await _audit(
                "agent_spawned",
                st_rec["id"],
                f"{persona['name']} spawned · {persona['flag']} {persona['city']} | wallet {wallet_rec['id'][:8]}",
                {"agent": persona["name"], "wallet": wallet_rec["id"]},
            )
            return wallet_rec, st_rec

        # ── Selected agent bundles in parallel ───────────────────────────
        results = await asyncio.gather(*[_create_bundle(i, st) for i, st in enumerate(sub_tasks_raw)])

        agent_wallets = [r[0] for r in results]
        sub_tasks = [r[1] for r in results]

        await asyncio.to_thread(pb.update, "tasks", body.task_id, {"status": "decomposed"})

        return TaskDecomposeResponse(sub_tasks=sub_tasks, agent_wallets=agent_wallets)

    except (HTTPException, ValueError):
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decompose task: {str(e)}")


@router.post("/execute", response_model=TaskExecuteResponse)
@limiter.limit("20/hour")
async def execute_task(request: Request, body: TaskExecuteRequest, background_tasks: BackgroundTasks):
    """Kick off parallel execution in the background."""
    try:
        _validate_record_id(body.task_id)   # guard before handing to background task
        background_tasks.add_task(execute_task_background, body.task_id)
        return TaskExecuteResponse(status="running")
    except (HTTPException, ValueError):
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start execution: {str(e)}")


async def _notify_telegram(message: str) -> None:
    """Direct send — only for backward compat; prefer _notify_event."""
    try:
        from services.telegram_service import send, ALLOWED_CHAT_ID
        await send(ALLOWED_CHAT_ID, message)
    except Exception as e:
        logger.warning("[tg notify] %s", e)


async def _check_sovereignty_overthrow() -> None:
    """Fire-and-forget sovereignty check after each signed payment."""
    try:
        from services.sovereignty_service import sovereignty_service, notify_overthrow
        overthrow = await asyncio.to_thread(sovereignty_service.check_and_execute_overthrow)
        if overthrow:
            if overthrow.get("pending"):
                cand_id = overthrow["new_ruler"].get("agent_id", "")
                await _notify_event("pending_overthrow",
                    f"🚨 TREASON DETECTED 🚨\n"
                    f"──────────────────────\n"
                    f"{cand_id} has mathematically surpassed REGIS and is attempting an overthrow!\n\n"
                    f"Human Sovereign, you must decide:\n"
                    f"Type /approve {cand_id} to accept succession\n"
                    f"Type /veto {cand_id} to punish them and slash earnings."
                )
            else:
                await notify_overthrow(overthrow)
    except Exception as exc:
        logger.warning("[sovereignty] overthrow check: %s", exc)

async def _notify_event(event_type: str, message: str) -> None:
    """Send Telegram notification through NotificationGate (signal events only)."""
    try:
        from services.telegram_service import notify_event
        await notify_event(event_type, message)
    except Exception as e:
        logger.warning("[tg event] %s", e)


async def execute_task_background(task_id: str):
    """
    Goal-compounding sequential execution:
      1. Agents run in priority order (ATLAS→CIPHER→FORGE→BISHOP→SØN)
      2. Each agent receives a context summary of all previous agents' outputs
      3. Quality is evaluated post-execution; payment scales with quality (0-10)
      4. Telegram notifications at key milestones (Telegram as umbilical cord)
      5. REGIS challenge check after task completion
    """
    try:
        task = await asyncio.to_thread(pb.get, "tasks", task_id)
        sub_tasks = await asyncio.to_thread(pb.list, "sub_tasks", filter_params=_safe_filter("task_id", task_id))
        coordinator_wallet = await asyncio.to_thread(pb.get, "wallets", task["coordinator_wallet_id"])
        task_goal = task.get("description", "")

        await asyncio.to_thread(pb.update, "tasks", task_id, {"status": "in_progress"})

        # Silent during execution — one completion signal at the end
        agent_names = [st["agent_id"] for st in sub_tasks]
        lead_agent  = next((st["agent_id"] for st in sub_tasks if st.get("is_lead")), agent_names[0] if agent_names else "?")

        # Sort by EXECUTION_ORDER for goal-compounding
        def _exec_priority(st: Dict) -> int:
            name = st.get("agent_id", "")
            return EXECUTION_ORDER.index(name) if name in EXECUTION_ORDER else 99

        ordered_sub_tasks = sorted(sub_tasks, key=_exec_priority)

        # Shared context: {agent_name: output_preview} — grows as agents complete
        shared_context: Dict[str, str] = {}

        async def run_agent(sub_task: Dict) -> None:
            agent_name = sub_task["agent_id"]
            is_lead    = bool(sub_task.get("is_lead", False))
            try:
                await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {"status": "working"})
                await _audit("work_started", sub_task["id"], f"{agent_name} commenced work")

                # Execute with accumulated team context (goal-compounding)
                output_json = await asyncio.to_thread(
                    agent_service.execute_sub_task,
                    sub_task["description"], agent_name,
                    sub_task.get("wallet_id", ""), is_lead,
                    dict(shared_context),   # snapshot — don't pass reference
                    task_goal,
                    task_id,
                )

                # ── Quality evaluation (DeepSeek, ~80 tokens) ─────────────
                try:
                    parsed_out = json.loads(output_json)
                    output_text = parsed_out.get("text", "")[:300]
                    ctx_preview = " | ".join(f"{k}: {str(v)[:100]}" for k, v in shared_context.items())
                    quality = await asyncio.to_thread(
                        evaluate_work, task_id, task_goal, agent_name, output_text, ctx_preview
                    )
                    # Inject quality score into output JSON
                    parsed_out["quality_score"]  = quality["score"]
                    parsed_out["quality_reason"] = quality["reason"]
                    output_json = json.dumps(parsed_out)
                    x402_payments = parsed_out.get("x402_payments", [])
                except Exception as qe:
                    logger.warning("[quality eval] %s: %s", agent_name, qe)
                    quality = {"score": 5.0, "reason": "", "payment_multiplier": 0.5}
                    x402_payments = []

                await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {
                    "status": "complete", "output": output_json,
                })

                # Add to shared context for subsequent agents (goal-compounding)
                parsed_preview = json.loads(output_json)
                if parsed_preview.get("text"):
                    shared_context[agent_name] = parsed_preview["text"][:250]

                preview = parsed_preview.get("text", "")[:80]
                score   = quality.get("score", 5.0)
                await _audit("work_complete", sub_task["id"],
                             f"{agent_name} finished · quality {score:.1f}/10",
                             {"preview": preview, "quality_score": score})

                # Agent completion is routine — suppressed by gate

                for xp in x402_payments:
                    await _audit(
                        "x402_payment", sub_task["id"],
                        f"⚡ x402 · {agent_name} paid {xp.get('amount')} {xp.get('currency')} "
                        f"via Solana · {xp.get('txHash','')[:20]}…",
                        {"wallet_id": xp.get("wallet_id"), "amount": xp.get("amount"),
                         "currency": xp.get("currency"), "endpoint": xp.get("endpoint"),
                         "tx": xp.get("txHash")},
                    )

                # Quality-scaled payment
                sub_task_with_quality = dict(sub_task)
                sub_task_with_quality["_quality_multiplier"] = quality.get("payment_multiplier", 0.5)
                await _process_payment(coordinator_wallet, sub_task_with_quality)

            except Exception as exc:
                logger.error("[agent error] %s: %s", agent_name, exc)
                await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {"status": "failed"})
                await _notify_event("task_failed", f"⚠ {agent_name} FAILED (Network/Infra)\n{str(exc)[:120]}")

        async def run_agent_with_dms(sub_task: Dict) -> None:
            agent_name = sub_task["agent_id"]
            try:
                await asyncio.wait_for(run_agent(sub_task), timeout=120.0)
            except asyncio.TimeoutError:
                # Ghost Bug 2 Fix: inject sentinel so downstream agents (e.g. FORGE)
                # receive a clear "no output from X" signal instead of blank context,
                # preventing hallucination of a completed prior step.
                shared_context[agent_name] = (
                    f"[DMS: {agent_name} timed out after 120s — "
                    f"no output produced. Do not reference or assume {agent_name}'s work.]"
                )
                await _trigger_dead_mans_switch(sub_task, coordinator_wallet)
                await _notify_event("dead_mans_switch",
                    f"⚠️ DEAD MAN'S SWITCH\n"
                    f"Agent: {agent_name}\n"
                    f"No heartbeat: 120s\n"
                    f"API key: REVOKED — funds swept to treasury"
                )

        # ── Sequential goal-compounding execution ────────────────────────────
        for sub_task in ordered_sub_tasks:
            await run_agent_with_dms(sub_task)

        # ── Peer payments (inter-agent micro-economy) ─────────────────────
        fresh_sub_tasks = await asyncio.to_thread(
            pb.list, "sub_tasks", filter_params=_safe_filter("task_id", task_id)
        )
        await _do_peer_payments(fresh_sub_tasks)

        # ── Sync REGIS sovereign brain + fetch payments once ─────────────
        all_task_payments: List[Dict] = []
        try:
            all_payments = await asyncio.to_thread(pb.list, "payments", limit=50, sort="-created")
            all_task_payments = [
                p for p in all_payments
                if any(st["wallet_id"] in (p.get("from_wallet_id", ""), p.get("to_wallet_id", ""))
                       for st in fresh_sub_tasks)
            ]
            await brain_service.async_update_after_task(
                task, fresh_sub_tasks, all_task_payments
            )
        except Exception as exc:
            logger.warning("[brain sync] %s", exc)

        # ── Update coordinator balance from RPC (B7) & Treasury Close ────
        try:
            live_rate = await get_live_sol_usdc_rate()
            if live_rate:
                usdc_total = float(task.get("total_budget", 0))
                sol_equiv  = round(usdc_total / live_rate, 6)
                await brain_service.async_append(
                    "TREASURY_CLOSE",
                    f"SOL/USDC rate {live_rate} (via MoonPay) · "
                    f"treasury ${usdc_total:.2f} USDC ≈ {sol_equiv} SOL",
                )
                
                # Fetch true SOL balance and update PB to reflect remaining USD
                from services.balance_service import balance_service
                bal_info = await balance_service.get_balance(coordinator_wallet["sol_address"], force_refresh=True)
                if bal_info and bal_info.balance_sol is not None:
                    real_usd = float(bal_info.balance_sol) * live_rate
                    await asyncio.to_thread(pb.update, "wallets", coordinator_wallet["id"], {"balance": real_usd})
                    logger.info("Updated coordinator balance from RPC: $%.2f", real_usd)
        except Exception as exc:
            logger.info("[treasury close] %s", exc)

        await asyncio.to_thread(pb.update, "tasks", task_id, {"status": "complete"})
        await _audit("task_complete", task_id, "REGIS closed the treasury. All agents settled.")

        # ── Task completion summary via Telegram ──────────────────────────
        try:
            fresh_sts     = fresh_sub_tasks  # already fetched above
            task_payments = all_task_payments
            paid_count    = sum(1 for p in task_payments if p.get("status") == "signed")
            blocked_count = sum(1 for p in task_payments if p.get("status") == "blocked")
            total_paid    = sum(float(p.get("amount", 0)) for p in task_payments if p.get("status") == "signed")

            # Quality scores summary
            quality_lines = []
            for st in fresh_sts:
                try:
                    out = json.loads(st.get("output", "{}"))
                    qs = out.get("quality_score")
                    if qs is not None:
                        quality_lines.append(f"  {st['agent_id']}: {qs:.1f}/10")
                except Exception:
                    pass

            summary = (
                f"✅ TASK COMPLETE\n"
                f"────────────────\n"
                f"Goal: {task_goal[:60]}\n"
                f"Paid: {paid_count} · Blocked: {blocked_count}\n"
                f"Treasury disbursed: {total_paid:.4f} USDC\n"
            )
            if quality_lines:
                summary += "Quality:\n" + "\n".join(quality_lines) + "\n"
            summary += f"ID: {task_id[:12]}\nUse /status for full detail."
            await _notify_event("task_complete", summary)
        except Exception as exc:
            logger.warning("[task summary tg] %s", exc)

        # ── BISHOP email: task receipt + treasury low ─────────────────────
        try:
            _budget_cap  = float(coordinator_wallet.get("budget_cap", 0))
            _distributed = sum(float(p.get("amount", 0)) for p in task_payments if p.get("status") == "signed")
            _saved       = sum(float(p.get("amount", 0)) for p in task_payments if p.get("status") == "blocked")
            _remaining   = max(0.0, _budget_cap - _distributed)
            _tx_hashes   = [p.get("tx_hash", "") for p in task_payments if p.get("status") == "signed" and p.get("tx_hash")]

            # Convert USDC → SOL using live rate (governance alert only)
            live_rate      = await get_live_sol_usdc_rate()
            _rate          = Decimal(str(live_rate))
            _dist_sol      = float((Decimal(str(_distributed)) / _rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
            _saved_sol     = float((Decimal(str(_saved))       / _rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
            _remaining_sol = float((Decimal(str(_remaining))   / _rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))

            asyncio.create_task(
                asyncio.to_thread(
                    send_task_receipt,
                    task_goal, paid_count, blocked_count,
                    _dist_sol, _saved_sol, _remaining_sol,
                    _tx_hashes,
                )
            )

            # MoonPay Agent + Treasury low alert
            if _remaining_sol < TREASURY_LOW_THRESHOLD_SOL:
                # 1. Email notification
                asyncio.create_task(
                    asyncio.to_thread(
                        send_treasury_low,
                        _remaining_sol,
                        TREASURY_LOW_THRESHOLD_SOL,
                    )
                )
                # 2. Telegram MoonPay auto-trigger
                try:
                    from services.moonpay_service import get_onramp_info
                    sol_addr = coordinator_wallet.get("sol_address", "—")
                    mp_info = get_onramp_info(sol_addr, default_amount=25)
                    mp_url = mp_info.get("url")

                    msg = (
                        f"🚨 TREASURY LOW\n"
                        f"────────────────\n"
                        f"BISHOP: \"My Liege, the treasury has dropped below {_remaining_sol:.3f} SOL!\"\n\n"
                        f"Please restock immediately. I have pre-filled a fiat onramp for you:\n\n"
                        f"{mp_url}\n\n"
                        f"(Or tap /fund for custom amounts)"
                    )
                    await _notify_event("treasury_low", msg)
                except Exception as ex:
                    logger.warning("[moonpay trigger] %s", ex)
        except Exception as exc:
            logger.warning("[bishop email receipt] %s", exc)

        # ── REGIS challenge check ─────────────────────────────────────────
        try:
            all_reps = await asyncio.to_thread(pb.get_all_reputations)
            for agent_name, rep in all_reps.items():
                if qualifies_for_challenge(agent_name, rep):
                    from services.quality_service import get_avg_quality
                    avg_q = get_avg_quality(agent_name)
                    await _notify_event("challenge_result",
                        f"⚔ CHALLENGE ELIGIBLE\n"
                        f"{agent_name} qualifies to challenge REGIS!\n"
                        f"Avg quality: {avg_q:.1f}/10  |  Rep: {rep:.2f}★\n"
                        f"Send /challenge {agent_name} to initiate."
                    )
                    await _audit(
                        "challenge_eligible", agent_name,
                        f"{agent_name} qualifies to challenge REGIS — avg quality {avg_q:.1f}/10",
                        {"rep": rep, "avg_quality": avg_q},
                    )
        except Exception as exc:
            logger.warning("[challenge check] %s", exc)

        # ── SIGNAL SNIPER: VIP Broadcast & Cross-chain Route (Uniblock + XMTP) ──
        try:
            has_signal = False
            for st in fresh_sts:
                try:
                    if st.get("output"):
                        out_text = json.loads(st["output"]).get("text", "")
                        if "BUY SIGNAL" in out_text:
                            has_signal = True
                            break
                except Exception:
                    pass
            
            if has_signal:
                from services.uniblock_service import uniblock_service
                opt_route = await asyncio.to_thread(
                    uniblock_service.get_optimal_route, "solana", "ethereum", "USDC", 100.0
                )
                route_summary = f"Uniblock Route (Solana→Eth): fee {opt_route.get('estimated_fee', 0)} USD"
                
                from services.xmtp_service import xmtp_service
                await asyncio.to_thread(
                    xmtp_service.broadcast,
                    ["0xAdminVIPWallet00000000000000000000000"],
                    "task.sniper.signal",
                    {"alert": "BUY SIGNAL CONFIRMED", "routing": route_summary, "task_id": task_id}
                )
                logger.info("[xmtp sniper] Broadcasted to VIP! %s", route_summary)
        except Exception as exc:
            logger.warning("[sniper final] %s", exc)

    except Exception as exc:
        logger.error("[bg error] %s", exc)
        await asyncio.to_thread(pb.update, "tasks", task_id, {"status": "failed"})
        await _notify_event("task_failed", f"❌ TASK FAILED\n{task_id[:12]}\n{str(exc)[:120]}")


async def _solana_transfer(from_wallet_id: str, to_wallet_id: str, amount_usdc: float) -> str:
    """
    Execute a real Solana devnet transfer so the tx appears on Solscan.

    Converts USDC→SOL (÷79), sends via solana_service using the registered
    Ed25519 keypair for from_wallet_id. Looks up the sol_address of
    to_wallet_id from PocketBase.

    Returns real base58 signature if successful, empty string otherwise.
    Never raises — payment flow must not be blocked by Solana errors.
    """
    try:
        # Look up recipient sol_address
        to_wallet = await asyncio.to_thread(pb.get, "wallets", to_wallet_id)
        to_sol = to_wallet.get("sol_address", "")
        if not to_sol or len(to_sol) < 20:
            return ""

        # Convert USDC to lamports using live rate (1 SOL = 1e9 lamports)
        live_rate  = await get_live_sol_usdc_rate()
        sol_amount = amount_usdc / live_rate
        lamports   = max(5_000, int(sol_amount * 1_000_000_000))  # min 5k lamports

        sig = await asyncio.to_thread(
            solana_service.transfer,
            from_wallet_id,   # registered Ed25519 keypair
            to_sol,           # recipient pubkey (base58)
            lamports,
        )
        if solana_service.is_real_sig(sig):
            logger.info("[solana] ◎%.6f → %s sig=%s…", sol_amount, to_sol[:8], sig[:16])
            return sig
        return ""
    except Exception as exc:
        logger.debug("[solana transfer] %s", exc)
        return ""


async def _trigger_dead_mans_switch(sub_task: Dict, coordinator_wallet: Dict):
    """
    Dead Man's Switch — fires when an agent exceeds the 120 s heartbeat window.
      1. Revoke OWS API key
      2. Sweep remaining budget to coordinator wallet
      3. Mark sub_task "timed_out"
      4. Audit log + reputation penalty
    """
    agent_name = sub_task.get("agent_id", "AGENT")
    swept_at   = datetime.now(timezone.utc).isoformat()
    try:
        # 1 — Revoke OWS key and record revocation in wallet record
        await asyncio.to_thread(ows.revoke_api_key, sub_task["wallet_id"])
        await asyncio.to_thread(pb.update, "wallets", sub_task["wallet_id"], {
            "api_key_id": f"REVOKED-{swept_at}",
        })

        # 2 — Sweep budget back to coordinator (real Solana transfer)
        swept_amount = float(sub_task.get("budget_allocated", 0))
        sweep_tx = await asyncio.to_thread(
            ows.sign_payment,
            sub_task["wallet_id"], coordinator_wallet["id"], swept_amount,
        )
        sweep_sig = await _solana_transfer(
            sub_task["wallet_id"],
            coordinator_wallet["id"],
            swept_amount,
        )
        sweep_hash = sweep_sig or sweep_tx.get("tx_hash", f"0x{uuid.uuid4().hex}")
        await asyncio.to_thread(pb.create, "payments", {
            "from_wallet_id": sub_task["wallet_id"],
            "to_wallet_id":   coordinator_wallet["id"],
            "amount":         swept_amount,
            "chain_id":       "solana:devnet",
            "status":         "signed",
            "policy_reason":  f"SWEEP: Dead man's switch — {agent_name}",
            "tx_hash":        sweep_hash,
            "solscan_url":    f"https://explorer.solana.com/tx/{sweep_hash}?cluster=devnet" if solana_service.is_real_sig(sweep_hash) else "",
        })

        # 3 — Mark sub_task with full sweep metadata in output
        sweep_output = json.dumps({
            "text": f"Dead man's switch triggered. Budget swept to treasury.",
            "ms": 120000,
            "key_revoked": True,
            "key_revoked_at": swept_at,
            "swept_amount": swept_amount,
            "tools": [],
        })
        await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {
            "status": "timed_out",
            "output": sweep_output,
        })

        # 4 — Audit + reputation
        await _audit(
            "dead_mans_switch",
            sub_task["id"],
            f"SECURITY: Dead man's switch triggered for {agent_name}. Funds swept to treasury.",
            {"agent": agent_name, "swept_amount": swept_amount, "revoked_at": swept_at},
        )
        new_rep = await asyncio.to_thread(pb.update_reputation, agent_name, -0.3)
        await _audit("reputation_updated", agent_name,
                     f"{agent_name} rep penalised → {new_rep:.2f}★ (timeout)",
                     {"delta": -0.3, "new_reputation": new_rep})

    except Exception as exc:
        logger.error("[dms] %s: %s", agent_name, exc)


async def _process_payment(coordinator_wallet: Dict, sub_task: Dict):
    """
    Reputation-gated policy engine.
    FORGE attempts +50% quality bonus → REP BLOCK (4★ limit is $2 USDC).
    All others pay exactly budget_allocated → SIGNED.
    Reputation updated after every outcome.
    """
    agent_name = sub_task.get("agent_id", "AGENT")
    try:
        # Ghost Bug 3 Fix: use Decimal for all financial arithmetic to avoid
        # IEEE-754 drift (e.g. 0.10 * 0.3 = 0.030000000000000002 in raw float).
        _D6 = Decimal("0.000001")
        base = Decimal(str(sub_task["budget_allocated"]))
        quality_multiplier = Decimal(str(sub_task.get("_quality_multiplier", 0.5)))
        quality_scaled = float((base * quality_multiplier).quantize(_D6, rounding=ROUND_HALF_UP))
        # FORGE attempts quality bonus; others pay quality-scaled amount
        attempted = float(
            (Decimal(str(quality_scaled)) * Decimal("1.5")).quantize(_D6, rounding=ROUND_HALF_UP)
        ) if agent_name == "FORGE" else quality_scaled

        # Fetch live reputation score before evaluating policy
        reputation = await asyncio.to_thread(pb.get_reputation, agent_name)

        lit_resp = await asyncio.to_thread(
            ows.evaluate_and_sign_lit_action,
            from_wallet=coordinator_wallet,
            to_wallet={"id": sub_task["wallet_id"], "role": "sub-agent"},
            amount=attempted,
            sub_task=sub_task,
            reputation=reputation
        )
        
        from pydantic import BaseModel
        class PolicyResult(BaseModel):
            allow: bool
            reason: str = ""
            is_probation: bool = False
            effective_cap: float = 0.0

        policy_result = PolicyResult(
            allow=lit_resp.get("allow", False),
            reason=lit_resp.get("reason") or "",
            is_probation=lit_resp.get("is_probation", False),
            effective_cap=lit_resp.get("effective_cap", 0.0)
        )
        lit_tx = lit_resp.get("tx_hash", "")

        # ── FIX 1: Probation retry — cap to effective_cap and re-evaluate ──
        # Instead of hard-blocking, pay the capped amount (probation payment).
        # This breaks the death spiral: agent still earns, rep recovers over time.
        if not policy_result.allow and policy_result.is_probation and policy_result.effective_cap:
            cap = policy_result.effective_cap
            await _audit(
                "work_started",  # reuse work_started colour (amber) for probation notice
                sub_task["id"],
                f"{agent_name} probation payment: {cap:.4f} USDC "
                f"({get_rep_multiplier(reputation)*100:.0f}% of budget at {reputation:.1f}★) — rehabilitation mode",
                {"agent": agent_name, "cap": cap, "full_amount": attempted, "reputation": reputation},
            )
            attempted = cap
            new_lit_resp = await asyncio.to_thread(
                ows.evaluate_and_sign_lit_action,
                from_wallet=coordinator_wallet,
                to_wallet={"id": sub_task["wallet_id"], "role": "sub-agent"},
                amount=attempted,
                sub_task=sub_task,
                reputation=reputation
            )
            policy_result = PolicyResult(
                allow=new_lit_resp.get("allow", False),
                reason=new_lit_resp.get("reason") or "",
                is_probation=new_lit_resp.get("is_probation", False),
                effective_cap=new_lit_resp.get("effective_cap", 0.0)
            )
            lit_tx = new_lit_resp.get("tx_hash", "")

        payload: Dict[str, Any] = {
            "from_wallet_id": coordinator_wallet["id"],
            "to_wallet_id": sub_task["wallet_id"],
            "amount": attempted,
            "chain_id": "solana:devnet",
            "status": "signed" if policy_result.allow else "blocked",
            "policy_reason": policy_result.reason or "",
        }

        if policy_result.allow:
            # We already invoked Lit Action so we use the PKP signature returned by Lit
            tx = {"tx_hash": lit_tx}
            # Attempt real on-chain Solana transfer — makes tx visible on Solscan
            real_sig = await _solana_transfer(
                coordinator_wallet["id"],
                sub_task["wallet_id"],
                attempted,
            )
            # Prefer real Solana signature over OWS mock hash
            tx_hash = real_sig or tx.get("tx_hash", "")
            payload["tx_hash"] = tx_hash
            payload["solscan_url"] = (
                f"https://explorer.solana.com/tx/{tx_hash}?cluster=devnet"
                if solana_service.is_real_sig(tx_hash) else ""
            )
            if solana_service.is_real_sig(tx_hash):
                # Queue payment for on-chain verification (B5)
                # target wallet must be resolved
                to_wallet_sol = ""
                try:
                    to_wallet_obj = await asyncio.to_thread(pb.get, "wallets", sub_task["wallet_id"])
                    to_wallet_sol = to_wallet_obj.get("sol_address", "")
                except Exception:
                    pass
                
                live_rate_verify = await get_live_sol_usdc_rate()
                expected_sol = attempted / live_rate_verify

                p_data = PaymentData(
                    tx_hash=tx_hash,
                    task_id=sub_task["task_id"],
                    agent_id=agent_name,
                    expected_amount_sol=Decimal(str(expected_sol)),
                    recipient=to_wallet_sol,
                    timestamp=time.time()
                )
                await payment_verification_service.queue_verification(p_data)

            await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {"status": "paid"})
            # Probation recovery bonus: slightly higher rep reward when on probation
            rep_delta = +0.3 if is_probation(reputation) else +0.1
            new_rep = await asyncio.to_thread(pb.update_reputation, agent_name, rep_delta)
            # Sovereignty: track earnings + distributed, then check for overthrow
            await asyncio.to_thread(sovereignty_service.update_earnings, agent_name, attempted)
            await asyncio.to_thread(sovereignty_service.update_distributed, "REGIS", attempted)
            asyncio.create_task(_check_sovereignty_overthrow())
        else:
            await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {"status": "blocked"})
            new_rep = await asyncio.to_thread(pb.update_reputation, agent_name, -0.2)

        payment_rec = await asyncio.to_thread(pb.create, "payments", payload)

        event = "payment_signed" if policy_result.allow else "payment_blocked"
        label = "SIGNED ✓" if policy_result.allow else "BLOCKED ✗"
        msg = f"Payment {payment_rec['id'][:8]} {label} {attempted:.4f} USDC"
        if policy_result.reason:
            msg += f" — {policy_result.reason}"

        await _audit(event, payment_rec["id"], msg, {
            "from": coordinator_wallet["id"],
            "to": sub_task["wallet_id"],
            "amount": attempted,
            "reputation_before": reputation,
            "reputation_after": new_rep,
        })

        delta = +0.3 if (policy_result.allow and is_probation(reputation)) else (+0.1 if policy_result.allow else -0.2)
        direction = "recovered" if (policy_result.allow and is_probation(reputation)) else ("rewarded" if policy_result.allow else "penalised")
        await _audit("reputation_updated", agent_name,
                     f"{agent_name} rep {direction} → {new_rep:.2f}★ (was {reputation:.2f}★)",
                     {"delta": delta, "new_reputation": new_rep})

        if not policy_result.allow:
            await _notify_event("payment_blocked",
                f"🚨 POLICY BLOCK\n"
                f"Agent: {agent_name}\n"
                f"Attempted: {attempted:.4f} USDC\n"
                f"Rep: {reputation:.2f}★ → {new_rep:.2f}★ (-0.2)\n"
                f"Reason: {policy_result.reason}"
            )
            live_rate  = await get_live_sol_usdc_rate()
            amount_sol = attempted / live_rate
            if amount_sol > CRITICAL_BLOCK_THRESHOLD_SOL:
                task_desc = sub_task.get("description", "")
                asyncio.create_task(
                    asyncio.to_thread(
                        send_critical_block,
                        agent_name, amount_sol,
                        policy_result.reason or "Policy threshold exceeded",
                        task_desc,
                    )
                )

    except Exception as exc:
        logger.error("[payment error] %s", exc)


async def _do_peer_payments(sub_tasks: List[Dict]):
    """
    Inter-agent micro-economy — fires after all agents settle.
      ATLAS  → CIPHER  0.005 USDC  (research handoff fee)
      CIPHER → FORGE   0.003 USDC  (analysis delivery fee)
    Peer payments bypass the coordinator policy engine.
    Both routes only fire when the sending agent completed (paid / complete).
    """
    wallet_map = {st["agent_id"]: st["wallet_id"] for st in sub_tasks}
    status_map = {st["agent_id"]: st["status"] for st in sub_tasks}

    routes = [
        ("ATLAS",  "CIPHER", 0.005, "research handoff"),
        ("CIPHER", "FORGE",  0.003, "analysis delivery"),
        ("FORGE",  "BISHOP", 0.002, "compliance review"),
    ]

    for sender, receiver, amount, label in routes:
        sender_wallet  = wallet_map.get(sender)
        receiver_wallet = wallet_map.get(receiver)
        if not sender_wallet or not receiver_wallet:
            continue
        # Allow peer payments if sender completed work (paid or blocked for quality bonus)
        # "blocked" = coordinator denied fee, but work was still produced
        if status_map.get(sender) not in ("paid", "complete", "blocked"):
            continue
        try:
            tx = await asyncio.to_thread(
                ows.sign_payment, sender_wallet, receiver_wallet, amount
            )
            peer_sig = await _solana_transfer(sender_wallet, receiver_wallet, amount)
            peer_hash = peer_sig or tx.get("tx_hash", "")
            payment_rec = await asyncio.to_thread(pb.create, "payments", {
                "from_wallet_id": sender_wallet,
                "to_wallet_id":   receiver_wallet,
                "amount":         amount,
                "chain_id":       "solana:devnet",
                "status":         "signed",
                "policy_reason":  f"PEER: {label}",
                "tx_hash":        peer_hash,
                "solscan_url":    f"https://explorer.solana.com/tx/{peer_hash}?cluster=devnet" if solana_service.is_real_sig(peer_hash) else "",
            })
            # XMTP: send wallet-to-wallet verified message on handoff
            xmtp_verified = False
            try:
                from services.xmtp_service import xmtp_service
                output_map = {st["agent_id"]: st.get("output", "") for st in sub_tasks}
                sender_output = output_map.get(sender, "")[:300]
                xmtp_result = await asyncio.to_thread(
                    xmtp_service.send_message,
                    _agent_symbolic_addr(receiver),
                    f"task.peer.{label.replace(' ', '_')}",
                    {
                        "from_agent": sender, "to_agent": receiver,
                        "content":    f"Intel handoff: {sender_output}",
                        "payment_usdc": amount, "label": label,
                    },
                )
                xmtp_verified = bool(xmtp_result and xmtp_result.get("success"))
            except Exception:
                pass

            xmtp_tag = " [✓ XMTP]" if xmtp_verified else " [internal]"
            await _audit(
                "peer_payment",
                payment_rec["id"],
                f"⇄ {sender} → {receiver}  {amount:.3f} USDC  [{label}]{xmtp_tag}",
                {
                    "from_agent":    sender,
                    "to_agent":      receiver,
                    "amount":        amount,
                    "label":         label,
                    "xmtp_verified": xmtp_verified,
                },
            )
        except Exception as exc:
            logger.warning("[peer payment] %s→%s: %s", sender, receiver, exc)


def _agent_symbolic_addr(agent_id: str) -> str:
    """Deterministic symbolic ETH address for XMTP routing."""
    import hashlib
    h = hashlib.sha256(f"swarmpay_agent_{agent_id}".encode()).hexdigest()
    return f"0x{h[:40]}"


@router.get("/{task_id}/status")
async def get_task_status(task_id: str):
    try:
        return await asyncio.to_thread(pb.get_full_task, task_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Task not found: {str(e)}")


@router.get("/{task_id}/stream")
async def stream_task_status(task_id: str):
    """SSE — polls PocketBase every 2 s until terminal state."""
    async def event_stream():
        last = None
        while True:
            try:
                data = await asyncio.to_thread(pb.get_full_task, task_id)
                current = json.dumps(data, sort_keys=True)
                if current != last:
                    yield f"data: {current}\n\n"
                    last = current
                if data.get("task", {}).get("status") in ("complete", "failed"):
                    break
            except Exception as exc:
                yield f"data: {{\"error\": \"{str(exc)}\"}}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
