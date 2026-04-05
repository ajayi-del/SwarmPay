"""
Reputation-Gated Policy Engine
Based on Claude Code Skill System pattern for dynamic policy evaluation
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)

class ReputationLevel(Enum):
    BLOCKED = "blocked"
    LIMITED = "limited"
    STANDARD = "standard"
    ENHANCED = "enhanced"
    PREMIUM = "premium"

@dataclass
class ReputationThreshold:
    stars: float
    max_auto_approve: float
    requires_coordinator: bool
    level: ReputationLevel

class ReputationPolicyEngine:
    """Reputation-based policy engine using Claude Code Skill System pattern"""
    
    def __init__(self, pocketbase_service):
        self.pb = pocketbase_service
        self.thresholds = self._initialize_thresholds()
        
    def _initialize_thresholds(self) -> Dict[ReputationLevel, ReputationThreshold]:
        """Initialize reputation thresholds based on requirements"""
        return {
            ReputationLevel.PREMIUM: ReputationThreshold(
                stars=5.0,
                max_auto_approve=0.15,
                requires_coordinator=False,
                level=ReputationLevel.PREMIUM
            ),
            ReputationLevel.ENHANCED: ReputationThreshold(
                stars=4.0,
                max_auto_approve=0.10,
                requires_coordinator=False,
                level=ReputationLevel.ENHANCED
            ),
            ReputationLevel.STANDARD: ReputationThreshold(
                stars=3.0,
                max_auto_approve=0.05,
                requires_coordinator=False,
                level=ReputationLevel.STANDARD
            ),
            ReputationLevel.LIMITED: ReputationThreshold(
                stars=2.0,
                max_auto_approve=0.02,
                requires_coordinator=True,
                level=ReputationLevel.LIMITED
            ),
            ReputationLevel.BLOCKED: ReputationThreshold(
                stars=1.0,
                max_auto_approve=0.0,
                requires_coordinator=True,
                level=ReputationLevel.BLOCKED
            )
        }
    
    async def evaluate_payment(self, agent_id: str, amount: float) -> Dict:
        """
        Evaluate payment using reputation-based policy
        Returns: {allow: bool, reason: str, threshold: ReputationThreshold}
        """
        try:
            # Get agent reputation
            reputation = await self._get_agent_reputation(agent_id)
            threshold = self._get_reputation_threshold(reputation)
            
            # Check if blocked entirely
            if threshold.level == ReputationLevel.BLOCKED:
                return {
                    "allow": False,
                    "reason": f"REP BLOCK: reputation {reputation:.1f} insufficient for {amount:.3f} ETH",
                    "threshold": threshold,
                    "reputation": reputation
                }
            
            # Check auto-approval limit
            if amount <= threshold.max_auto_approve:
                return {
                    "allow": True,
                    "reason": f"REP APPROVE: {amount:.3f} ETH within {threshold.level.value} limit",
                    "threshold": threshold,
                    "reputation": reputation
                }
            
            # Check if requires coordinator approval
            if threshold.requires_coordinator:
                return {
                    "allow": False,
                    "reason": f"REP BLOCK: reputation {reputation:.1f} requires coordinator approval for {amount:.3f} ETH",
                    "threshold": threshold,
                    "reputation": reputation,
                    "requires_coordinator": True
                }
            
            # Amount exceeds limit
            return {
                "allow": False,
                "reason": f"BUDGET BLOCK: {amount:.3f} ETH exceeds {threshold.level.value} limit of {threshold.max_auto_approve:.3f}",
                "threshold": threshold,
                "reputation": reputation
            }
            
        except Exception as e:
            logger.error(f"Reputation evaluation failed: {e}")
            return {
                "allow": False,
                "reason": f"POLICY ERROR: {str(e)}",
                "threshold": None,
                "reputation": 0.0
            }
    
    async def _get_agent_reputation(self, agent_id: str) -> float:
        """Get agent reputation from PocketBase"""
        try:
            # Get agent record
            agent_records = await self.pb.get_records('agents', {
                'filter': f'id = "{agent_id}"'
            })
            
            if not agent_records:
                # New agent gets default reputation
                return 3.0
            
            agent = agent_records[0]
            return float(agent.get('reputation', 3.0))
            
        except Exception as e:
            logger.error(f"Failed to get agent reputation: {e}")
            return 3.0  # Default to standard
    
    def _get_reputation_threshold(self, reputation: float) -> ReputationThreshold:
        """Get threshold based on reputation score"""
        if reputation >= 5.0:
            return self.thresholds[ReputationLevel.PREMIUM]
        elif reputation >= 4.0:
            return self.thresholds[ReputationLevel.ENHANCED]
        elif reputation >= 3.0:
            return self.thresholds[ReputationLevel.STANDARD]
        elif reputation >= 2.0:
            return self.thresholds[ReputationLevel.LIMITED]
        else:
            return self.thresholds[ReputationLevel.BLOCKED]
    
    async def update_reputation(self, agent_id: str, success: bool) -> Dict:
        """
        Update agent reputation based on task outcome
        Success: +0.1 (max 5.0)
        Failed: -0.2 (min 1.0)
        """
        try:
            # Get current reputation
            current_rep = await self._get_agent_reputation(agent_id)
            
            # Calculate new reputation
            if success:
                new_rep = min(5.0, current_rep + 0.1)
                change = "+0.1"
                event_type = "TASK_SUCCESS"
            else:
                new_rep = max(1.0, current_rep - 0.2)
                change = "-0.2"
                event_type = "TASK_FAILED"
            
            # Update in PocketBase
            await self.pb.update_record('agents', agent_id, {
                'reputation': new_rep,
                'last_reputation_update': asyncio.get_event_loop().time()
            })
            
            # Log reputation change
            await self._log_reputation_change(agent_id, current_rep, new_rep, event_type)
            
            logger.info(f"Updated reputation for {agent_id}: {current_rep:.1f} → {new_rep:.1f} ({change})")
            
            return {
                "agent_id": agent_id,
                "previous_reputation": current_rep,
                "new_reputation": new_rep,
                "change": change,
                "event_type": event_type
            }
            
        except Exception as e:
            logger.error(f"Failed to update reputation: {e}")
            return {
                "agent_id": agent_id,
                "error": str(e)
            }
    
    async def _log_reputation_change(self, agent_id: str, old_rep: float, new_rep: float, event_type: str):
        """Log reputation change to audit log"""
        try:
            await self.pb.create_record('audit_log', {
                'agent_id': agent_id,
                'event_type': 'REPUTATION_CHANGE',
                'event_data': {
                    'old_reputation': old_rep,
                    'new_reputation': new_rep,
                    'event_type': event_type,
                    'change': new_rep - old_rep
                },
                'timestamp': asyncio.get_event_loop().time()
            })
        except Exception as e:
            logger.error(f"Failed to log reputation change: {e}")
    
    async def get_reputation_history(self, agent_id: str, limit: int = 50) -> List[Dict]:
        """Get reputation change history for an agent"""
        try:
            records = await self.pb.get_records('audit_log', {
                'filter': f'agent_id = "{agent_id}" AND event_type = "REPUTATION_CHANGE"',
                'sort': '-timestamp',
                'limit': limit
            })
            
            return records
            
        except Exception as e:
            logger.error(f"Failed to get reputation history: {e}")
            return []
