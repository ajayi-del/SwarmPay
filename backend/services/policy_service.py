"""
Policy Service — reputation-gated, three-rule payment engine.

Rule order:
  1. REP GATE     — reputation score → proportional budget cap (never zero)
  2. BUDGET CAP   — coordinator allocation ceiling
  3. COORD AUTH   — only coordinator wallets may sign
  4. DOUBLE PAY   — no duplicate payments for the same sub-task

FIX 1 — FORGE Rehabilitation:
  Reputation now controls a MULTIPLIER on budget_allocated (not a fixed USDC cap).
  Even at 0★ FORGE earns 20% of their allocation — never fully blocked.
  This prevents the death spiral where a blocked agent loses reputation,
  gets more blocked, loses more rep, etc.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel


class PolicyResult(BaseModel):
    allow: bool
    reason: Optional[str] = None
    # When True: payment allowed at reduced (probation) amount — caller must re-attempt with cap
    is_probation: bool = False
    effective_cap: Optional[float] = None


# Sliding reputation multipliers — applied to sub_task.budget_allocated
# Agent always earns something; higher rep = higher fraction of budget
_REP_TIERS = [
    (4.5, 1.0),   # 4.5★+  → 100% of budget
    (3.5, 0.85),  # 3.5-4.5 → 85%
    (2.5, 0.65),  # 2.5-3.5 → 65%
    (1.5, 0.45),  # 1.5-2.5 → 45%
    (0.5, 0.25),  # 0.5-1.5 → 25% (probation floor)
]
_PROBATION_FLOOR = 0.20  # absolute minimum even at 0★


def get_rep_multiplier(reputation: float) -> float:
    """
    Return payment multiplier (0.20 – 1.0) for a given reputation score.
    Applied to sub_task.budget_allocated to compute the effective cap.
    """
    for floor, multiplier in _REP_TIERS:
        if reputation >= floor:
            return multiplier
    return _PROBATION_FLOOR


def _stars_label(reputation: float) -> str:
    return f"{reputation:.1f}★"


def is_probation(reputation: float) -> bool:
    """True when agent is earning at reduced rate (rep < 3.5)."""
    return reputation < 3.5


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
        allocated = float(sub_task.get("budget_allocated", amount))
        multiplier = get_rep_multiplier(reputation)
        effective_cap = round(allocated * multiplier, 6)
        stars = _stars_label(reputation)

        if amount > effective_cap:
            prob = is_probation(reputation)
            return PolicyResult(
                allow=False,
                is_probation=prob,
                effective_cap=effective_cap,
                reason=(
                    f"REP GATE: {agent_id} {stars} — capped at {effective_cap:.4f} USDC "
                    f"({multiplier*100:.0f}% of budget · {'probation' if prob else 'rep tier'})"
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
                    f"BUDGET BLOCK: requested {amount:.4f} USDC exceeds "
                    f"coordinator allocation {allocated:.4f} USDC"
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
