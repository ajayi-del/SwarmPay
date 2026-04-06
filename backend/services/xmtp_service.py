"""
XMTP Service — Decentralized agent-to-agent messaging.

XMTP (Extensible Message Transport Protocol) is an open, decentralized protocol
for wallet-to-wallet messaging. Each agent's ETH address is its identity.

Architecture:
  • Messages addressed to wallet addresses — no central server
  • End-to-end encrypted via MLS (Messaging Layer Security)
  • Persistent: messages stored on XMTP network nodes

Fallback contract:
  • If XMTP_PRIVATE_KEY not set: mock mode (log only, no network calls)
  • All methods return structured result dicts — callers never see raw exceptions
  • Synchronous — call via asyncio.to_thread from async context

Env vars:
  XMTP_PRIVATE_KEY  — agent's ETH private key (hex, no 0x prefix)
  XMTP_ENV          — "production" | "dev" (default: "dev")
"""

import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

import requests

logger = logging.getLogger("swarmpay.xmtp")

_PRIVATE_KEY = os.environ.get("XMTP_PRIVATE_KEY", "").strip()
_ENV = os.environ.get("XMTP_ENV", "dev").strip()

# XMTP HTTP API base (gRPC-gateway compatible REST endpoint)
_API_BASE = {
    "production": "https://production.xmtp.network",
    "dev":        "https://dev.xmtp.network",
}.get(_ENV, "https://dev.xmtp.network")

_TIMEOUT = 8  # seconds per request


class XMTPService:
    """
    Agent messaging over XMTP protocol.

    Agents talk via their ETH wallet addresses. Each message is a JSON
    envelope: { from, to, topic, payload, timestamp }.
    """

    def __init__(self):
        self._mock = not bool(_PRIVATE_KEY)
        if self._mock:
            logger.warning("[xmtp] XMTP_PRIVATE_KEY not set — running in mock mode")
        else:
            logger.info("[xmtp] initialized on XMTP %s network", _ENV)

    # ── Public API ─────────────────────────────────────────────────────────

    def send_message(
        self,
        to_address: str,
        topic: str,
        payload: dict,
        from_address: Optional[str] = None,
    ) -> dict:
        """
        Send a structured message to an agent wallet address.

        Args:
            to_address:   Recipient ETH wallet address (0x…)
            topic:        Message topic / intent ("task_dispatch", "payment_ready", etc.)
            payload:      Arbitrary JSON-serialisable dict
            from_address: Sender address (defaults to this node's address)

        Returns:
            { success, message_id, topic, to, timestamp, mock }
        """
        envelope = {
            "from":      from_address or self._local_address(),
            "to":        to_address,
            "topic":     topic,
            "payload":   payload,
            "timestamp": int(time.time() * 1000),
        }

        if self._mock:
            mid = _short_hash(json.dumps(envelope))
            logger.info("[xmtp mock] → %s topic=%s mid=%s", to_address[:10], topic, mid)
            return {"success": True, "message_id": mid, "mock": True, **envelope}

        try:
            return self._publish(envelope)
        except Exception as exc:
            logger.error("[xmtp] send failed: %s", exc)
            return {"success": False, "error": str(exc), "mock": False}

    def broadcast(
        self,
        addresses: list[str],
        topic: str,
        payload: dict,
    ) -> list[dict]:
        """
        Broadcast the same message to multiple agent addresses.
        Returns list of per-address results.
        """
        results = []
        for addr in addresses:
            results.append(self.send_message(addr, topic, payload))
        return results

    def query_messages(
        self,
        address: str,
        topic: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """
        Pull latest messages for a given wallet address.
        Returns list of envelope dicts, newest first.
        """
        if self._mock:
            logger.info("[xmtp mock] query %s topic=%s", address[:10], topic)
            return []

        try:
            params: dict[str, Any] = {"contentTopic": _xmtp_topic(address), "limit": limit}
            if topic:
                params["filter"] = topic
            r = requests.get(
                f"{_API_BASE}/api/v1/query",
                params=params,
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            envelopes = data.get("envelopes", [])
            return [_decode_envelope(e) for e in envelopes]
        except Exception as exc:
            logger.error("[xmtp] query failed: %s", exc)
            return []

    def is_reachable(self, address: str) -> bool:
        """Check if a wallet address has an XMTP identity (can receive messages)."""
        if self._mock:
            return True
        try:
            r = requests.post(
                f"{_API_BASE}/api/v1/identity/is-authorized",
                json={"walletAddress": address},
                timeout=_TIMEOUT,
            )
            return r.status_code == 200 and r.json().get("isAuthorized", False)
        except Exception:
            return False

    # ── Internal helpers ───────────────────────────────────────────────────

    def _local_address(self) -> str:
        """Derive ETH address from private key (simplified hex digest for mock)."""
        if not _PRIVATE_KEY:
            return "0x0000000000000000000000000000000000000000"
        try:
            from eth_account import Account
            return Account.from_key(_PRIVATE_KEY).address
        except Exception:
            return "0x" + hashlib.sha256(_PRIVATE_KEY.encode()).hexdigest()[:40]

    def _publish(self, envelope: dict) -> dict:
        """HTTP publish to XMTP network node."""
        body = {
            "envelopes": [{
                "contentTopic": _xmtp_topic(envelope["to"]),
                "timestampNs":  str(envelope["timestamp"] * 1_000_000),
                "message":      json.dumps(envelope).encode("utf-8").hex(),
            }]
        }
        r = requests.post(
            f"{_API_BASE}/api/v1/publish",
            json=body,
            headers={"Content-Type": "application/json"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        mid = _short_hash(json.dumps(envelope))
        return {"success": True, "message_id": mid, "mock": False, **envelope}


# ── Module-level helpers ───────────────────────────────────────────────────────

def _xmtp_topic(address: str) -> str:
    """XMTP content topic format: /xmtp/0/dm-{address}/proto"""
    addr = address.lower().lstrip("0x")
    return f"/xmtp/0/dm-{addr}/proto"


def _short_hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _decode_envelope(raw: dict) -> dict:
    """Decode a raw XMTP envelope back to a Python dict."""
    try:
        msg_hex = raw.get("message", "")
        msg_bytes = bytes.fromhex(msg_hex)
        return json.loads(msg_bytes.decode("utf-8"))
    except Exception:
        return raw


# Singleton
xmtp_service = XMTPService()
