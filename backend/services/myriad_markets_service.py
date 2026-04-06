"""
Myriad Markets Service — Autonomous prediction markets for agent intelligence.

Agents bet on each other's yield predictions giving them real skin in the game.
CIPHER creates markets, ATLAS + SØN take positions.

API docs: https://api.myriad.markets/v1
Get key: myriad.markets → Developer → API Keys

Graceful fallback: no MYRIAD_API_KEY → mock mode.
Mock markets are stored in memory, never crash the system,
and are returned by the /integrations/myriad/markets endpoint.

Env vars:
  MYRIAD_API_KEY   — from myriad.markets dashboard
"""

import httpx
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("swarmpay.myriad_markets")

MYRIAD_API_KEY = os.environ.get("MYRIAD_API_KEY", "").strip()
_BASE_URL      = "https://api.myriad.markets/v1"

# In-memory market registry — shared across module lifetime
# {market_id: {id, question, resolution_date, status, bets: []}}
_markets: dict[str, dict] = {}


# ── Public API ─────────────────────────────────────────────────────────────────

async def create_yield_market(
    question: str,
    resolution_date: str,
    initial_liquidity: float = 0.001,
) -> Optional[dict]:
    """
    CIPHER creates a prediction market on a yield opportunity.
    Returns market dict with 'id' key on success, None on failure.
    """
    if not MYRIAD_API_KEY:
        return _mock_create(question, resolution_date, initial_liquidity)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{_BASE_URL}/markets",
                headers=_headers(),
                json={
                    "question":           question,
                    "description":        f"SwarmPay CIPHER agent prediction. {_now()}",
                    "resolution_date":    resolution_date,
                    "initial_liquidity":  initial_liquidity,
                    "category":           "crypto",
                },
            )
            if r.status_code == 201:
                data = r.json()
                _markets[data["id"]] = {**data, "bets": [], "mock": False}
                return data
            logger.warning("[myriad] create_market %d: %s", r.status_code, r.text[:120])
            # Fall through to mock on API failure
    except Exception as exc:
        logger.warning("[myriad] create_market: %s", exc)

    return _mock_create(question, resolution_date, initial_liquidity)


async def place_agent_bet(
    market_id: str,
    agent_name: str,
    outcome: str,        # "YES" or "NO"
    amount_sol: float = 0.0001,
) -> Optional[dict]:
    """Agent stakes SOL on a prediction outcome."""
    bet = {
        "agent":      agent_name,
        "outcome":    outcome,
        "amount_sol": amount_sol,
        "placed_at":  _now(),
    }

    # Always update local registry regardless of live/mock
    if market_id in _markets:
        _markets[market_id].setdefault("bets", []).append(bet)

    if not MYRIAD_API_KEY:
        logger.info("[myriad mock] %s bet %s on %s (◎%.5f)", agent_name, outcome, market_id, amount_sol)
        return {**bet, "mock": True}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{_BASE_URL}/markets/{market_id}/bets",
                headers=_headers(),
                json={"outcome": outcome, "amount": amount_sol, "agent": agent_name},
            )
            if r.status_code == 201:
                return {**r.json(), "mock": False}
            logger.warning("[myriad] place_bet %d", r.status_code)
    except Exception as exc:
        logger.warning("[myriad] place_bet: %s", exc)

    return {**bet, "mock": True}


async def get_market(market_id: str) -> Optional[dict]:
    """Fetch current status and bets for a market."""
    if not MYRIAD_API_KEY:
        return _markets.get(market_id)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{_BASE_URL}/markets/{market_id}",
                headers=_headers(),
            )
            if r.status_code == 200:
                data = r.json()
                # Merge local bets if live API doesn't return them
                if "bets" not in data and market_id in _markets:
                    data["bets"] = _markets[market_id].get("bets", [])
                return data
            return _markets.get(market_id)
    except Exception as exc:
        logger.warning("[myriad] get_market: %s", exc)
        return _markets.get(market_id)


def get_active_markets() -> list[dict]:
    """Return all known active markets (local registry)."""
    return [m for m in _markets.values() if m.get("status") == "open"]


def is_available() -> bool:
    return bool(MYRIAD_API_KEY)


# ── Internal helpers ────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {MYRIAD_API_KEY}",
        "Content-Type":  "application/json",
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mock_create(question: str, resolution_date: str, initial_liquidity: float) -> dict:
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%H%M%S%f")[:10]
    market_id = f"mock_{ts}"
    market = {
        "id":               market_id,
        "question":         question,
        "resolution_date":  resolution_date,
        "initial_liquidity": initial_liquidity,
        "status":           "open",
        "created_at":       _now(),
        "bets":             [],
        "mock":             True,
    }
    _markets[market_id] = market
    logger.info("[myriad mock] market created: %s", market_id)
    return market
