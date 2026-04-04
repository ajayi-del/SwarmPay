"""
Audit Router - Handles audit log and wallet endpoints
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.pocketbase import PocketBaseService

router = APIRouter(tags=["audit", "wallets"])

pb = PocketBaseService()

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
