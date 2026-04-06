"""
SovereignAgent — Base class for all SwarmPay agents.

Every agent in the SwarmPay world inherits from SovereignAgent.
The base class wires four built-in capabilities at construction time:

  • self.messaging     → XMTPService    (talk — agent-to-agent messages)
  • self.analytics     → AlliumService  (see  — on-chain data observation)
  • self.transactions  → UniblockService (transact — multi-chain execution)
  • self.identity      → MyriadService  (verify — attestations + trust)

Plus shared utilities every agent needs:
  • self.log()         → structured audit logging to PocketBase
  • self.verify_peer() → confirm another agent's identity before trusting it
  • self.attest()      → issue a credential claim about another agent

Design contract:
  • Subclasses implement handle_task(payload) → dict
  • All capabilities degrade gracefully (mock mode if keys absent)
  • No __init__ args required — services are singletons
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger("swarmpay.agent")


class SovereignAgent(ABC):
    """
    Base class giving every SwarmPay agent its four sovereign capabilities:
    talk (XMTP), see (Allium), transact (Uniblock), verify (Myriad).
    """

    # Subclasses set these class-level attributes
    agent_id:   str = "AGENT"
    agent_name: str = "Agent"
    role:       str = "worker"
    wallet_address: Optional[str] = None

    def __init__(self):
        # Lazy-import singletons — avoids circular imports and makes tests easy
        from services.xmtp_service    import xmtp_service
        from services.allium_service  import allium_service
        from services.uniblock_service import uniblock_service
        from services.myriad_service  import myriad_service

        # ── Four sovereign capabilities ──────────────────────────────────
        self.messaging    = xmtp_service     # TALK
        self.analytics    = allium_service   # SEE
        self.transactions = uniblock_service # TRANSACT
        self.identity     = myriad_service   # VERIFY

        self._initialized_at = time.time()
        logger.info("[%s] sovereign agent initialized", self.agent_id)

    # ── Abstract interface — subclasses must implement ─────────────────────

    @abstractmethod
    def handle_task(self, payload: dict) -> dict:
        """
        Process an incoming task payload.

        Args:
            payload: Task description, budget, context, sender identity.

        Returns:
            Result dict with at minimum: { success, output, agent_id, duration_ms }
        """

    # ── Shared utilities ───────────────────────────────────────────────────

    def verify_peer(self, peer_agent_id: str, peer_wallet: Optional[str] = None) -> bool:
        """
        Verify a peer agent's identity before trusting their output.
        Returns True if identity is confirmed and trust score > 0.3.
        """
        result = self.identity.verify_agent(
            peer_agent_id,
            peer_wallet or "",
        )
        trust = self.identity.get_trust_score(peer_agent_id)
        verified = result.get("verified", False) and trust >= 0.3
        if not verified:
            logger.warning("[%s] peer verification failed for %s (trust=%.2f)",
                           self.agent_id, peer_agent_id, trust)
        return verified

    def attest_peer(
        self,
        subject_agent_id: str,
        claim: str,
        evidence: Optional[dict] = None,
    ) -> dict:
        """
        Issue a verifiable attestation about a peer agent.
        Called after reviewing another agent's output.
        """
        return self.identity.issue_attestation(
            issuer_agent=self.agent_id,
            subject_agent=subject_agent_id,
            claim=claim,
            evidence=evidence,
        )

    def send(self, to_address: str, topic: str, payload: dict) -> dict:
        """Convenience wrapper for sending a typed message to a wallet address."""
        return self.messaging.send_message(
            to_address=to_address,
            topic=topic,
            payload={**payload, "_from_agent": self.agent_id},
        )

    def observe_wallet(self, address: str, chain: str = "solana") -> dict:
        """Convenience: get on-chain summary for a wallet before interacting."""
        return self.analytics.get_wallet_summary(address, chain)

    def simulate_payment(self, to_address: str, amount_sol: float) -> dict:
        """Pre-flight check before any payment. Returns will_succeed + fee."""
        from_addr = self.wallet_address or "0x0"
        return self.transactions.simulate_transfer(from_addr, to_address, amount_sol)

    async def log(self, event_type: str, message: str, metadata: dict = None):
        """Fire-and-forget audit log write to PocketBase."""
        try:
            from services.pocketbase import PocketBaseService
            pb = PocketBaseService()
            await asyncio.to_thread(pb.create, "audit_log", {
                "event_type": event_type,
                "entity_id":  self.agent_id,
                "message":    message,
                "metadata":   metadata or {},
            })
        except Exception as exc:
            logger.warning("[%s] audit log failed: %s", self.agent_id, exc)

    def health(self) -> dict:
        """Return health status of all four capabilities."""
        return {
            "agent_id":      self.agent_id,
            "messaging":     "ok" if self.messaging.health_check() else "degraded",
            "analytics":     "ok" if self.analytics.health_check() else "degraded",
            "transactions":  "ok" if self.transactions.health_check() else "degraded",
            "identity":      "ok" if self.identity.health_check() else "degraded",
            "uptime_secs":   round(time.time() - self._initialized_at, 1),
        }

    def __repr__(self) -> str:
        return f"<SovereignAgent {self.agent_id} role={self.role}>"
