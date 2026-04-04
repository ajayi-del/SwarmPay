"""
Task Router - Handles all task-related endpoints
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.pocketbase import PocketBaseService
from services.ows_service import OWSService
from services.agent_service import AgentService, AGENT_PERSONAS
from services.policy_service import PolicyService

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


@router.post("/submit", response_model=TaskSubmitResponse)
async def submit_task(request: TaskSubmitRequest):
    """Submit a new task and create REGIS coordinator wallet."""
    try:
        ows_wallet = await asyncio.to_thread(ows.create_wallet, f"REGIS-{uuid.uuid4().hex[:6]}")

        wallet_record = await asyncio.to_thread(pb.create, "wallets", {
            "name": ows_wallet["name"],
            "role": "coordinator",
            "eth_address": ows_wallet["eth_address"],
            "sol_address": ows_wallet["sol_address"],
            "budget_cap": request.budget,
            "balance": request.budget,
            "api_key_id": f"regis_api_{uuid.uuid4().hex[:8]}",
        })

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
    """Decompose task into 5 persona sub-tasks — all wallets created in parallel."""
    try:
        task = await asyncio.to_thread(pb.get, "tasks", request.task_id)
        sub_tasks_raw = await asyncio.to_thread(
            agent_service.decompose_task, task["description"], task["total_budget"]
        )

        async def _create_bundle(i: int, st_data: Dict) -> tuple:
            """Parallel: create OWS wallet + PocketBase wallet + sub_task for one agent."""
            persona = st_data["persona"]
            slug = request.task_id[-6:]

            ows_w = await asyncio.to_thread(ows.create_wallet, f"{persona['name'].lower()}-{slug}")
            api_key = await asyncio.to_thread(ows.create_api_key, ows_w["id"], st_data["budget_allocated"])

            wallet_rec = await asyncio.to_thread(pb.create, "wallets", {
                "name": ows_w["name"],
                "role": "sub-agent",
                "eth_address": ows_w["eth_address"],
                "sol_address": ows_w["sol_address"],
                "budget_cap": st_data["budget_allocated"],
                "balance": 0,
                "api_key_id": api_key,
            })

            st_rec = await asyncio.to_thread(pb.create, "sub_tasks", {
                "task_id": request.task_id,
                "agent_id": persona["name"],          # "ATLAS", "CIPHER", …
                "wallet_id": wallet_rec["id"],
                "description": st_data["description"],
                "budget_allocated": st_data["budget_allocated"],
                "status": "spawned",
            })

            await _audit(
                "agent_spawned",
                st_rec["id"],
                f"{persona['name']} spawned · {persona['flag']} {persona['city']} | wallet {wallet_rec['id'][:8]}",
                {"agent": persona["name"], "wallet": wallet_rec["id"]},
            )
            return wallet_rec, st_rec

        # ── All 5 agent bundles in parallel ──────────────────────────────
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


async def execute_task_background(task_id: str):
    """Parallel agent execution + policy-gated payments."""
    try:
        task = await asyncio.to_thread(pb.get, "tasks", task_id)
        sub_tasks = await asyncio.to_thread(pb.list, "sub_tasks", filter_params=f"task_id='{task_id}'")
        coordinator_wallet = await asyncio.to_thread(pb.get, "wallets", task["coordinator_wallet_id"])

        await asyncio.to_thread(pb.update, "tasks", task_id, {"status": "in_progress"})

        async def run_agent(sub_task: Dict):
            agent_name = sub_task["agent_id"]   # Already the persona name
            try:
                await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {"status": "working"})
                await _audit("work_started", sub_task["id"], f"{agent_name} commenced work")

                # Haiku call — blocking, run in thread
                output_json = await asyncio.to_thread(
                    agent_service.execute_sub_task, sub_task["description"], agent_name
                )

                await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {
                    "status": "complete",
                    "output": output_json,
                })

                # Preview text for audit
                try:
                    preview = json.loads(output_json).get("text", "")[:100]
                except Exception:
                    preview = output_json[:100]

                await _audit("work_complete", sub_task["id"],
                             f"{agent_name} finished work",
                             {"preview": preview})

                await _process_payment(coordinator_wallet, sub_task)

            except Exception as exc:
                print(f"[agent error] {agent_name}: {exc}")
                await asyncio.to_thread(pb.update, "sub_tasks", sub_task["id"], {"status": "failed"})
                # Reputation penalty for failed work
                new_rep = await asyncio.to_thread(pb.update_reputation, agent_name, -0.2)
                await _audit("reputation_updated", agent_name,
                             f"{agent_name} rep penalised → {new_rep:.2f}★ (work failed)",
                             {"delta": -0.2, "new_reputation": new_rep})

        await asyncio.gather(*[run_agent(st) for st in sub_tasks])

        await asyncio.to_thread(pb.update, "tasks", task_id, {"status": "complete"})
        await _audit("task_complete", task_id, "REGIS closed the treasury. All agents settled.")

    except Exception as exc:
        print(f"[bg error] {exc}")
        await asyncio.to_thread(pb.update, "tasks", task_id, {"status": "failed"})


async def _process_payment(coordinator_wallet: Dict, sub_task: Dict):
    """
    Reputation-gated policy engine.
    FORGE attempts +50% quality bonus → REP BLOCK (4★ limit is 0.10 ETH).
    All others pay exactly budget_allocated → SIGNED.
    Reputation updated after every outcome.
    """
    agent_name = sub_task.get("agent_id", "AGENT")
    try:
        base = sub_task["budget_allocated"]
        attempted = round(base * 1.5, 6) if agent_name == "FORGE" else base

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
        msg = f"Payment {payment_rec['id'][:8]} {label} {attempted:.4f} ETH"
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

    except Exception as exc:
        print(f"[payment error] {exc}")


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
