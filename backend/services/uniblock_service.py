"""
Uniblock Service — Multi-chain transaction routing ("agents can TRANSACT").

Uniblock provides a unified API for executing and simulating transactions
across 30+ blockchains including Solana, Ethereum, and EVM chains.
Agents use this for:
  • Pre-flight transaction simulation (no gas wasted on failures)
  • Optimal routing (cheapest path across chains)
  • Transaction status tracking
  • Gas estimation with live prices

Fallback contract:
  • If UNIBLOCK_API_KEY not set: returns mock simulation results
  • All methods return structured dicts — never raw exceptions
  • Synchronous — call via asyncio.to_thread

Env vars:
  UNIBLOCK_API_KEY  — from uniblock.dev/dashboard
  UNIBLOCK_CHAIN    — default chain (default: "solana")
"""

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger("swarmpay.uniblock")

_API_KEY  = os.environ.get("UNIBLOCK_API_KEY", "").strip()
_BASE_URL = "https://api.uniblock.dev"
_CHAIN    = os.environ.get("UNIBLOCK_CHAIN", "solana")
_TIMEOUT  = 10


class UniblockService:
    """
    Multi-chain transaction infrastructure for sovereign agents.
    Agents use this to simulate, route, and verify transactions
    before committing on-chain.
    """

    def __init__(self):
        self._mock = not bool(_API_KEY)
        if self._mock:
            logger.warning("[uniblock] UNIBLOCK_API_KEY not set — mock mode")
        else:
            logger.info("[uniblock] initialized, default chain=%s", _CHAIN)

    # ── Transaction Lifecycle ──────────────────────────────────────────────

    def simulate_transfer(
        self,
        from_address: str,
        to_address: str,
        amount_sol: float,
        chain: str = _CHAIN,
    ) -> dict:
        """
        Simulate a transfer before executing.
        Returns { success, estimated_fee_sol, will_succeed, simulation_id }.
        Agents call this before every payment to catch failures early.
        """
        if self._mock:
            return _mock_simulation(from_address, to_address, amount_sol)

        try:
            r = requests.post(
                f"{_BASE_URL}/v1/transaction/simulate",
                json={
                    "chain":       chain,
                    "fromAddress": from_address,
                    "toAddress":   to_address,
                    "amount":      str(int(amount_sol * 1e9)),  # lamports
                    "token":       "SOL",
                },
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            return {
                "success":           True,
                "will_succeed":      data.get("success", True),
                "estimated_fee_sol": data.get("fee", 0.000005),
                "simulation_id":     data.get("simulationId", ""),
                "logs":              data.get("logs", []),
                "mock":              False,
            }
        except Exception as exc:
            logger.error("[uniblock] simulate: %s", exc)
            return _mock_simulation(from_address, to_address, amount_sol)

    def get_optimal_route(
        self,
        from_chain: str,
        to_chain: str,
        token: str,
        amount: float,
    ) -> dict:
        """
        Find cheapest/fastest route for a cross-chain transfer.
        Used by SØN for bridge operations and fund routing.
        """
        if self._mock:
            return {
                "route":        [from_chain, to_chain],
                "estimated_fee": 0.001,
                "estimated_time_secs": 30,
                "provider":     "mock_bridge",
                "mock":         True,
            }

        try:
            r = requests.post(
                f"{_BASE_URL}/v1/bridge/route",
                json={
                    "fromChain": from_chain,
                    "toChain":   to_chain,
                    "token":     token,
                    "amount":    amount,
                },
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.error("[uniblock] route: %s", exc)
            return {"error": str(exc), "mock": False}

    def get_transaction_status(self, tx_hash: str, chain: str = _CHAIN) -> dict:
        """
        Poll transaction confirmation status.
        Returns { confirmed, block_number, timestamp, error }.
        """
        if self._mock:
            return {
                "confirmed":    True,
                "block_number": 320_000_000,
                "timestamp":    int(time.time()),
                "finalized":    True,
                "mock":         True,
            }

        try:
            r = requests.get(
                f"{_BASE_URL}/v1/transaction/{tx_hash}",
                params={"chain": chain},
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            return {
                "confirmed":    data.get("status") in ("confirmed", "finalized"),
                "block_number": data.get("slot"),
                "timestamp":    data.get("blockTime"),
                "finalized":    data.get("status") == "finalized",
                "mock":         False,
            }
        except Exception as exc:
            logger.error("[uniblock] tx_status: %s", exc)
            return {"confirmed": False, "error": str(exc)}

    def estimate_gas(
        self,
        from_address: str,
        to_address: str,
        chain: str = _CHAIN,
    ) -> dict:
        """
        Estimate transaction fee in native token.
        Returns { fee_native, fee_usd, priority }.
        """
        if self._mock:
            return {"fee_native": 0.000005, "fee_usd": 0.0004, "priority": "medium", "mock": True}

        try:
            r = requests.post(
                f"{_BASE_URL}/v1/gas/estimate",
                json={"chain": chain, "fromAddress": from_address, "toAddress": to_address},
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.error("[uniblock] gas_estimate: %s", exc)
            return {"fee_native": 0.000005, "fee_usd": 0.0004, "priority": "medium"}

    def get_token_balance(self, address: str, token: str = "SOL", chain: str = _CHAIN) -> float:
        """Return token balance for an address. Used by agents before spending."""
        if self._mock:
            return 10.0  # Mock 10 SOL

        try:
            r = requests.get(
                f"{_BASE_URL}/v1/balance/{address}",
                params={"chain": chain, "token": token},
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            return float(data.get("balance", 0))
        except Exception as exc:
            logger.error("[uniblock] balance: %s", exc)
            return 0.0

    def health_check(self) -> bool:
        if self._mock:
            return True
        try:
            r = requests.get(f"{_BASE_URL}/v1/health", headers=self._headers(), timeout=4)
            return r.status_code == 200
        except Exception:
            return False

    # ── Internal ───────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "X-API-Key":     _API_KEY,
            "Content-Type":  "application/json",
            "User-Agent":    "SwarmPay/2.0",
        }


# ── Mock helpers ───────────────────────────────────────────────────────────────

def _mock_simulation(from_addr: str, to_addr: str, amount: float) -> dict:
    return {
        "success":           True,
        "will_succeed":      True,
        "estimated_fee_sol": 0.000005,
        "simulation_id":     f"mock_sim_{int(time.time())}",
        "logs":              [f"Transfer {amount} SOL: {from_addr[:8]}→{to_addr[:8]}"],
        "mock":              True,
    }


# Singleton
uniblock_service = UniblockService()
