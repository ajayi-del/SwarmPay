"""
Helius Service — Real-time Solana on-chain intelligence for ATLAS.

Replaces Allium as the primary Solana data source.
Uses Helius decoded transaction API + RPC for validator stats.

API key from: https://dev.helius.xyz/dashboard
Docs: https://docs.helius.dev/

Graceful fallback: if HELIUS_API_KEY not set, returns empty lists.
ATLAS falls back to DuckDuckGo automatically.

Env vars:
  HELIUS_API_KEY   — from Helius dashboard
  SOLANA_RPC_URL   — override RPC endpoint (defaults to Helius devnet)
"""

import httpx
import logging
import os
from typing import Optional

logger = logging.getLogger("swarmpay.helius")

HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY", "").strip()
_HELIUS_BASE   = f"https://api-devnet.helius-rpc.com/v0"
_HELIUS_RPC    = f"https://devnet.helius-rpc.com/?api-key={HELIUS_API_KEY}" if HELIUS_API_KEY else ""


async def get_recent_transactions(limit: int = 10) -> list[dict]:
    """
    Fetch recent decoded Solana transactions (SWAP type).
    ATLAS uses this for real-time on-chain intelligence.
    Returns [] if API key missing or request fails.
    """
    if not HELIUS_API_KEY:
        return []

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                f"{_HELIUS_BASE}/transactions/",
                params={"api-key": HELIUS_API_KEY, "limit": limit, "type": "SWAP"},
            )
            if r.status_code == 200:
                data = r.json()
                return data if isinstance(data, list) else []
            logger.debug("[helius] transactions %d", r.status_code)
            return []
    except Exception as exc:
        logger.warning("[helius] transactions: %s", exc)
        return []


async def get_validator_stats() -> list[dict]:
    """
    Fetch Solana validator performance via Helius RPC.
    ATLAS uses this for staking research tasks.
    """
    if not HELIUS_API_KEY:
        return []

    rpc = _HELIUS_RPC
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.post(
                rpc,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getVoteAccounts",
                    "params": [{"limit": 10}],
                },
            )
            if r.status_code == 200:
                return r.json().get("result", {}).get("current", [])[:10]
            return []
    except Exception as exc:
        logger.warning("[helius] validators: %s", exc)
        return []


async def get_token_metadata(mint_address: str) -> Optional[dict]:
    """Get decoded metadata for a Solana token mint."""
    if not HELIUS_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{_HELIUS_BASE}/token-metadata",
                params={"api-key": HELIUS_API_KEY, "mintAccounts[]": mint_address},
            )
            if r.status_code == 200:
                data = r.json()
                return data[0] if data else None
            return None
    except Exception as exc:
        logger.warning("[helius] metadata: %s", exc)
        return None


async def atlas_helius_scan() -> dict:
    """
    ATLAS real-time intelligence via Helius decoded transactions.
    Returns {findings, source, real_data, findings_count}.

    Significant events (>50 SOL) are surfaced as 'notable'.
    Major events (>500 SOL) are surfaced as 'major'.
    """
    findings = []

    # ── Recent large swaps ────────────────────────────────────────────────
    try:
        txns = await get_recent_transactions(limit=8)
        for tx in txns:
            if not isinstance(tx, dict):
                continue

            # Sum native transfer amounts (lamports → SOL)
            transfers = tx.get("nativeTransfers") or []
            total_lamports = sum(
                int(t.get("amount", 0)) for t in transfers if isinstance(t, dict)
            )
            amount_sol = total_lamports / 1_000_000_000

            if amount_sol < 50:
                continue

            sig = tx.get("signature", "")
            findings.append({
                "title":       f"Large {tx.get('type', 'SWAP')}: ◎{amount_sol:.1f} SOL",
                "type":        tx.get("type", "SWAP"),
                "signature":   sig[:20],
                "significance": "major" if amount_sol > 500 else "notable",
                "source":      "helius_realtime",
                "explorer":    f"https://explorer.solana.com/tx/{sig}?cluster=devnet",
            })
    except Exception as exc:
        logger.warning("[helius atlas_scan] txns: %s", exc)

    # ── Validator network health ──────────────────────────────────────────
    try:
        validators = await get_validator_stats()
        if validators:
            findings.append({
                "title":       f"Validator network: {len(validators)} active validators",
                "type":        "NETWORK_HEALTH",
                "significance": "minor",
                "source":      "helius_rpc",
            })
    except Exception as exc:
        logger.warning("[helius atlas_scan] validators: %s", exc)

    return {
        "findings":       findings,
        "source":         "helius",
        "real_data":      True,
        "findings_count": len(findings),
    }


def is_available() -> bool:
    """Return True if Helius API key is configured."""
    return bool(HELIUS_API_KEY)
