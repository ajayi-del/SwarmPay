"""
Moonpay Service — Fiat-to-SOL onramp widget URL generator.

Returns a pre-filled Moonpay Buy widget URL for a given Solana wallet address.
No API key required for URL generation — Moonpay handles auth client-side.
"""

import urllib.parse

_MOONPAY_BASE = "https://buy.moonpay.com"
_PARTNER_CODE = "swarm_pay_demo"  # demo partner code


def get_onramp_url(
    wallet_address: str,
    currency: str = "sol",
    fiat: str = "usd",
    amount: float = 20.0,
) -> str:
    """
    Return a Moonpay Buy widget URL pre-filled with wallet + amount.
    In production, sign this URL with your Moonpay secret key.
    """
    params = {
        "apiKey": "pk_test_demo",       # Moonpay public test key placeholder
        "currencyCode": currency,
        "walletAddress": wallet_address,
        "baseCurrencyCode": fiat,
        "baseCurrencyAmount": str(amount),
        "colorCode": "%23a78bfa",        # SwarmPay violet
        "redirectURL": "https://swarm.pay/funded",
        "externalTransactionId": f"swarm_{wallet_address[:8]}",
    }
    return f"{_MOONPAY_BASE}?{urllib.parse.urlencode(params)}"


def get_onramp_info(wallet_address: str) -> dict:
    """Return onramp metadata for the CoordinatorCard widget."""
    url = get_onramp_url(wallet_address)
    return {
        "url": url,
        "currency": "SOL",
        "fiat": "USD",
        "suggested_amount": 20.0,
        "note": "Powered by Moonpay — fiat → SOL in <5 min",
        "wallet": wallet_address,
    }
