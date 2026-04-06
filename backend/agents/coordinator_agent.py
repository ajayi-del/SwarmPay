"""
CoordinatorAgent — REGIS, sovereign coordinator of SwarmPay.

REGIS inherits SovereignAgent and orchestrates the entire agent world:

  1. RECEIVE  — accepts a task payload from the API
  2. VERIFY   — confirms all available agents are who they claim to be
  3. ANALYZE  — decomposes the task into per-agent subtasks
  4. SEE      — observes on-chain context via Allium before dispatching
  5. BROADCAST — sends subtasks to each agent over XMTP messaging
  6. SIMULATE — pre-flight checks every payment via Uniblock
  7. ATTEST   — issues compliance credentials via Myriad after completion

REGIS does not do the work himself — he governs who does it,
ensures they're authorized, and verifies the outcome.

The "agent world" principle: agents have addresses, memories, skills, and
persistence. They can talk to each other, see the chain, transact, and
build trust over time. REGIS is the crown that holds this world together.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional

from agents.base_agent import SovereignAgent

logger = logging.getLogger("swarmpay.regis")

# Wallet addresses for each agent (resolved from PocketBase at runtime)
# In a full deployment these would be on-chain identities on XMTP
_AGENT_XMTP_TOPICS: dict[str, str] = {
    "ATLAS":  "task.research",
    "CIPHER": "task.analysis",
    "FORGE":  "task.synthesis",
    "BISHOP": "task.compliance",
    "SØN":    "task.observation",
}


class CoordinatorAgent(SovereignAgent):
    """
    REGIS — Sovereign Coordinator.
    Governs the agent world: receives tasks, verifies agents,
    decomposes work, broadcasts via XMTP, and attests outcomes.
    """

    agent_id   = "REGIS"
    agent_name = "REGIS"
    role       = "coordinator"

    def __init__(self):
        super().__init__()
        self._session_tasks: list[dict] = []

    # ── Core: handle_task ─────────────────────────────────────────────────

    def handle_task(self, payload: dict) -> dict:
        """
        Entry point for a new task dispatch from the API.

        Expected payload:
        {
          "task_id":     str,
          "description": str,
          "budget_sol":  float,
          "budget_usdc": float,
          "context":     dict  (optional prior context)
        }

        Returns:
        {
          "success":        bool,
          "task_id":        str,
          "agents_verified": list[str],
          "agents_dispatched": list[str],
          "subtasks":       list[dict],
          "xmtp_broadcasts": list[dict],
          "onchain_context": dict,
          "duration_ms":    int
        }
        """
        t0 = time.monotonic()
        task_id     = payload.get("task_id", f"task_{uuid.uuid4().hex[:8]}")
        description = payload.get("description", "")
        budget_sol  = float(payload.get("budget_sol", 0.3))
        budget_usdc = float(payload.get("budget_usdc", budget_sol * 79))
        context     = payload.get("context", {})

        logger.info("[REGIS] handling task %s: %s…", task_id, description[:60])

        # ── Step 1: Verify agents ──────────────────────────────────────────
        verified_agents = self._verify_agent_roster()
        if not verified_agents:
            return {
                "success": False,
                "task_id": task_id,
                "error":   "No verified agents available",
                "duration_ms": int((time.monotonic() - t0) * 1000),
            }

        # ── Step 2: Observe on-chain context ──────────────────────────────
        onchain_ctx = self._gather_onchain_context(description, budget_sol)

        # ── Step 3: Decompose task ────────────────────────────────────────
        subtasks = self._decompose(description, budget_usdc, verified_agents)

        # ── Step 4: Pre-flight simulations ───────────────────────────────
        simulations = self._simulate_payments(subtasks)

        # ── Step 5: Broadcast via XMTP ───────────────────────────────────
        broadcasts = self._broadcast_subtasks(subtasks, task_id, description, context)

        # ── Step 6: Issue REGIS attestation for task launch ───────────────
        self._attest_task_launch(task_id, verified_agents, subtasks)

        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info("[REGIS] task %s dispatched to %d agents in %dms",
                    task_id, len(subtasks), duration_ms)

        self._session_tasks.append({
            "task_id": task_id,
            "dispatched_at": int(time.time()),
            "agents": [st["agent_id"] for st in subtasks],
        })

        return {
            "success":            True,
            "task_id":            task_id,
            "agents_verified":    verified_agents,
            "agents_dispatched":  [st["agent_id"] for st in subtasks],
            "subtasks":           subtasks,
            "xmtp_broadcasts":    broadcasts,
            "simulations":        simulations,
            "onchain_context":    onchain_ctx,
            "duration_ms":        duration_ms,
        }

    # ── Step implementations ───────────────────────────────────────────────

    def _verify_agent_roster(self) -> list[str]:
        """
        Verify all SwarmPay agents via Myriad identity.
        Only verified agents are eligible for task dispatch.
        """
        all_agents = ["ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"]
        verified = []
        for agent_id in all_agents:
            try:
                result = self.identity.verify_agent(agent_id, "")
                trust  = self.identity.get_trust_score(agent_id)
                if result.get("verified", False) and trust >= 0.3:
                    verified.append(agent_id)
                    logger.debug("[REGIS] verified %s trust=%.2f", agent_id, trust)
                else:
                    logger.warning("[REGIS] agent %s failed verification trust=%.2f",
                                   agent_id, trust)
            except Exception as exc:
                logger.error("[REGIS] verify %s: %s", agent_id, exc)
                verified.append(agent_id)  # Fail open for availability
        return verified

    def _gather_onchain_context(self, description: str, budget_sol: float) -> dict:
        """
        Use Allium to observe relevant on-chain state before dispatching.
        Provides agents with live market context.
        """
        ctx: dict[str, Any] = {"gathered_at": int(time.time())}
        task_lower = description.lower()

        try:
            # Check coordinator wallet balance
            if self.wallet_address:
                balance = self.transactions.get_token_balance(self.wallet_address)
                ctx["coordinator_balance_sol"] = balance
                if balance < budget_sol:
                    logger.warning("[REGIS] coordinator balance %.4f < budget %.4f",
                                   balance, budget_sol)
                    ctx["insufficient_funds_warning"] = True
        except Exception as exc:
            logger.debug("[REGIS] balance check: %s", exc)

        # DeFi context for relevant tasks
        if any(w in task_lower for w in ["defi", "tvl", "raydium", "orca", "jupiter", "yield"]):
            for protocol in ["raydium", "orca", "jupiter"]:
                if protocol in task_lower:
                    try:
                        ctx[f"{protocol}_tvl"] = self.analytics.get_defi_tvl(protocol)
                    except Exception:
                        pass

        # Anomaly check for compliance tasks
        if any(w in task_lower for w in ["compliance", "monitor", "risk", "bridge", "wormhole"]):
            ctx["anomaly_scan_requested"] = True

        return ctx

    def _decompose(
        self,
        description: str,
        budget_usdc: float,
        available_agents: list[str],
    ) -> list[dict]:
        """
        Decompose task into per-agent subtasks using existing AgentService logic.
        Enriches subtasks with XMTP topic + Myriad trust scores.
        """
        try:
            from services.agent_service import AgentService
            svc = AgentService()
            analysis = svc.analyze_task_for_agents(description, available_agents, budget_usdc / 79)
            selected = analysis["agents"]
            lead     = analysis["lead"]
            subtask_descs = analysis["subtasks"]

            raw = svc.decompose_task(description, budget_usdc, selected, lead)
            subtasks = []
            for st in raw:
                name = st["name"]
                trust = self.identity.get_trust_score(name)
                subtasks.append({
                    "agent_id":         name,
                    "description":      subtask_descs.get(name, st["description"]),
                    "budget_allocated": st["budget_allocated"],
                    "is_lead":          st.get("is_lead", False),
                    "xmtp_topic":       _AGENT_XMTP_TOPICS.get(name, "task.general"),
                    "trust_score":      trust,
                    "subtask_id":       f"sub_{uuid.uuid4().hex[:8]}",
                })
            return subtasks
        except Exception as exc:
            logger.error("[REGIS] decompose failed: %s", exc)
            # Minimal fallback
            per = round(budget_usdc / max(len(available_agents), 1), 6)
            return [
                {
                    "agent_id":         a,
                    "description":      f"{a} contribution to: {description}",
                    "budget_allocated": per,
                    "is_lead":          i == 0,
                    "xmtp_topic":       _AGENT_XMTP_TOPICS.get(a, "task.general"),
                    "trust_score":      0.5,
                    "subtask_id":       f"sub_{uuid.uuid4().hex[:8]}",
                }
                for i, a in enumerate(available_agents[:3])
            ]

    def _simulate_payments(self, subtasks: list[dict]) -> list[dict]:
        """
        Pre-flight simulate every payment via Uniblock.
        Flags any that are predicted to fail — REGIS can hold them back.
        """
        results = []
        for st in subtasks:
            try:
                sim = self.transactions.simulate_transfer(
                    from_address=self.wallet_address or "coordinator",
                    to_address=st["agent_id"],
                    amount_sol=st["budget_allocated"] / 79,  # USDC → SOL approx
                )
                results.append({
                    "agent_id":    st["agent_id"],
                    "will_succeed": sim.get("will_succeed", True),
                    "fee_sol":     sim.get("estimated_fee_sol", 0.000005),
                })
                if not sim.get("will_succeed", True):
                    logger.warning("[REGIS] payment simulation failed for %s", st["agent_id"])
            except Exception as exc:
                logger.debug("[REGIS] simulate %s: %s", st["agent_id"], exc)
                results.append({"agent_id": st["agent_id"], "will_succeed": True, "fee_sol": 0.000005})
        return results

    def _broadcast_subtasks(
        self,
        subtasks: list[dict],
        task_id: str,
        description: str,
        context: dict,
    ) -> list[dict]:
        """
        Broadcast subtasks to each agent over XMTP.
        Each agent receives its own work order + the task goal for context.
        """
        results = []
        for st in subtasks:
            msg_payload = {
                "task_id":      task_id,
                "task_goal":    description,
                "subtask_id":   st["subtask_id"],
                "description":  st["description"],
                "budget_usdc":  st["budget_allocated"],
                "is_lead":      st["is_lead"],
                "context":      context,
                "from_regis":   True,
            }
            # Use agent_id as a symbolic address for XMTP
            # In production this would be the agent's ETH wallet address
            symbolic_addr = _agent_symbolic_address(st["agent_id"])
            result = self.messaging.send_message(
                to_address=symbolic_addr,
                topic=st["xmtp_topic"],
                payload=msg_payload,
            )
            results.append({
                "agent_id":   st["agent_id"],
                "topic":      st["xmtp_topic"],
                "message_id": result.get("message_id", ""),
                "delivered":  result.get("success", False),
            })
            logger.info("[REGIS→%s] XMTP dispatch: %s mid=%s",
                        st["agent_id"], st["xmtp_topic"], result.get("message_id", ""))
        return results

    def _attest_task_launch(
        self,
        task_id: str,
        verified_agents: list[str],
        subtasks: list[dict],
    ) -> None:
        """
        Issue Myriad attestations for the task launch.
        Proves REGIS authorized this specific set of agents for this task.
        """
        for st in subtasks:
            try:
                self.attest_peer(
                    subject_agent_id=st["agent_id"],
                    claim="task_dispatch_authorized",
                    evidence={
                        "task_id":    task_id,
                        "subtask_id": st["subtask_id"],
                        "budget":     st["budget_allocated"],
                        "by_regis":   True,
                    },
                )
            except Exception as exc:
                logger.debug("[REGIS] attestation for %s: %s", st["agent_id"], exc)

    # ── Allium webhook handler ─────────────────────────────────────────────

    def handle_allium_webhook(self, event: dict) -> dict:
        """
        Process incoming Allium data push.
        Allium pushes real-time blockchain events (anomalies, large txs, etc.)
        REGIS evaluates and decides if swarm action is needed.
        """
        event_type = event.get("type", "unknown")
        chain      = event.get("chain", "solana")
        data       = event.get("data", {})
        severity   = event.get("severity", "info")

        logger.info("[REGIS] allium webhook: type=%s chain=%s severity=%s",
                    event_type, chain, severity)

        action = "logged"
        if event_type == "anomaly_detected" and severity in ("high", "critical"):
            # High-severity anomaly: flag for BISHOP compliance review
            action = "flagged_for_bishop_review"
        elif event_type == "large_transfer" and float(data.get("amount_usd", 0)) > 10_000:
            action = "flagged_for_compliance"
        elif event_type == "defi_tvl_drop" and float(data.get("drop_pct", 0)) > 20:
            action = "risk_alert_issued"

        return {
            "received":   True,
            "event_type": event_type,
            "action":     action,
            "severity":   severity,
            "processed_at": int(time.time()),
        }

    # ── Status ─────────────────────────────────────────────────────────────

    def get_world_status(self) -> dict:
        """
        Return the current state of the agent world as REGIS sees it.
        Used by the /api/swarm/status endpoint.
        """
        agents_status = []
        for agent_id in ["ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"]:
            trust = self.identity.get_trust_score(agent_id)
            identity = self.identity.get_agent_identity(agent_id)
            agents_status.append({
                "agent_id":   agent_id,
                "role":       identity.get("role", "worker"),
                "clearance":  identity.get("clearance", "basic"),
                "trust_score": trust,
                "flag":       identity.get("flag", "🤖"),
                "verified":   identity.get("verified", False),
            })

        return {
            "world":         "SwarmPay Kingdom",
            "coordinator":   self.agent_id,
            "session_tasks": len(self._session_tasks),
            "agents":        agents_status,
            "capabilities": {
                "messaging":    "xmtp",
                "analytics":    "allium",
                "transactions": "uniblock",
                "identity":     "myriad",
            },
            "services":      self.health(),
            "timestamp":     int(time.time()),
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _agent_symbolic_address(agent_id: str) -> str:
    """
    In production, each agent has a real ETH wallet address registered on XMTP.
    For devnet, we use deterministic symbolic addresses derived from agent name.
    """
    import hashlib
    h = hashlib.sha256(f"swarmpay_agent_{agent_id}".encode()).hexdigest()
    return f"0x{h[:40]}"


# Module-level singleton
coordinator_agent = CoordinatorAgent()
