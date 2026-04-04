"""
x402 Payment Service — Mock Solana USDC micropayment gating.

Implements the x402 two-phase HTTP protocol:
  Phase 1: Server returns 402 with payment requirements
  Phase 2: Client presents X-Payment header → server issues receipt

All Solana signatures are mock base58-encoded (no on-chain dependency).
Three gated microservices:
  /x402/search   — 0.001 USDC  (ATLAS pays for web search access)
  /x402/analyze  — 0.002 USDC  (CIPHER pays for analysis engine access)
  /x402/publish  — 0.001 USDC  (FORGE pays for publish endpoint access)
"""

import base64
import hashlib
import os
import time
import uuid
from typing import Optional

# ── Mock base58 alphabet ──────────────────────────────────────────────────────
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _mock_b58_encode(data: bytes) -> str:
    """Produce a plausible-looking base58 string from raw bytes."""
    n = int.from_bytes(data, "big")
    result = []
    while n:
        n, rem = divmod(n, 58)
        result.append(_B58[rem])
    return "".join(reversed(result)) or _B58[0]


def _mock_solana_signature(seed: str) -> str:
    """Return a deterministic mock Solana signature (88-char base58)."""
    raw = hashlib.sha256(seed.encode()).digest() + hashlib.sha256(seed[::-1].encode()).digest()
    sig = _mock_b58_encode(raw)
    # Pad / trim to canonical 88 chars
    sig = (sig * 3)[:88]
    return sig


# ── Endpoint registry ─────────────────────────────────────────────────────────

ENDPOINTS = {
    "search":  {"path": "/x402/search",  "amount": 0.001, "currency": "USDC", "network": "solana-devnet"},
    "analyze": {"path": "/x402/analyze", "amount": 0.002, "currency": "USDC", "network": "solana-devnet"},
    "publish": {"path": "/x402/publish", "amount": 0.001, "currency": "USDC", "network": "solana-devnet"},
}

# Mock USDC devnet program address (real address on Solana devnet)
_USDC_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
_TREASURY_PUBKEY = "REGiSsovereign1111111111111111111111111111"


class X402Service:
    """
    Mock x402 micropayment service.
    No network calls — all signatures and receipts are deterministic mocks.
    """

    def gate(self, endpoint: str, wallet_id: str) -> dict:
        """
        Simulate full two-phase x402 flow:
          1. Issue payment requirements (402)
          2. Agent 'signs' mock Solana tx
          3. Server validates and issues receipt

        Returns a receipt dict or raises if endpoint unknown.
        """
        ep = ENDPOINTS.get(endpoint)
        if not ep:
            raise ValueError(f"Unknown x402 endpoint: {endpoint}")

        nonce   = uuid.uuid4().hex[:16]
        amount  = ep["amount"]
        network = ep["network"]
        path    = ep["path"]
        ts      = int(time.time())

        # ── Phase 1: 402 payment requirements ────────────────────────────────
        payment_requirements = {
            "x402Version": 1,
            "accepts": [
                {
                    "scheme":     "exact",
                    "network":    network,
                    "maxAmount":  str(int(amount * 1_000_000)),   # 6-decimal USDC
                    "resource":   f"http://localhost:8000{path}",
                    "asset":      _USDC_MINT,
                    "payTo":      _TREASURY_PUBKEY,
                    "nonce":      nonce,
                    "expiry":     ts + 60,
                }
            ],
        }

        # ── Phase 2: Mock agent signs transaction ─────────────────────────────
        sig_seed  = f"{wallet_id}:{nonce}:{amount}:{ts}"
        signature = _mock_solana_signature(sig_seed)

        x_payment_header = base64.b64encode(
            f"solana:{signature}:{_TREASURY_PUBKEY}:{nonce}".encode()
        ).decode()

        # ── Phase 3: Server validates → issues receipt ────────────────────────
        receipt = {
            "success":    True,
            "txHash":     signature,
            "network":    network,
            "asset":      _USDC_MINT,
            "amount":     amount,
            "currency":   ep["currency"],
            "endpoint":   path,
            "wallet_id":  wallet_id,
            "nonce":      nonce,
            "timestamp":  ts,
            "x_payment":  x_payment_header,
            "requirements": payment_requirements,
        }
        return receipt

    def pay_search(self, wallet_id: str) -> dict:
        return self.gate("search", wallet_id)

    def pay_analyze(self, wallet_id: str) -> dict:
        return self.gate("analyze", wallet_id)

    def pay_publish(self, wallet_id: str) -> dict:
        return self.gate("publish", wallet_id)


# Singleton
x402_service = X402Service()
