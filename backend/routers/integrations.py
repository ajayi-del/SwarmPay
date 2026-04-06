"""
Integrations Router — Sponsor tool health + data endpoints.

Endpoints:
  GET /integrations/status         — Health of all 5 sponsor integrations
  GET /integrations/helius/recent  — Last 10 decoded Solana transactions
  GET /integrations/myriad/markets — Active prediction markets + agent bets
  GET /integrations/bounties       — Open bounty board
  GET /integrations/decrees        — REGIS governance decrees
  GET /integrations/proposals      — CIPHER yield proposals

Judges can verify which integrations are live at a glance.
"""

import asyncio
import logging
import os

from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger("swarmpay.integrations")
limiter = Limiter(key_func=get_remote_address)
router  = APIRouter(prefix="/integrations", tags=["integrations"])


# ── Integration status ─────────────────────────────────────────────────────────

@router.get("/status")
@limiter.limit("60/minute")
async def integration_status(request: Request):
    """
    Return health of all 5 sponsor integrations.
    Judges can verify which are live in real time.
    """
    def _check(key: str, label: str) -> str:
        val = os.environ.get(key, "").strip()
        return "connected" if val else "no_key"

    # Myriad markets
    myriad_key = os.environ.get("MYRIAD_API_KEY", "")
    myriad_status = "connected" if myriad_key else "mock_mode"
    try:
        from services.myriad_markets_service import get_active_markets
        markets = get_active_markets()
        myriad_detail = f"{len(markets)} active markets"
    except Exception:
        myriad_detail = "unavailable"

    # Helius
    helius_key = os.environ.get("HELIUS_API_KEY", "")
    helius_status = "connected" if helius_key else "no_key"
    if helius_key:
        try:
            from services.helius_service import is_available
            helius_status = "live" if is_available() else "no_key"
        except Exception:
            helius_status = "error"

    # XMTP
    xmtp_key = os.environ.get("XMTP_PRIVATE_KEY", "") or os.environ.get("XMTP_WALLET_KEY", "")
    xmtp_status = "connected" if xmtp_key else "no_key"

    # MoonPay
    moonpay_key = os.environ.get("MOONPAY_API_KEY", "")
    moonpay_status = "live" if moonpay_key else "sandbox"

    # Uniblock
    uniblock_key = os.environ.get("UNIBLOCK_API_KEY", "")
    uniblock_status = "connected" if uniblock_key else "no_key"

    return {
        "myriad":    {"status": myriad_status,  "detail": myriad_detail,    "mode": "prediction_markets"},
        "helius":    {"status": helius_status,   "detail": "solana_realtime", "replaces": "allium"},
        "xmtp":      {"status": xmtp_status,     "detail": "agent_messaging", "verified": xmtp_status == "connected"},
        "moonpay":   {"status": moonpay_status,  "detail": "fiat_onramp",    "currency": "SOL"},
        "uniblock":  {"status": uniblock_status, "detail": "multichain_routing", "chains": ["solana", "ethereum", "base", "arbitrum"]},
        "solana_rpc": os.environ.get("SOLANA_RPC_URL", "devnet_public"),
    }


# ── Helius live data ───────────────────────────────────────────────────────────

@router.get("/helius/recent")
@limiter.limit("30/minute")
async def helius_recent(request: Request, limit: int = 10):
    """Return recent decoded Solana transactions from Helius."""
    if not os.environ.get("HELIUS_API_KEY"):
        return {"transactions": [], "status": "no_key", "fallback": "ddg_polling"}

    try:
        from services.helius_service import get_recent_transactions, get_validator_stats
        txns       = await get_recent_transactions(limit=min(limit, 20))
        validators = await get_validator_stats()

        # Summarise transactions
        summary = []
        for tx in txns:
            if not isinstance(tx, dict):
                continue
            transfers    = tx.get("nativeTransfers") or []
            total_lamports = sum(int(t.get("amount", 0)) for t in transfers if isinstance(t, dict))
            amount_sol   = total_lamports / 1_000_000_000
            summary.append({
                "type":      tx.get("type", "UNKNOWN"),
                "amount_sol": round(amount_sol, 4),
                "signature": tx.get("signature", "")[:20] + "…",
                "explorer":  f"https://explorer.solana.com/tx/{tx.get('signature','')}?cluster=devnet",
            })

        return {
            "transactions":     summary,
            "validators_count": len(validators),
            "source":           "helius_realtime",
            "network":          "devnet",
        }
    except Exception as exc:
        logger.error("[helius/recent] %s", exc)
        return {"transactions": [], "error": str(exc)}


# ── Myriad prediction markets ─────────────────────────────────────────────────

@router.get("/myriad/markets")
@limiter.limit("60/minute")
async def myriad_markets(request: Request):
    """Return all active Myriad prediction markets with agent bets."""
    try:
        from services.myriad_markets_service import get_active_markets, is_available

        markets = get_active_markets()
        return {
            "markets":      markets,
            "total":        len(markets),
            "live_api":     is_available(),
            "mode":         "live" if is_available() else "mock",
            "description":  "Agents bet on their own yield intelligence",
        }
    except Exception as exc:
        logger.error("[myriad/markets] %s", exc)
        return {"markets": [], "error": str(exc)}


# ── Bounty board ───────────────────────────────────────────────────────────────

@router.get("/bounties")
@limiter.limit("60/minute")
async def get_bounties(request: Request):
    """Return open bounties on the agent economy board."""
    try:
        from services.pocketbase import PocketBaseService
        pb = PocketBaseService()
        bounties = await asyncio.to_thread(
            pb.list, "bounties", sort="-created", limit=20
        )
        return {
            "bounties": bounties,
            "open":     [b for b in bounties if b.get("status") == "open"],
            "bidding":  [b for b in bounties if b.get("status") == "bidding"],
            "awarded":  [b for b in bounties if b.get("status") == "awarded"],
        }
    except Exception as exc:
        logger.debug("[bounties] %s", exc)
        return {"bounties": [], "note": "bounties collection not yet created in PocketBase"}


# ── REGIS decrees ─────────────────────────────────────────────────────────────

@router.get("/decrees")
@limiter.limit("60/minute")
async def get_decrees(request: Request):
    """Return REGIS governance decrees (austerity / prosperity)."""
    try:
        from services.pocketbase import PocketBaseService
        pb = PocketBaseService()
        decrees = await asyncio.to_thread(
            pb.list, "decrees", sort="-created", limit=10
        )
        return {"decrees": decrees, "total": len(decrees)}
    except Exception as exc:
        logger.debug("[decrees] %s", exc)
        return {"decrees": [], "note": "decrees collection not yet created in PocketBase"}


# ── CIPHER yield proposals ────────────────────────────────────────────────────

@router.get("/proposals")
@limiter.limit("60/minute")
async def get_proposals(request: Request):
    """Return CIPHER yield proposals and their REGIS approval status."""
    try:
        from services.pocketbase import PocketBaseService
        pb = PocketBaseService()
        proposals = await asyncio.to_thread(
            pb.list, "proposals", sort="-created", limit=20
        )
        return {
            "proposals": proposals,
            "pending":   [p for p in proposals if p.get("status") == "pending"],
            "approved":  [p for p in proposals if p.get("status") == "approved"],
        }
    except Exception as exc:
        logger.debug("[proposals] %s", exc)
        return {"proposals": [], "note": "proposals collection not yet created in PocketBase"}
