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
_MOONPAY_LIVE    = "https://buy.moonpay.com"


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
