"""
Policy Service — reputation-gated, three-rule payment engine.

Rule order:
  1. REP GATE     — reputation score → per-agent spend limit
  2. BUDGET CAP   — coordinator allocation ceiling
  3. COORD AUTH   — only coordinator wallets may sign
  4. DOUBLE PAY   — no duplicate payments for the same sub-task
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel


class PolicyResult(BaseModel):
    allow: bool
    reason: Optional[str] = None


# Spend limits per star tier — calibrated to actual agent allocations:
#   5★ CIPHER  0.100 ETH → approved (limit 0.20)
#   4★ ATLAS   0.100 ETH → approved (limit 0.12)
#   4★ BISHOP  0.120 ETH → approved (limit 0.12)
#   4★ FORGE   0.150 ETH → REP BLOCK (0.15 > 0.12) ← demo block
#   3★ SØN     0.050 ETH → approved (limit 0.06)
_REP_TIERS = [
    (5.0, 0.20),
    (4.0, 0.12),
    (3.0, 0.06),
    (2.0, 0.02),
]


def _rep_limit(reputation: float) -> float:
    """Return maximum auto-approved ETH for this reputation score."""
    for floor, limit in _REP_TIERS:
        if reputation >= floor:
            return limit
    return 0.0  # < 2.0 → blocked entirely


def _stars_label(reputation: float) -> str:
    filled = int(reputation)
    return f"{reputation:.1f}★"


class PolicyService:
    def evaluate_payment(
        self,
        from_wallet: Dict[str, Any],
        to_wallet: Dict[str, Any],
        amount: float,
        sub_task: Dict[str, Any],
        reputation: float = 3.0,
    ) -> PolicyResult:
        """Evaluate all four rules in order, returning first failure."""

        for check in (
            self._check_reputation_gate,
            self._check_budget_cap,
            self._check_coordinator_auth,
            self._check_double_payment,
        ):
            result = check(amount=amount, sub_task=sub_task,
                           from_wallet=from_wallet, reputation=reputation)
            if not result.allow:
                return result

        return PolicyResult(allow=True)

    # ── Rule 1 ────────────────────────────────────────────────────────────

    def _check_reputation_gate(self, *, amount: float, sub_task: Dict[str, Any],
                                reputation: float, **_) -> PolicyResult:
        agent_id = sub_task.get("agent_id", "AGENT")
        limit = _rep_limit(reputation)
        stars = _stars_label(reputation)

        if reputation < 2.0:
            return PolicyResult(
                allow=False,
                reason=(
                    f"REP BLOCK: {agent_id} reputation {stars} — "
                    f"agent suspended (minimum 2★ required)"
                ),
            )

        if amount > limit:
            return PolicyResult(
                allow=False,
                reason=(
                    f"REP BLOCK: {agent_id} reputation {stars} insufficient "
                    f"for {amount:.4f} ETH ({stars} limit: {limit:.2f} ETH)"
                ),
            )

        return PolicyResult(allow=True)

    # ── Rule 2 ────────────────────────────────────────────────────────────

    def _check_budget_cap(self, *, amount: float, sub_task: Dict[str, Any],
                           **_) -> PolicyResult:
        allocated = float(sub_task.get("budget_allocated", 0))
        if amount > allocated:
            return PolicyResult(
                allow=False,
                reason=(
                    f"BUDGET BLOCK: requested {amount:.4f} ETH exceeds "
                    f"coordinator allocation {allocated:.4f} ETH"
                ),
            )
        return PolicyResult(allow=True)

    # ── Rule 3 ────────────────────────────────────────────────────────────

    def _check_coordinator_auth(self, *, from_wallet: Dict[str, Any],
                                 **_) -> PolicyResult:
        if from_wallet.get("role") != "coordinator":
            return PolicyResult(
                allow=False,
                reason="AUTH BLOCK: only coordinator wallet may sign payments",
            )
        return PolicyResult(allow=True)

    # ── Rule 4 ────────────────────────────────────────────────────────────

    def _check_double_payment(self, *, sub_task: Dict[str, Any],
                               **_) -> PolicyResult:
        if sub_task.get("status") == "paid":
            return PolicyResult(
                allow=False,
                reason="DOUBLE PAY BLOCK: sub-task already settled",
            )
        return PolicyResult(allow=True)
