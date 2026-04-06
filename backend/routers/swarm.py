"""
Swarm Router — Sovereign agent world API.

Endpoints:
  POST /api/swarm/launch           — REGIS receives task, verifies agents, broadcasts via XMTP
  POST /api/swarm/allium/webhook   — Allium pushes on-chain events to REGIS
  GET  /api/swarm/status           — World state: agents, trust scores, service health
  GET  /api/swarm/agents/{id}      — Single agent identity + capabilities
  POST /api/swarm/verify/{id}      — Verify a specific agent's identity on demand

Rate limits:
  /launch   — 10/hour (LLM + XMTP cost)
  /webhook  — 100/minute (external push, must be fast)
  /status   — 60/minute (polling-friendly)
"""

import asyncio
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger("swarmpay.swarm")
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/swarm", tags=["swarm"])

# Lazy singleton — avoids import-time side effects
_regis: Any = None


def _get_regis():
    global _regis
    if _regis is None:
        from agents.coordinator_agent import CoordinatorAgent
        _regis = CoordinatorAgent()
    return _regis


# ── Request / Response models ──────────────────────────────────────────────────

class SwarmLaunchRequest(BaseModel):
    description: str
    budget_sol:  float = 0.3
    context:     dict  = {}

    @field_validator("description")
    @classmethod
    def desc_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("description cannot be empty")
        if len(v) > 2000:
            raise ValueError("description too long (max 2000 chars)")
        return v

    @field_validator("budget_sol")
    @classmethod
    def budget_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("budget_sol must be positive")
        return round(v, 6)


class SwarmLaunchResponse(BaseModel):
    success:             bool
    task_id:             str
    agents_verified:     list[str]
    agents_dispatched:   list[str]
    xmtp_broadcasts:     list[dict]
    onchain_context:     dict
    duration_ms:         int
    message:             str = ""


class AlliumWebhookPayload(BaseModel):
    type:     str
    chain:    str = "solana"
    severity: str = "info"
    data:     dict = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/launch", response_model=SwarmLaunchResponse)
