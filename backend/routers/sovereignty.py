"""
Sovereignty Router — kingdom succession endpoints.

  GET  /sovereignty/status        full succession state
  GET  /sovereignty/leaderboard   all agents ranked by lifetime_earnings
  POST /sovereignty/test-overthrow  force-trigger overthrow for testing (admin key required)
"""

import asyncio
import logging
import os
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from services.sovereignty_service import sovereignty_service, notify_overthrow

logger = logging.getLogger("swarmpay.sovereignty")

router = APIRouter(prefix="/sovereignty", tags=["sovereignty"])


@router.get("/status")
async def get_sovereignty_status():
    """Full sovereignty state: ruler, former rulers, closest challenger, leaderboard."""
    try:
        return await asyncio.to_thread(sovereignty_service.get_status)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/leaderboard")
async def get_leaderboard():
    """All agents ranked by lifetime_earnings_usdc descending."""
    try:
        all_records = await asyncio.to_thread(sovereignty_service.get_all)
        from services.agent_service import AGENT_PERSONAS, COORDINATOR_PERSONA
        _pm = {p["name"]: p for p in AGENT_PERSONAS}
        _pm["REGIS"] = COORDINATOR_PERSONA

        _rate = 79.0
        result = []
        for r in all_records:
            aid = r.get("agent_id", "")
            persona = _pm.get(aid, {})
            earn_usdc = float(r.get("lifetime_earnings_usdc", 0))
            dist_usdc = float(r.get("lifetime_distributed_usdc", 0))
            result.append({
                "agent_id":               aid,
                "city":                   persona.get("city", ""),
                "flag":                   persona.get("flag", ""),
                "role":                   persona.get("role", ""),
                "lifetime_earnings_usdc": earn_usdc,
                "lifetime_earnings_sol":  round(earn_usdc / _rate, 6),
                "lifetime_distributed_usdc": dist_usdc,
                "lifetime_distributed_sol":  round(dist_usdc / _rate, 6),
                "is_ruler":               bool(r.get("is_ruler")),
                "times_ruled":            int(r.get("times_ruled", 0)),
                "overthrow_count":        int(r.get("overthrow_count", 0)),
                "ascended_at":            r.get("ascended_at", ""),
            })
        return {"leaderboard": result, "count": len(result)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class TestOverthrowRequest(BaseModel):
    agent: str = "CIPHER"   # which agent to force to overthrow REGIS


@router.post("/test-overthrow")
async def test_overthrow(
    body: TestOverthrowRequest,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """
    Force-trigger an overthrow for testing. Requires X-Admin-Key header.
    Sets the target agent's lifetime_earnings just above REGIS distributed
    so the check fires naturally — no short-circuit hacks.
    """
    admin_key = os.environ.get("ADMIN_API_KEY", "")
    if not admin_key or x_admin_key != admin_key:
        raise HTTPException(status_code=403, detail="Invalid or missing admin key")

    try:
        # Ensure both REGIS and target agent have sovereignty records
        await asyncio.to_thread(sovereignty_service._get_or_create, "REGIS")
        await asyncio.to_thread(sovereignty_service._get_or_create, body.agent)

        # Get REGIS's current distributed amount
        status = await asyncio.to_thread(sovereignty_service.get_status)
        ruler = status.get("current_ruler") or {}
        regis_distributed = float(ruler.get("lifetime_distributed_usdc", 0))

        # Ensure REGIS has enough distributed to pass the minimum threshold
        if regis_distributed < 0.5:
            await asyncio.to_thread(
                sovereignty_service.update_distributed, "REGIS", 1.0
            )
            regis_distributed = 1.0

        # Set agent earnings just above threshold (ruler distributed + 0.01 USDC)
        target_earnings = regis_distributed + 0.01
        rec = await asyncio.to_thread(sovereignty_service._get_or_create, body.agent)
        if rec.get("id"):
            from services.pocketbase import PocketBaseService
            pb = PocketBaseService()
            pb.update("sovereignty", rec["id"], {
                "lifetime_earnings_usdc": target_earnings
            })

        # Now trigger the real check
        overthrow = await asyncio.to_thread(sovereignty_service.check_and_execute_overthrow)
        if overthrow:
            await notify_overthrow(overthrow)
            return {
                "triggered": True,
                "old_ruler": overthrow["old_ruler"].get("agent_id"),
                "new_ruler": overthrow["new_ruler"].get("agent_id"),
                "margin_usdc": round(target_earnings - regis_distributed, 4),
                "message": "Overthrow executed. Voice, email, and Telegram fired.",
            }
        else:
            return {
                "triggered": False,
                "message": "Check ran but no overthrow — check minimum threshold or current ruler state.",
                "regis_distributed": regis_distributed,
                "target_earnings":   target_earnings,
            }
    except (HTTPException, ValueError):
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
