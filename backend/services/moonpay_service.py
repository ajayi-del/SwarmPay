"""
Moonpay Service — Fiat-to-SOL onramp widget URL generator.

Sandbox: uses buy-sandbox.moonpay.com (no API key required to open the page).
Production: set MOONPAY_API_KEY env var to your Moonpay publishable key.

To get a real key: https://dashboard.moonpay.com → Create Account → API Keys
"""

import os
import urllib.parse

MOONPAY_API_KEY = os.environ.get("MOONPAY_API_KEY", "")

# Sandbox works without a real key — shows the full widget UI in test mode
_MOONPAY_SANDBOX = "https://buy-sandbox.moonpay.com"
_MOONPAY_SANDBOX = "https://buy-sandbox.moonpay.com"
_MOONPAY_LIVE    = "https://buy.moonpay.com"

import asyncio
import httpx
import time
import logging

logger = logging.getLogger("swarmpay.moonpay")

_RATE_CACHE: dict = {"rate": None, "ts": 0.0}
_RATE_LOCK = asyncio.Lock()
_RATE_TTL = 30  # seconds

async def get_live_sol_usdc_rate() -> float:
    """Live SOL/USD rate from MoonPay pricing API. 30s TTL cache."""
    async with _RATE_LOCK:
        if time.time() - _RATE_CACHE["ts"] < _RATE_TTL and _RATE_CACHE["rate"]:
            return _RATE_CACHE["rate"]
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    "https://api.moonpay.com/v3/currencies/sol/ask_price",
                    params={"apiKey": MOONPAY_API_KEY or "pk_test_key"},
                    timeout=5.0
                )
                r.raise_for_status()
                rate = float(r.json()["USD"])
                _RATE_CACHE.update({"rate": rate, "ts": time.time()})
                return rate
        except Exception as e:
            logger.warning("MoonPay rate failed: %s — trying Meteora", e)
            try:
                from services.meteora_service import get_sol_usdc_rate
                rate_data = await asyncio.to_thread(get_sol_usdc_rate)
                if rate_data and rate_data.get("rate"):
                    rate = float(rate_data["rate"])
                    _RATE_CACHE.update({"rate": rate, "ts": time.time()})
                    return rate
            except Exception as e2:
                logger.warning("Meteora rate failed: %s", e2)
            
            # Absolute fallback
            return 79.0


def get_onramp_url(
    wallet_address: str,
    currency: str = "sol",
    fiat: str = "usd",
    amount: float = 20.0,
) -> str:
    """
    Return a Moonpay Buy widget URL pre-filled with wallet + amount.

    - If MOONPAY_API_KEY is set → uses live endpoint with real key
    - Otherwise → uses sandbox endpoint (test mode, no real funds)
    """
    if MOONPAY_API_KEY:
        base = _MOONPAY_LIVE
        api_key = MOONPAY_API_KEY
    else:
        base = _MOONPAY_SANDBOX
        api_key = "pk_test_key"   # Moonpay sandbox accepts any pk_test_* value

    params = {
        "apiKey": api_key,
        "currencyCode": currency,
        "walletAddress": wallet_address,
        "baseCurrencyCode": fiat,
        "baseCurrencyAmount": str(amount),
        "colorCode": "#a78bfa",
        "redirectURL": "https://swarm.pay/funded",
        "externalTransactionId": f"swarm_{wallet_address[:8]}",
    }
    return f"{base}?{urllib.parse.urlencode(params)}"


def get_onramp_info(wallet_address: str) -> dict:
    """Return onramp metadata for the CoordinatorCard widget."""
    url = get_onramp_url(wallet_address)
    is_live = bool(MOONPAY_API_KEY)
    return {
        "url": url,
        "currency": "SOL",
        "fiat": "USD",
        "suggested_amount": 20.0,
        "mode": "live" if is_live else "sandbox",
        "note": "Powered by Moonpay — fiat → SOL in <5 min" if is_live
                else "Moonpay sandbox mode — set MOONPAY_API_KEY for live onramp",
        "wallet": wallet_address,
    }
