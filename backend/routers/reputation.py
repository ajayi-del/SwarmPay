"""
Reputation API endpoints
Using Claude Code RESTful API patterns
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging

from ..services.reputation_service import ReputationPolicyEngine
from ..services.pocketbase import PocketBaseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reputation", tags=["reputation"])

# Pydantic models for API
class ReputationEvaluationRequest(BaseModel):
    agent_id: str
    amount: float

class ReputationEvaluationResponse(BaseModel):
    allow: bool
    reason: str
    reputation: float
    threshold: Optional[Dict] = None
    requires_coordinator: Optional[bool] = False

class ReputationUpdateRequest(BaseModel):
    agent_id: str
    success: bool

class ReputationUpdateResponse(BaseModel):
    agent_id: str
    previous_reputation: float
    new_reputation: float
    change: str
    event_type: str

# Dependency injection
async def get_reputation_service() -> ReputationPolicyEngine:
    from ..main import get_reputation_service
    return await get_reputation_service()

@router.post("/evaluate", response_model=ReputationEvaluationResponse)
async def evaluate_payment(
    request: ReputationEvaluationRequest,
    reputation_service: ReputationPolicyEngine = Depends(get_reputation_service)
):
    """Evaluate payment amount against agent reputation"""
    try:
        result = await reputation_service.evaluate_payment(request.agent_id, request.amount)
        
        return ReputationEvaluationResponse(**result)
        
    except Exception as e:
        logger.error(f"Reputation evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update", response_model=ReputationUpdateResponse)
async def update_reputation(
    request: ReputationUpdateRequest,
    reputation_service: ReputationPolicyEngine = Depends(get_reputation_service)
):
    """Update agent reputation based on task outcome"""
    try:
        result = await reputation_service.update_reputation(request.agent_id, request.success)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return ReputationUpdateResponse(**result)
        
    except Exception as e:
        logger.error(f"Reputation update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{agent_id}")
async def get_reputation_history(
    agent_id: str,
    limit: int = 50,
    reputation_service: ReputationPolicyEngine = Depends(get_reputation_service)
):
    """Get reputation change history for an agent"""
    try:
        history = await reputation_service.get_reputation_history(agent_id, limit)
        
        return {
            "agent_id": agent_id,
            "history": history,
            "total_changes": len(history)
        }
        
    except Exception as e:
        logger.error(f"Failed to get reputation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/thresholds")
async def get_reputation_thresholds(
    reputation_service: ReputationPolicyEngine = Depends(get_reputation_service)
):
    """Get all reputation thresholds for reference"""
    try:
        thresholds = {}
        for level, threshold in reputation_service.thresholds.items():
            thresholds[level.value] = {
                "stars": threshold.stars,
                "max_auto_approve": threshold.max_auto_approve,
                "requires_coordinator": threshold.requires_coordinator,
                "level": threshold.level.value
            }
        
        return {"thresholds": thresholds}
        
    except Exception as e:
        logger.error(f"Failed to get thresholds: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/agent/{agent_id}")
async def get_agent_reputation(
    agent_id: str,
    reputation_service: ReputationPolicyEngine = Depends(get_reputation_service)
):
    """Get current reputation for a specific agent"""
    try:
        reputation = await reputation_service._get_agent_reputation(agent_id)
        threshold = reputation_service._get_reputation_threshold(reputation)
        
        return {
            "agent_id": agent_id,
            "reputation": reputation,
            "level": threshold.level.value,
            "max_auto_approve": threshold.max_auto_approve,
            "requires_coordinator": threshold.requires_coordinator
        }
        
    except Exception as e:
        logger.error(f"Failed to get agent reputation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
