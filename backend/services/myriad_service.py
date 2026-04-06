"""
Myriad Service — Agent identity, trust, and credential verification.

Myriad provides on-chain identity attestations and verifiable credentials.
Agents use this to:
  • Prove they are who they claim to be (wallet-bound identity)
  • Verify counterparty credentials before trusting outputs
  • Issue compliance attestations after task completion
  • Build a reputation ledger across sessions

In the SwarmPay world, every sovereign agent has a Myriad identity.
REGIS verifies all agent identities before dispatching work.
BISHOP uses Myriad attestations as part of compliance receipts.

Fallback contract:
  • If MYRIAD_API_KEY not set: mock mode with deterministic fake attestations
  • All methods return structured dicts
  • Synchronous — call via asyncio.to_thread

Env vars:
  MYRIAD_API_KEY     — from myriad network
  MYRIAD_NETWORK     — "mainnet" | "testnet" (default: "testnet")
"""

import hashlib
import json
import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger("swarmpay.myriad")

_API_KEY  = os.environ.get("MYRIAD_API_KEY", "").strip()
_NETWORK  = os.environ.get("MYRIAD_NETWORK", "testnet")
_BASE_URL = f"https://api.myriad.social/v1" if _NETWORK == "mainnet" else "https://api.testnet.myriad.social/v1"
_TIMEOUT  = 8

# SwarmPay agent identities — deterministic credential issuers
_AGENT_IDENTITIES: dict[str, dict] = {
    "REGIS":  {"role": "coordinator",  "clearance": "sovereign",  "flag": "🇬🇧"},
    "ATLAS":  {"role": "researcher",   "clearance": "analyst",    "flag": "🇩🇪"},
    "CIPHER": {"role": "analyst",      "clearance": "analyst",    "flag": "🇯🇵"},
    "FORGE":  {"role": "synthesizer",  "clearance": "producer",   "flag": "🇳🇬"},
    "BISHOP": {"role": "compliance",   "clearance": "auditor",    "flag": "🇻🇦"},
    "SØN":    {"role": "fund_tracker", "clearance": "observer",   "flag": "🇸🇪"},
}


class MyriadService:
    """
    Identity and trust layer for sovereign agents.
    Every agent interaction can be attested and verified on-chain.
    """

    def __init__(self):
        self._mock = not bool(_API_KEY)
        if self._mock:
            logger.warning("[myriad] MYRIAD_API_KEY not set — mock attestations")
        else:
            logger.info("[myriad] initialized on %s", _NETWORK)

    # ── Identity ───────────────────────────────────────────────────────────

    def get_agent_identity(self, agent_id: str) -> dict:
        """
        Resolve an agent's verified identity from Myriad.
        Returns { agent_id, wallet_address, role, clearance, verified, attestation_id }.
        """
        meta = _AGENT_IDENTITIES.get(agent_id, {"role": "agent", "clearance": "basic", "flag": "🤖"})

        if self._mock:
            return {
                "agent_id":       agent_id,
                "role":           meta["role"],
                "clearance":      meta["clearance"],
                "flag":           meta["flag"],
                "verified":       True,
                "attestation_id": _deterministic_id(agent_id, "identity"),
                "network":        _NETWORK,
                "mock":           True,
            }

        try:
            r = requests.get(
                f"{_BASE_URL}/identity/{agent_id}",
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            return {**data, "mock": False}
        except Exception as exc:
            logger.error("[myriad] get_identity %s: %s", agent_id, exc)
            return {**meta, "agent_id": agent_id, "verified": False, "error": str(exc)}

    def verify_agent(self, agent_id: str, wallet_address: str) -> dict:
        """
        Verify that a wallet address matches an agent's registered identity.
        REGIS calls this before dispatching any task.
        Returns { verified, trust_score, reason }.
        """
        if self._mock:
            known = agent_id in _AGENT_IDENTITIES
            return {
                "verified":    known,
                "agent_id":    agent_id,
                "trust_score": 0.95 if known else 0.0,
                "reason":      "Known SwarmPay agent" if known else "Unregistered agent",
                "mock":        True,
            }

        try:
            r = requests.post(
                f"{_BASE_URL}/identity/verify",
                json={"agentId": agent_id, "walletAddress": wallet_address},
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            return {**r.json(), "mock": False}
        except Exception as exc:
            logger.error("[myriad] verify %s: %s", agent_id, exc)
            return {"verified": False, "trust_score": 0.0, "error": str(exc)}

    # ── Attestations ───────────────────────────────────────────────────────

    def issue_attestation(
        self,
        issuer_agent: str,
        subject_agent: str,
        claim: str,
        evidence: Optional[dict] = None,
    ) -> dict:
        """
        Issue a verifiable credential: issuer attests a claim about subject.
        BISHOP issues compliance attestations after reviewing agent outputs.
        REGIS issues task-completion attestations.

        Example claims:
          "task_completed_successfully"
          "payment_policy_compliant"
          "output_verified_accurate"
        """
        attestation = {
            "issuer":    issuer_agent,
            "subject":   subject_agent,
            "claim":     claim,
            "evidence":  evidence or {},
            "timestamp": int(time.time()),
            "id":        _deterministic_id(f"{issuer_agent}:{subject_agent}:{claim}", "attest"),
        }

        if self._mock:
            logger.info("[myriad mock] attestation: %s → %s: %s", issuer_agent, subject_agent, claim)
            return {"success": True, "attestation": attestation, "mock": True}

        try:
            r = requests.post(
                f"{_BASE_URL}/attestations",
                json=attestation,
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            return {"success": True, "attestation": r.json(), "mock": False}
        except Exception as exc:
            logger.error("[myriad] issue_attestation: %s", exc)
            return {"success": False, "error": str(exc), "attestation": attestation}

    def get_attestations(
        self,
        agent_id: str,
        claim_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Retrieve attestations issued to or by an agent."""
        if self._mock:
            return []

        try:
            params: dict = {"limit": limit}
            if claim_type:
                params["claim"] = claim_type
            r = requests.get(
                f"{_BASE_URL}/attestations/{agent_id}",
                params=params,
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            return r.json().get("attestations", [])
        except Exception as exc:
            logger.error("[myriad] get_attestations: %s", exc)
            return []

    def get_trust_score(self, agent_id: str) -> float:
        """
        Aggregate trust score 0.0-1.0 based on attestation history.
        Higher score → agent can be dispatched higher-value tasks.
        """
        if self._mock:
            base = {"REGIS": 1.0, "BISHOP": 0.95, "ATLAS": 0.88, "CIPHER": 0.85, "SØN": 0.80, "FORGE": 0.65}
            return base.get(agent_id, 0.5)

        try:
            r = requests.get(
                f"{_BASE_URL}/trust/{agent_id}",
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            return float(r.json().get("score", 0.5))
        except Exception as exc:
            logger.error("[myriad] trust_score %s: %s", agent_id, exc)
            return 0.5

    def health_check(self) -> bool:
        if self._mock:
            return True
        try:
            r = requests.get(f"{_BASE_URL}/health", headers=self._headers(), timeout=4)
            return r.status_code == 200
        except Exception:
            return False

    # ── Internal ───────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {_API_KEY}",
            "Content-Type":  "application/json",
            "User-Agent":    "SwarmPay/2.0",
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _deterministic_id(seed: str, prefix: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


# Singleton
myriad_service = MyriadService()
