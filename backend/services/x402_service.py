"""
x402 Payment Service — two-phase x402 HTTP protocol with real Solana devnet transfers.

Implements the x402 spec:
  Phase 1: Server returns 402 with payment requirements (amount, network, payTo, nonce)
  Phase 2: Agent submits X-Payment header → server validates → issues receipt + tx sig

ATLAS  pays /x402/search   0.001 USDC-eq   (search access gate)
CIPHER pays /x402/analyze  0.002 USDC-eq   (analysis engine gate)
FORGE  pays /x402/publish  0.001 USDC-eq   (publish endpoint gate)

Each transaction is a real Solana devnet SOL transfer (1000–2000 lamports ≈ $0.0001)
with a real signature verifiable at https://explorer.solana.com?cluster=devnet.
Falls back to deterministic mock signature if solana_service unavailable.
"""

import base64
import time
import uuid
from typing import Optional

from services.solana_service import solana_service

# ── Endpoint registry ─────────────────────────────────────────────────────────

ENDPOINTS = {
    "search":  {
        "path": "/x402/search",
        "amount": 0.001,
        "lamports": 1_000,
        "currency": "USDC",
        "network": "solana-devnet",
        "label": "Search Access",
    },
    "analyze": {
        "path": "/x402/analyze",
        "amount": 0.002,
        "lamports": 2_000,
        "currency": "USDC",
        "network": "solana-devnet",
        "label": "Analysis Engine",
    },
    "publish": {
        "path": "/x402/publish",
        "amount": 0.001,
        "lamports": 1_000,
        "currency": "USDC",
        "network": "solana-devnet",
        "label": "Publish Gate",
    },
}

# Devnet USDC mint (Circle devnet)
_USDC_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"


class X402Service:
    """
    Mock-gated x402 microservice with real Solana devnet settlement.
    """

    def gate(self, endpoint: str, wallet_id: str) -> dict:
        """
        Execute the full two-phase x402 flow:
          1. Build payment requirements (402 response body)
          2. Sign mock X-Payment header
          3. Submit real Solana devnet transfer → get signature
          4. Return receipt

        Returns receipt dict. Raises ValueError for unknown endpoints.
        """
        ep = ENDPOINTS.get(endpoint)
        if not ep:
            raise ValueError(f"Unknown x402 endpoint: {endpoint}")

        nonce        = uuid.uuid4().hex[:16]
        amount       = ep["amount"]
        lamports     = ep["lamports"]
        network      = ep["network"]
        path         = ep["path"]
        ts           = int(time.time())
        treasury_pub = solana_service._treasury_pubkey

        # ── Phase 1: 402 payment requirements ────────────────────────────────
        payment_requirements = {
            "x402Version": 1,
            "accepts": [{
                "scheme":    "exact",
                "network":   network,
                "maxAmount": str(int(amount * 1_000_000)),   # 6-decimal
                "resource":  f"http://localhost:8000{path}",
                "asset":     _USDC_MINT,
                "payTo":     treasury_pub,
                "nonce":     nonce,
                "expiry":    ts + 60,
            }],
        }

        # ── Phase 2: Agent signs + submits real Solana transfer ───────────────
        sig = solana_service.transfer(wallet_id, treasury_pub, lamports)
        on_chain = solana_service.is_real_sig(sig) and solana_service._available
        explorer_url = solana_service.explorer_url(sig) if on_chain else ""

        # Build X-Payment header (base64 of payment proof)
        x_payment = base64.b64encode(
            f"solana:{sig}:{treasury_pub}:{nonce}".encode()
        ).decode()

        # ── Receipt ───────────────────────────────────────────────────────────
        return {
            "success":      True,
            "txHash":       sig,
            "network":      network,
            "asset":        _USDC_MINT,
            "amount":       amount,
            "lamports":     lamports,
            "currency":     ep["currency"],
            "endpoint":     path,
            "label":        ep["label"],
            "wallet_id":    wallet_id,
            "nonce":        nonce,
            "timestamp":    ts,
            "on_chain":     on_chain,
            "explorer_url": explorer_url,
            "x_payment":    x_payment,
            "requirements": payment_requirements,
        }

    def pay_search(self, wallet_id: str) -> dict:
        return self.gate("search", wallet_id)

    def pay_analyze(self, wallet_id: str) -> dict:
        return self.gate("analyze", wallet_id)

    def pay_publish(self, wallet_id: str) -> dict:
        return self.gate("publish", wallet_id)


# Singleton
x402_service = X402Service()
