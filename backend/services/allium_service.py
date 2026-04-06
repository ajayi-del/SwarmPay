"""
Allium Service — On-chain blockchain analytics ("agents can SEE").

Allium provides SQL-queryable access to indexed blockchain data across
Solana, Ethereum, and 20+ chains. Used by agents to observe the world:
  • Wallet activity, token balances, DeFi positions
  • Transaction histories, anomaly detection
  • Protocol TVL, liquidity pool analytics

Fallback contract:
  • If ALLIUM_API_KEY not set: returns mock/cached data so agents degrade gracefully
  • All methods return structured dicts — callers never catch raw exceptions
  • Synchronous — call via asyncio.to_thread

Env vars:
  ALLIUM_API_KEY  — from app.allium.so
"""

import logging
import os
import time
from typing import Any, Optional

import requests

logger = logging.getLogger("swarmpay.allium")

_API_KEY = os.environ.get("ALLIUM_API_KEY", "").strip()
_BASE_URL = "https://api.allium.so/api/v1"
_TIMEOUT = 12


class AlliumService:
    """
    On-chain intelligence for sovereign agents.
    Agents call this to "see" the blockchain state before making decisions.
    """

    def __init__(self):
        self._mock = not bool(_API_KEY)
        if self._mock:
            logger.warning("[allium] ALLIUM_API_KEY not set — returning mock data")
        else:
            logger.info("[allium] initialized")

    # ── Wallet Intelligence ────────────────────────────────────────────────

    def get_wallet_summary(self, address: str, chain: str = "solana") -> dict:
        """
        Return a compact summary of a wallet: balance, recent txs, tokens held.
        Used by agents to assess counterparty standing before payments.
        """
        if self._mock:
            return _mock_wallet(address, chain)

        try:
            sql = f"""
                SELECT
                    address,
                    sol_balance,
                    tx_count_30d,
                    first_tx_date,
                    last_tx_date
                FROM solana.wallet_stats
                WHERE address = '{address}'
                LIMIT 1
            """
            rows = self._run_query(sql)
            return rows[0] if rows else {"address": address, "error": "not found"}
        except Exception as exc:
            logger.error("[allium] wallet_summary %s: %s", address, exc)
            return _mock_wallet(address, chain)

    def get_token_activity(
        self,
        token_mint: str,
        hours: int = 24,
        limit: int = 50,
    ) -> list[dict]:
        """
        Recent transfers for a token mint. Used to detect anomalous flows.
        """
        if self._mock:
            return _mock_token_activity(token_mint)

        try:
            sql = f"""
                SELECT
                    signature, block_time, from_address, to_address,
                    amount, usd_value
                FROM solana.token_transfers
                WHERE mint = '{token_mint}'
                  AND block_time > NOW() - INTERVAL '{hours} hours'
                ORDER BY block_time DESC
                LIMIT {limit}
            """
            return self._run_query(sql)
        except Exception as exc:
            logger.error("[allium] token_activity: %s", exc)
            return []

    def get_defi_tvl(self, protocol: str = "raydium", chain: str = "solana") -> dict:
        """
        Total Value Locked for a DeFi protocol. Used by CIPHER for yield analysis.
        """
        if self._mock:
            return _mock_defi_tvl(protocol)

        try:
            sql = f"""
                SELECT
                    protocol_name,
                    tvl_usd,
                    tvl_7d_change_pct,
                    top_pool,
                    updated_at
                FROM {chain}.defi_protocols
                WHERE protocol_name ILIKE '%{protocol}%'
                ORDER BY tvl_usd DESC
                LIMIT 1
            """
            rows = self._run_query(sql)
            return rows[0] if rows else {"protocol": protocol, "tvl_usd": 0}
        except Exception as exc:
            logger.error("[allium] defi_tvl: %s", exc)
            return _mock_defi_tvl(protocol)

    def detect_anomalies(self, address: str, threshold_usd: float = 10_000) -> list[dict]:
        """
        Flag unusual transaction patterns for compliance review.
        BISHOP calls this for AML/risk screening.
        """
        if self._mock:
            return _mock_anomalies(address)

        try:
            sql = f"""
                SELECT
                    signature, block_time, amount_usd,
                    from_address, to_address, anomaly_type
                FROM solana.anomaly_flags
                WHERE (from_address = '{address}' OR to_address = '{address}')
                  AND amount_usd > {threshold_usd}
                  AND block_time > NOW() - INTERVAL '7 days'
                ORDER BY block_time DESC
                LIMIT 20
            """
            return self._run_query(sql)
        except Exception as exc:
            logger.error("[allium] anomalies: %s", exc)
            return []

    def run_custom_query(self, sql: str) -> list[dict]:
        """
        Execute arbitrary SQL against Allium's indexed blockchain data.
        Power-user escape hatch for ATLAS research tasks.
        """
        if self._mock:
            logger.info("[allium mock] custom query: %s…", sql[:60])
            return []
        return self._run_query(sql)

    # ── Internal ───────────────────────────────────────────────────────────

    def _run_query(self, sql: str) -> list[dict]:
        """POST to Allium SQL API, return rows as list of dicts."""
        r = requests.post(
            f"{_BASE_URL}/explorer/query",
            json={"sql": sql},
            headers={
                "Authorization": f"Bearer {_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", data.get("rows", []))

    def health_check(self) -> bool:
        if self._mock:
            return True
        try:
            r = requests.get(
                f"{_BASE_URL}/health",
                headers={"Authorization": f"Bearer {_API_KEY}"},
                timeout=4,
            )
            return r.status_code == 200
        except Exception:
            return False


# ── Mock data (used when ALLIUM_API_KEY absent) ────────────────────────────────

def _mock_wallet(address: str, chain: str) -> dict:
    return {
        "address": address,
        "chain": chain,
        "sol_balance": 1.234,
        "tx_count_30d": 47,
        "first_tx_date": "2024-01-15",
        "last_tx_date": "2025-04-05",
        "mock": True,
    }


def _mock_token_activity(mint: str) -> list[dict]:
    return [
        {
            "signature": f"mock_sig_{mint[:8]}_1",
            "block_time": "2025-04-05T10:00:00Z",
            "from_address": "mock_from_1",
            "to_address": "mock_to_1",
            "amount": 1000.0,
            "usd_value": 1000.0,
            "mock": True,
        }
    ]


def _mock_defi_tvl(protocol: str) -> dict:
    tvls = {
        "raydium": 650_000_000,
        "orca": 420_000_000,
        "jupiter": 1_200_000_000,
    }
    return {
        "protocol_name": protocol,
        "tvl_usd": tvls.get(protocol.lower(), 100_000_000),
        "tvl_7d_change_pct": 3.2,
        "top_pool": f"{protocol.upper()}/SOL",
        "mock": True,
    }


def _mock_anomalies(address: str) -> list[dict]:
    return []  # Clean by default in mock mode


# Singleton
allium_service = AlliumService()
