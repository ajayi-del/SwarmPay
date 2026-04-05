"""
Task Router - Handles all task-related endpoints
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.pocketbase import PocketBaseService
from services.ows_service import OWSService
from services.agent_service import AgentService, AGENT_PERSONAS, EXECUTION_ORDER
from services.policy_service import PolicyService
from services.brain_service import brain_service
from services.solana_service import solana_service
from services.agent_lock_service import filter_available, is_locked
from services.quality_service import evaluate_work, qualifies_for_challenge, run_regis_challenge

router = APIRouter(prefix="/task", tags=["tasks"])

class TaskSubmitRequest(BaseModel):
    description: str
    budget: float

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
async def clarify_task(request: TaskClarifyRequest):
    """
    REGIS asks 2-3 context questions before task starts.
    Returns empty list if task description is already clear enough.
    """
    try:
        from services.model_service import call_claude
        prompt = (
            f'Task description: "{request.description}"\n\n'
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
        raw = await asyncio.to_thread(call_claude, prompt, 300)
        s, e = raw.find("{"), raw.rfind("}") + 1
        if s != -1 and e > s:
            parsed = json.loads(raw[s:e])
            return TaskClarifyResponse(
                questions=parsed.get("questions", [])[:3],
                needs_clarification=bool(parsed.get("needs_clarification", False)),
                suggested_budget=float(parsed.get("suggested_budget", 5.0)),
            )
    except Exception as exc:
        print(f"[clarify] {exc}")
    return TaskClarifyResponse(questions=[], needs_clarification=False, suggested_budget=5.0)


@router.post("/submit", response_model=TaskSubmitResponse)
async def submit_task(request: TaskSubmitRequest):
    """Submit a new task and create REGIS coordinator wallet."""
    try:
        ows_wallet = await asyncio.to_thread(ows.create_wallet, f"REGIS-{uuid.uuid4().hex[:6]}")
        sol_wallet = await asyncio.to_thread(solana_service.generate_and_fund)

        wallet_record = await asyncio.to_thread(pb.create, "wallets", {
            "name": ows_wallet["name"],
            "role": "coordinator",
            "eth_address": ows_wallet["eth_address"],
            "sol_address": sol_wallet["pubkey"],
            "budget_cap": request.budget,
            "balance": request.budget,
            "api_key_id": f"regis_api_{uuid.uuid4().hex[:8]}",
        })
        solana_service.register(wallet_record["id"], sol_wallet["privkey_hex"])

        task_record = await asyncio.to_thread(pb.create, "tasks", {
            "description": request.description,
            "total_budget": request.budget,
            "status": "pending",
            "coordinator_wallet_id": wallet_record["id"],
        })

        await _audit(
            "task_submitted",
            task_record["id"],
            f"REGIS accepted task: {request.description[:60]}",
            {"budget": request.budget, "coordinator_wallet": wallet_record["id"]},
        )

        return TaskSubmitResponse(task_id=task_record["id"], coordinator_wallet=wallet_record)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")


@router.post("/decompose", response_model=TaskDecomposeResponse)
async def decompose_task(request: TaskDecomposeRequest):
    """Deterministically decompose task — Claude picks the right agents, not all 5."""
    try:
        task = await asyncio.to_thread(pb.get, "tasks", request.task_id)

        # Step 1: Claude analyzes task → picks which agents to spawn + who leads
        # Filter out locked agents before analysis
        from services.agent_service import ALL_AGENT_NAMES
        available = filter_available(ALL_AGENT_NAMES)
        analysis = await asyncio.to_thread(
            agent_service.analyze_task_for_agents, task["description"], available
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
            slug = request.task_id[-6:]

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
                "task_id": request.task_id,
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

        await asyncio.to_thread(pb.update, "tasks", request.task_id, {"status": "decomposed"})

        return TaskDecomposeResponse(sub_tasks=sub_tasks, agent_wallets=agent_wallets)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decompose task: {str(e)}")


@router.post("/execute", response_model=TaskExecuteResponse)
async def execute_task(request: TaskExecuteRequest, background_tasks: BackgroundTasks):
    """Kick off parallel execution in the background."""
    try:
        background_tasks.add_task(execute_task_background, request.task_id)
        return TaskExecuteResponse(status="running")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start execution: {str(e)}")


async def _notify_telegram(message: str) -> None:
    """Non-blocking Telegram notification to REGIS chat."""
    try:
        from services.telegram_service import send, ALLOWED_CHAT_ID
        await send(ALLOWED_CHAT_ID, message)
    except Exception as e:
        print(f"[tg notify] {e}")


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
        sub_tasks = await asyncio.to_thread(pb.list, "sub_tasks", filter_params=f"task_id='{task_id}'")
        coordinator_wallet = await asyncio.to_thread(pb.get, "wallets", task["coordinator_wallet_id"])
        task_goal = task.get("description", "")

        await asyncio.to_thread(pb.update, "tasks", task_id, {"status": "in_progress"})

        # Notify task started
        agent_names = [st["agent_id"] for st in sub_tasks]
        lead_agent  = next((st["agent_id"] for st in sub_tasks if st.get("is_lead")), agent_names[0] if agent_names else "?")
        await _notify_telegram(
            f"🚀 SWARM ACTIVE\n"
            f"──────────────\n"
            f"Task: {task_goal[:80]}\n"
            f"Agents: {' · '.join(agent_names)}\n"
            f"Lead: {lead_agent} (Claude)\n"
            f"Support: DeepSeek\n"
            f"ID: {task_id[:12]}"
        )

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
                )

                # ── Quality evaluation (DeepSeek, ~80 tokens) ─────────────
                try:
                    parsed_out = json.loads(output_json)
                    output_text = parsed_out.get("text", "")[:300]
                    ctx_preview = " | ".join(f"{k}: {v[:100]}" for k, v in shared_context.items())
                    quality = await asyncio.to_thread(
                        evaluate_work, task_goal, agent_name, output_text, ctx_preview
                    )
                    # Inject quality score into output JSON
                    parsed_out["quality_score"]  = quality["score"]
                    parsed_out["quality_reason"] = quality["reason"]
                    output_json = json.dumps(parsed_out)
                    x402_payments = parsed_out.get("x402_payments", [])
                except Exception as qe:
                    print(f"[quality eval] {agent_name}: {qe}")
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

                # Telegram: agent completed
                lang    = parsed_preview.get("lang", "")
                en_text = parsed_preview.get("english_text") or preview
                model   = parsed_preview.get("model", "?")
                await _notify_telegram(
                    f"{'★ ' if is_lead else ''}✓ {agent_name} COMPLETE\n"
                    f"Quality: {score:.1f}/10  |  Model: {model}\n"
                    f"{en_text[:120]}"
                )

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
                print(f"[agent error] {agent_name}: {exc}")
                await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {"status": "failed"})
                new_rep = await asyncio.to_thread(pb.update_reputation, agent_name, -0.2)
                await _audit("reputation_updated", agent_name,
                             f"{agent_name} rep penalised → {new_rep:.2f}★ (work failed)",
                             {"delta": -0.2, "new_reputation": new_rep})
                await _notify_telegram(f"⚠ {agent_name} FAILED\n{str(exc)[:120]}")

        async def run_agent_with_dms(sub_task: Dict) -> None:
            try:
                await asyncio.wait_for(run_agent(sub_task), timeout=120.0)
            except asyncio.TimeoutError:
                await _trigger_dead_mans_switch(sub_task, coordinator_wallet)
                await _notify_telegram(f"⏱ {sub_task['agent_id']} TIMED OUT — funds swept to treasury")

        # ── Sequential goal-compounding execution ────────────────────────────
        for sub_task in ordered_sub_tasks:
            await run_agent_with_dms(sub_task)

        # ── Peer payments (inter-agent micro-economy) ─────────────────────
        fresh_sub_tasks = await asyncio.to_thread(
            pb.list, "sub_tasks", filter_params=f"task_id='{task_id}'"
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
            await asyncio.to_thread(
                brain_service.update_after_task, task, fresh_sub_tasks, all_task_payments
            )
        except Exception as exc:
            print(f"[brain sync] {exc}")

        # ── Meteora: log SOL/USDC rate at treasury close ─────────────────
        try:
            from services.meteora_service import get_sol_usdc_rate
            rate_data = await asyncio.to_thread(get_sol_usdc_rate)
            if rate_data:
                usdc_total = float(task.get("total_budget", 0))
                sol_equiv  = round(usdc_total / rate_data["rate"], 6)
                brain_service.append(
                    "TREASURY_CLOSE",
                    f"SOL/USDC rate {rate_data['rate']} (via {rate_data['source']}) · "
                    f"treasury ${usdc_total:.2f} USDC ≈ {sol_equiv} SOL",
                )
        except Exception as exc:
            print(f"[meteora log] {exc}")

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
            summary += f"ID: {task_id[:12]}\nUse /status for full report."
            await _notify_telegram(summary)
        except Exception as exc:
            print(f"[task summary tg] {exc}")

        # ── REGIS challenge check ─────────────────────────────────────────
        try:
            all_reps = await asyncio.to_thread(pb.get_all_reputations)
            for agent_name, rep in all_reps.items():
                if qualifies_for_challenge(agent_name, rep):
                    from services.quality_service import get_avg_quality
                    avg_q = get_avg_quality(agent_name)
                    await _notify_telegram(
                        f"⚔ REGIS CHALLENGE ELIGIBLE\n"
                        f"──────────────────────────\n"
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
            print(f"[challenge check] {exc}")

    except Exception as exc:
        print(f"[bg error] {exc}")
        await asyncio.to_thread(pb.update, "tasks", task_id, {"status": "failed"})
        await _notify_telegram(f"❌ TASK FAILED\n{task_id[:12]}\n{str(exc)[:120]}")


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

        # 2 — Sweep budget back to coordinator
        swept_amount = float(sub_task.get("budget_allocated", 0))
        sweep_tx = await asyncio.to_thread(
            ows.sign_payment,
            sub_task["wallet_id"], coordinator_wallet["id"], swept_amount,
        )
        await asyncio.to_thread(pb.create, "payments", {
            "from_wallet_id": sub_task["wallet_id"],
            "to_wallet_id":   coordinator_wallet["id"],
            "amount":         swept_amount,
            "chain_id":       "eip155:1",
            "status":         "signed",
            "policy_reason":  f"SWEEP: Dead man's switch — {agent_name}",
            "tx_hash":        sweep_tx.get("tx_hash", f"0x{uuid.uuid4().hex}"),
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
        print(f"[dead_mans_switch] {agent_name}: {exc}")


async def _process_payment(coordinator_wallet: Dict, sub_task: Dict):
    """
    Reputation-gated policy engine.
    FORGE attempts +50% quality bonus → REP BLOCK (4★ limit is $2 USDC).
    All others pay exactly budget_allocated → SIGNED.
    Reputation updated after every outcome.
    """
    agent_name = sub_task.get("agent_id", "AGENT")
    try:
        base = sub_task["budget_allocated"]
        # Quality-scaled: payment = base * quality_multiplier (0.0–1.0)
        # FORGE still attempts +50% quality bonus on top of the quality-scaled amount
        quality_multiplier = float(sub_task.get("_quality_multiplier", 0.5))
        quality_scaled = round(base * quality_multiplier, 6)
        attempted = round(quality_scaled * 1.5, 6) if agent_name == "FORGE" else quality_scaled

        # Fetch live reputation score before evaluating policy
        reputation = await asyncio.to_thread(pb.get_reputation, agent_name)

        policy_result = policy_service.evaluate_payment(
            from_wallet=coordinator_wallet,
            to_wallet={"id": sub_task["wallet_id"], "role": "sub-agent"},
            amount=attempted,
            sub_task=sub_task,
            reputation=reputation,
        )

        payload: Dict[str, Any] = {
            "from_wallet_id": coordinator_wallet["id"],
            "to_wallet_id": sub_task["wallet_id"],
            "amount": attempted,
            "chain_id": "eip155:1",
            "status": "signed" if policy_result.allow else "blocked",
            "policy_reason": policy_result.reason or "",
        }

        if policy_result.allow:
            tx = await asyncio.to_thread(
                ows.sign_payment,
                coordinator_wallet["id"], sub_task["wallet_id"], attempted
            )
            payload["tx_hash"] = tx.get("tx_hash", "")
            await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {"status": "paid"})
            # Reputation reward for successful payment
            new_rep = await asyncio.to_thread(pb.update_reputation, agent_name, +0.1)
        else:
            await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {"status": "blocked"})
            # Reputation penalty for blocked payment
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

        # Log reputation change
        delta = +0.1 if policy_result.allow else -0.2
        direction = "rewarded" if policy_result.allow else "penalised"
        await _audit("reputation_updated", agent_name,
                     f"{agent_name} rep {direction} → {new_rep:.2f}★ (was {reputation:.2f}★)",
                     {"delta": delta, "new_reputation": new_rep})

        # Telegram: payment outcome + rep update
        if policy_result.allow:
            tx_hash = payload.get("tx_hash", "")
            tx_short = f" · tx {tx_hash[:16]}…" if tx_hash else ""
            await _notify_telegram(
                f"💸 PAID: {agent_name}\n"
                f"────────────────\n"
                f"Amount: {attempted:.4f} USDC{tx_short}\n"
                f"Rep: {reputation:.2f}★ → {new_rep:.2f}★ (+0.1)\n"
                f"Policy: {policy_result.reason or 'approved'}"
            )
        else:
            await _notify_telegram(
                f"🚫 PAYMENT BLOCKED: {agent_name}\n"
                f"──────────────────────────\n"
                f"Attempted: {attempted:.4f} USDC\n"
                f"Rep: {reputation:.2f}★ → {new_rep:.2f}★ (-0.2)\n"
                f"Reason: {policy_result.reason}"
            )

    except Exception as exc:
        print(f"[payment error] {exc}")


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
            payment_rec = await asyncio.to_thread(pb.create, "payments", {
                "from_wallet_id": sender_wallet,
                "to_wallet_id":   receiver_wallet,
                "amount":         amount,
                "chain_id":       "eip155:1",
                "status":         "signed",
                "policy_reason":  f"PEER: {label}",
                "tx_hash":        tx.get("tx_hash", ""),
            })
            await _audit(
                "peer_payment",
                payment_rec["id"],
                f"⇄ {sender} → {receiver}  {amount:.3f} USDC  [{label}]",
                {"from_agent": sender, "to_agent": receiver,
                 "amount": amount, "label": label},
            )
            await _notify_telegram(
                f"⇄ PEER PAYMENT\n"
                f"{sender} → {receiver}\n"
                f"{amount:.3f} USDC · {label}"
            )
        except Exception as exc:
            print(f"[peer payment] {sender}→{receiver}: {exc}")


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
