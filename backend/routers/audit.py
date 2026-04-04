"""
Audit Router - Handles audit log, wallet, and swarm stats endpoints
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.pocketbase import PocketBaseService

router = APIRouter(tags=["audit", "wallets"])

pb = PocketBaseService()


@router.get("/swarm/stats")
async def get_swarm_stats() -> Dict[str, Any]:
    """Aggregate lifetime stats across all tasks and agents."""
    try:
        tasks     = pb.list("tasks",    limit=200)
        payments  = pb.list("payments", limit=500)
        reps      = pb.get_all_reputations()

        peer      = [p for p in payments if (p.get("policy_reason") or "").startswith("PEER:")]
        coord     = [p for p in payments if not (p.get("policy_reason") or "").startswith("PEER:")]
        signed    = [p for p in coord if p.get("status") == "signed"]
        blocked   = [p for p in coord if p.get("status") == "blocked"]

        total_coord = len(signed) + len(blocked)
        approval_rate = len(signed) / total_coord if total_coord else 1.0
        avg_rep = (sum(reps.values()) / len(reps)) if reps else 3.0

        health = round(approval_rate * 65 + (avg_rep / 5.0) * 35)

        agent_rankings = sorted(
            [{"agent_id": k, "reputation": v} for k, v in reps.items()],
            key=lambda x: x["reputation"],
            reverse=True,
        )

        return {
            "health_score":        health,
            "total_tasks":         len(tasks),
            "total_signed":        len(signed),
            "total_blocked":       len(blocked),
            "eth_processed":       round(sum(float(p["amount"]) for p in signed),  4),
            "eth_held":            round(sum(float(p["amount"]) for p in blocked), 4),
            "peer_count":          len(peer),
            "eth_peer":            round(sum(float(p["amount"]) for p in peer), 4),
            "avg_reputation":      round(avg_rep, 2),
            "agent_rankings":      agent_rankings,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get swarm stats: {str(e)}")


@router.get("/audit")
async def get_audit_logs(limit: int = Query(default=50, le=100)) -> Dict[str, List[Dict[str, Any]]]:
    """Get latest audit log entries"""
    try:
        logs = pb.list("audit_log", limit=limit, sort="-created")
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit logs: {str(e)}")

@router.get("/wallets")
async def get_wallets() -> Dict[str, List[Dict[str, Any]]]:
    """Get all wallets"""
    try:
        wallets = pb.list("wallets")
        return {"wallets": wallets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get wallets: {str(e)}")

@router.get("/wallets/{wallet_id}")
async def get_wallet(wallet_id: str) -> Dict[str, Any]:
    """Get specific wallet"""
    try:
        wallet = pb.get("wallets", wallet_id)
        return wallet
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Wallet not found: {str(e)}")

@router.post("/wallet/pay")
async def process_payment(request: Dict[str, Any]) -> Dict[str, Any]:
    """Manual payment processing endpoint"""
    try:
        from services.policy_service import PolicyService
        from services.ows_service import OWSService
        
        policy_service = PolicyService()
        ows_service = OWSService()
        
        # Get wallets
        from_wallet = pb.get("wallets", request["from_wallet_id"])
        to_wallet = pb.get("wallets", request["to_wallet_id"])
        
        # Get sub-task if provided
        sub_task = None
        if "task_id" in request:
            sub_tasks = pb.list("sub_tasks", f"task_id = '{request['task_id']}' and wallet_id = '{request['to_wallet_id']}'")
            if sub_tasks:
                sub_task = sub_tasks[0]
        
        # Evaluate policy
        policy_result = policy_service.evaluate_payment(
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            amount=request["amount"],
            sub_task=sub_task or {}
        )
        
        if not policy_result.allow:
            return {
                "status": "blocked",
                "policy_reason": policy_result.reason
            }
        
        # Process payment
        tx_result = ows_service.sign_payment(
            from_wallet=request["from_wallet_id"],
            to_wallet=request["to_wallet_id"],
            amount=request["amount"],
            chain_id=request.get("chain_id", "eip155:1")
        )
        
        return {
            "status": "signed",
            "tx_hash": tx_result.get("tx_hash"),
            "chain_id": tx_result.get("chain_id")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment processing failed: {str(e)}")