@limiter.limit("10/hour")
async def launch_swarm(
    request: Request,
    body: SwarmLaunchRequest,
    background_tasks: BackgroundTasks,
):
    """
    REGIS receives a task and orchestrates the agent world:

    1. Verifies all agent identities via Myriad
    2. Observes on-chain context via Allium
    3. Decomposes task into per-agent subtasks
    4. Simulates payments via Uniblock (pre-flight)
    5. Broadcasts subtasks to agents over XMTP
    6. Issues attestations for audit trail

    Also triggers the existing SwarmPay execution pipeline in background.
    """
    try:
        regis = _get_regis()
        budget_usdc = round(body.budget_sol * 79.0, 6)

        payload = {
            "description": body.description,
            "budget_sol":  body.budget_sol,
            "budget_usdc": budget_usdc,
            "context":     body.context,
        }

        # REGIS orchestration (blocking but fast — no LLM inside)
        result = await asyncio.to_thread(regis.handle_task, payload)

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Swarm launch failed"))

        # Fire the existing task pipeline in background (optional integration)
        task_id = result["task_id"]
        background_tasks.add_task(
            _audit_swarm_launch,
            task_id, body.description, result["agents_dispatched"]
        )

        return SwarmLaunchResponse(
            success=True,
            task_id=task_id,
            agents_verified=result.get("agents_verified", []),
            agents_dispatched=result.get("agents_dispatched", []),
            xmtp_broadcasts=result.get("xmtp_broadcasts", []),
            onchain_context=result.get("onchain_context", {}),
            duration_ms=result.get("duration_ms", 0),
            message=f"Swarm of {len(result.get('agents_dispatched', []))} agents dispatched via XMTP",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[swarm/launch] %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/allium/webhook")
@limiter.limit("100/minute")
async def allium_webhook(request: Request, body: AlliumWebhookPayload):
    """
    Allium pushes real-time blockchain events to REGIS.
    REGIS evaluates and decides if swarm action is needed.

    Example events:
      • anomaly_detected (large suspicious transfer)
      • defi_tvl_drop    (protocol TVL drops >20%)
      • large_transfer   (whale movement)
    """
    try:
        regis = _get_regis()
        result = await asyncio.to_thread(
            regis.handle_allium_webhook,
            body.model_dump(),
        )

        # Audit critical events
        if body.severity in ("high", "critical"):
            await _audit_swarm_launch(
                f"allium_{int(time.time())}",
                f"Allium webhook: {body.type} on {body.chain} (severity={body.severity})",
                ["REGIS"],
            )

        return {"received": True, "action": result.get("action", "logged"), **result}

    except Exception as exc:
        logger.error("[swarm/allium-webhook] %s", exc)
        # Return 200 to Allium even on error — prevent retry storms
        return {"received": True, "error": str(exc)}


@router.get("/status")
@limiter.limit("60/minute")
async def swarm_status(request: Request):
    """
    World state: all agents with trust scores, service health, capability map.
    """
    try:
        regis = _get_regis()
        status = await asyncio.to_thread(regis.get_world_status)
        return status
    except Exception as exc:
        logger.error("[swarm/status] %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agents/{agent_id}")
@limiter.limit("60/minute")
async def get_agent(request: Request, agent_id: str):
    """
    Resolve a specific agent's Myriad identity + trust score + capabilities.
    """
    agent_id = agent_id.upper()
    valid = {"REGIS", "ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"}
    if agent_id not in valid:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_id}")

    try:
        regis = _get_regis()
        identity   = await asyncio.to_thread(regis.identity.get_agent_identity, agent_id)
        trust      = await asyncio.to_thread(regis.identity.get_trust_score, agent_id)
        reachable  = await asyncio.to_thread(
            regis.messaging.is_reachable,
            _agent_address(agent_id),
        )
        return {
            "agent_id":    agent_id,
            "identity":    identity,
            "trust_score": trust,
            "xmtp_topic":  _AGENT_XMTP_TOPICS.get(agent_id, "task.general"),
            "xmtp_reachable": reachable,
            "capabilities": {
                "talk":     "xmtp",
                "see":      "allium",
                "transact": "uniblock",
                "verify":   "myriad",
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/verify/{agent_id}")
@limiter.limit("30/minute")
async def verify_agent(request: Request, agent_id: str):
    """On-demand identity verification for a specific agent."""
    agent_id = agent_id.upper()
    try:
        regis  = _get_regis()
        result = await asyncio.to_thread(regis.identity.verify_agent, agent_id, "")
        trust  = await asyncio.to_thread(regis.identity.get_trust_score, agent_id)
        return {
            "agent_id":    agent_id,
            "verified":    result.get("verified", False),
            "trust_score": trust,
            "reason":      result.get("reason", ""),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Background helpers ─────────────────────────────────────────────────────────

async def _audit_swarm_launch(task_id: str, description: str, agents: list[str]):
    """Write audit log entry for swarm launch."""
    try:
        from services.pocketbase import PocketBaseService
        pb = PocketBaseService()
        await asyncio.to_thread(pb.create, "audit_log", {
            "event_type": "task_submitted",
            "entity_id":  task_id,
            "message":    (
                f"REGIS dispatched swarm · "
                f"{len(agents)} agents via XMTP+Myriad+Allium+Uniblock · "
                f"{description[:80]}"
            ),
            "metadata": {"agents": agents, "source": "sovereign_swarm"},
        })
    except Exception as exc:
        logger.debug("[swarm audit] %s", exc)


# ── Module constants ───────────────────────────────────────────────────────────

_AGENT_XMTP_TOPICS = {
    "ATLAS":  "task.research",
    "CIPHER": "task.analysis",
    "FORGE":  "task.synthesis",
    "BISHOP": "task.compliance",
    "SØN":    "task.observation",
    "REGIS":  "task.coordinate",
}


def _agent_address(agent_id: str) -> str:
    import hashlib
    h = hashlib.sha256(f"swarmpay_agent_{agent_id}".encode()).hexdigest()
    return f"0x{h[:40]}"
