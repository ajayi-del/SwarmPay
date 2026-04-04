"""
Policy Service - Enforces spending rules before payments
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel

class PolicyResult(BaseModel):
    allow: bool
    reason: Optional[str] = None

class PolicyService:
    def __init__(self):
        pass
    
    def evaluate_payment(self, 
                        from_wallet: Dict[str, Any], 
                        to_wallet: Dict[str, Any], 
                        amount: float, 
                        sub_task: Dict[str, Any]) -> PolicyResult:
        """
        Evaluate payment against all policy rules
        
        Args:
            from_wallet: Source wallet data
            to_wallet: Destination wallet data  
            amount: Payment amount
            sub_task: Sub-task data for budget checking
        
        Returns:
            PolicyResult with allow/deny decision and reason
        """
        
        # Rule 1: Budget cap check
        budget_result = self._check_budget_cap(amount, sub_task)
        if not budget_result.allow:
            return budget_result
        
        # Rule 2: Coordinator authorization check
        auth_result = self._check_coordinator_auth(from_wallet)
        if not auth_result.allow:
            return auth_result
        
        # Rule 3: Double payment check
        double_pay_result = self._check_double_payment(sub_task)
        if not double_pay_result.allow:
            return double_pay_result
        
        # All checks passed
        return PolicyResult(allow=True)
    
    def _check_budget_cap(self, amount: float, sub_task: Dict[str, Any]) -> PolicyResult:
        """Rule 1: Payment cannot exceed sub-task budget allocation"""
        budget_allocated = sub_task.get("budget_allocated", 0)
        
        if amount > budget_allocated:
            return PolicyResult(
                allow=False,
                reason=f"Policy violation: amount {amount} exceeds cap {budget_allocated}"
            )
        
        return PolicyResult(allow=True)
    
    def _check_coordinator_auth(self, from_wallet: Dict[str, Any]) -> PolicyResult:
        """Rule 2: Only coordinator wallets can sign payments"""
        wallet_role = from_wallet.get("role")
        
        if wallet_role != "coordinator":
            return PolicyResult(
                allow=False,
                reason="Unauthorized signer: only coordinator can pay"
            )
        
        return PolicyResult(allow=True)
    
    def _check_double_payment(self, sub_task: Dict[str, Any]) -> PolicyResult:
        """Rule 3: Prevent double payments for the same sub-task"""
        sub_task_status = sub_task.get("status")
        
        if sub_task_status == "paid":
            return PolicyResult(
                allow=False,
                reason="Double payment attempt blocked by policy engine"
            )
        
        return PolicyResult(allow=True)
    
    def log_policy_decision(self, 
                           payment_id: str, 
                           result: PolicyResult, 
                           metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create audit log entry for policy decision"""
        from services.pocketbase import PocketBaseService
        
        pb = PocketBaseService()
        
        event_type = "payment_signed" if result.allow else "payment_blocked"
        message = f"Payment {payment_id}: {'APPROVED' if result.allow else 'BLOCKED'}"
        
        if result.reason:
            message += f" - {result.reason}"
        
        audit_data = {
            "id": f"audit_{payment_id}",
            "event_type": event_type,
            "entity_id": payment_id,
            "message": message,
            "metadata": metadata or {},
            "created_at": "now()"
        }
        
        try:
            return pb.create("audit_log", audit_data)
        except Exception as e:
            print(f"Failed to log policy decision: {e}")
            return {"id": "audit_failed"}
