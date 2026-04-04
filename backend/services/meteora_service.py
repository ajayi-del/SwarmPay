"""
Meteora Service — Fetch SOL/USDC pool rate from Meteora DLMM API.

Primary:  https://dlmm-api.meteora.ag (Meteora DLMM pairs)
Fallback: https://price.jup.ag/v6   (Jupiter aggregator — includes Meteora pools)

One function, one call. Non-blocking. Returns None on failure.
"""

import time
from typing import Optional

import httpx

_METEORA_DLMM = "https://dlmm-api.meteora.ag/pair/all_with_pagination"
_JUPITER_PRICE = "https://price.jup.ag/v6/price"

# Solana mainnet mint addresses
_SOL_MINT  = "So11111111111111111111111111111111111111112"
_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

_CACHE: dict = {}  # Simple TTL cache: {rate, ts, source}
_CACHE_TTL = 60    # seconds


def get_sol_usdc_rate() -> Optional[dict]:
    """
    Return {rate, source, pair_name, tvl} or None.
    Cached for 60 s to avoid hammering the API.
    """
    now = time.time()
    if _CACHE and (now - _CACHE.get("ts", 0)) < _CACHE_TTL:
        return dict(_CACHE)

    # ── Primary: Meteora DLMM ──────────────────────────────────────────────────
    try:
        client = httpx.Client(timeout=8.0)
        resp = client.get(
            _METEORA_DLMM,
            params={
                "page": 0,
                "limit": 20,
                "sort_key": "tvl",
                "order_by": "desc",
                "search_term": "SOL-USDC",
            },
        )
        if resp.is_success:
            raw = resp.json()
            # Response can be list or {"data": [...], "total": N}
            pairs = raw if isinstance(raw, list) else raw.get("data", [])
            # Find SOL-USDC pair with highest TVL
            for pair in pairs:
                name = pair.get("name", "")
                if ("SOL" in name and "USDC" in name and
                        "USDT" not in name and "mSOL" not in name and "bSOL" not in name):
                    price = (
                        pair.get("current_price") or
                        pair.get("price") or
                        pair.get("fee_apr")   # fallback fields
                    )
                    tvl = float(pair.get("tvl", 0))
                    if price and float(price) > 10:   # sanity: SOL > $10
                        result = {
                            "rate":      round(float(price), 2),
                            "source":    "Meteora DLMM",
                            "pair_name": name,
                            "tvl":       tvl,
                            "ts":        now,
                        }
                        _CACHE.update(result)
                        return result
    except Exception as e:
        print(f"[meteora primary] {e}")

    # ── Fallback: Jupiter price API ────────────────────────────────────────────
    try:
        client = httpx.Client(timeout=6.0)
        resp = client.get(
            _JUPITER_PRICE,
            params={"ids": _SOL_MINT, "vsToken": _USDC_MINT},
        )
        if resp.is_success:
            data = resp.json().get("data", {})
            sol = data.get(_SOL_MINT) or next(iter(data.values()), None)
            if sol and sol.get("price"):
                result = {
                    "rate":      round(float(sol["price"]), 2),
                    "source":    "Jupiter (Meteora pools)",
                    "pair_name": "SOL/USDC",
                    "tvl":       0,
                    "ts":        now,
                }
                _CACHE.update(result)
                return result
    except Exception as e:
        print(f"[meteora fallback] {e}")

    return None
