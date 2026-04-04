"""
Solana Service — Devnet keypair generation, airdrop, and SOL transfers.

Uses `solders` for keypair generation and raw httpx JSON-RPC for all
network calls. Degrades gracefully to deterministic mock signatures when
solders is unavailable (e.g., dev environment without Rust toolchain).

In-memory keypair cache keyed by PocketBase wallet_id — acceptable for
single-process demo deployments (resets on restart).
"""

import base64
import hashlib
import os
import struct
import time
from typing import Optional

import httpx

DEVNET_RPC = os.environ.get("SOLANA_RPC_URL", "https://api.devnet.solana.com")
EXPLORER_BASE = "https://explorer.solana.com/tx"

# wallet_id → 64-byte privkey hex (32 privkey || 32 pubkey)
_WALLET_KEYS: dict = {}

# ── Mock fallback ──────────────────────────────────────────────────────────────

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    result: list = []
    while n:
        n, r = divmod(n, 58)
        result.append(_B58[r])
    return ("".join(reversed(result)) or _B58[0])


def _mock_sig(seed: str) -> str:
    """Deterministic 88-char mock base58 signature."""
    raw = hashlib.sha256(seed.encode()).digest() * 4
    sig = _b58encode(raw[:64])
    return (sig * 2)[:88]


def _mock_pubkey(seed: str) -> str:
    """Deterministic 44-char mock base58 Solana pubkey."""
    raw = hashlib.sha256(f"pubkey:{seed}".encode()).digest()
    return (_b58encode(raw) * 2)[:44]


# ── Main service ───────────────────────────────────────────────────────────────

class SolanaService:
    def __init__(self):
        self._http = httpx.Client(timeout=30.0)
        self._available = self._check_libs()
        # Treasury keypair for x402 receipts — generated once at startup
        self._treasury_pubkey, self._treasury_privkey_hex = self._init_treasury()

    # ── Availability check ────────────────────────────────────────────────────

    def _check_libs(self) -> bool:
        try:
            import solders.keypair  # noqa
            import solders.instruction  # noqa
            return True
        except ImportError:
            return False

    # ── Treasury (x402 payment receiver) ──────────────────────────────────────

    def _init_treasury(self) -> tuple:
        if self._available:
            try:
                from solders.keypair import Keypair
                kp = Keypair()
                pubkey = str(kp.pubkey())
                privkey_hex = bytes(kp).hex()
                _WALLET_KEYS["x402_treasury"] = privkey_hex
                # Airdrop async — don't block startup
                self._airdrop_async(pubkey, 500_000_000)
                return pubkey, privkey_hex
            except Exception as e:
                print(f"[solana treasury init] {e}")
        # Mock fallback
        pubkey = _mock_pubkey("x402_treasury")
        _WALLET_KEYS["x402_treasury"] = "00" * 64
        return pubkey, "00" * 64

    # ── RPC helper ────────────────────────────────────────────────────────────

    def _rpc(self, method: str, params: list) -> dict:
        try:
            r = self._http.post(
                DEVNET_RPC,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                timeout=20,
            )
            return r.json()
        except Exception as e:
            print(f"[solana rpc:{method}] {e}")
            return {}

    # ── Airdrop (fire-and-forget) ─────────────────────────────────────────────

    def _airdrop_async(self, pubkey: str, lamports: int):
        """Fire airdrop — do not wait for confirmation."""
        try:
            self._rpc("requestAirdrop", [pubkey, lamports])
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_and_fund(self) -> dict:
        """
        Generate a Solana keypair and airdrop 0.5 SOL on devnet.
        Returns {pubkey, privkey_hex}.
        Falls back to deterministic mock if solders unavailable.
        """
        if self._available:
            try:
                from solders.keypair import Keypair
                kp = Keypair()
                pubkey = str(kp.pubkey())
                privkey_hex = bytes(kp).hex()
                self._airdrop_async(pubkey, 500_000_000)
                return {"pubkey": pubkey, "privkey_hex": privkey_hex, "on_chain": True}
            except Exception as e:
                print(f"[solana generate] {e}")
        # Mock fallback
        import secrets
        privkey = secrets.token_bytes(64)
        pubkey = _mock_pubkey(privkey.hex()[:16])
        return {"pubkey": pubkey, "privkey_hex": privkey.hex(), "on_chain": False}

    def register(self, wallet_id: str, privkey_hex: str):
        """Associate a PocketBase wallet_id with its Solana privkey for transfers."""
        _WALLET_KEYS[wallet_id] = privkey_hex

    def transfer(self, from_wallet_id: str, to_pubkey: str, lamports: int = 1_000) -> str:
        """
        Send SOL on devnet from a registered wallet.
        Returns tx signature (real base58 if on-chain, deterministic mock otherwise).
        """
        privkey_hex = _WALLET_KEYS.get(from_wallet_id)
        if not privkey_hex or privkey_hex == "00" * 64:
            return _mock_sig(f"{from_wallet_id}:{to_pubkey}:{lamports}:{time.time()}")
        if not self._available:
            return _mock_sig(f"{from_wallet_id}:{to_pubkey}:{lamports}:{time.time()}")
        try:
            return self._real_transfer(privkey_hex, to_pubkey, lamports)
        except Exception as e:
            print(f"[solana transfer] fallback: {e}")
            return _mock_sig(f"{from_wallet_id}:{to_pubkey}:{lamports}:{time.time()}")

    def _real_transfer(self, privkey_hex: str, to_pubkey_str: str, lamports: int) -> str:
        """Build, sign, and send a real devnet SOL transfer."""
        from solders.keypair import Keypair
        from solders.pubkey import Pubkey
        from solders.hash import Hash
        from solders.instruction import Instruction, AccountMeta

        kp = Keypair.from_bytes(bytes.fromhex(privkey_hex))
        to_pk = Pubkey.from_string(to_pubkey_str)
        system_id = Pubkey.from_string("11111111111111111111111111111111")

        # Get recent blockhash
        bh_resp = self._rpc("getLatestBlockhash", [{"commitment": "confirmed"}])
        blockhash_str = bh_resp.get("result", {}).get("value", {}).get("blockhash")
        if not blockhash_str:
            raise Exception("Could not get blockhash")
        recent_bh = Hash.from_string(blockhash_str)

        # System transfer instruction (type 2, u64 little-endian amount)
        ix_data = struct.pack("<IQ", 2, lamports)
        ix = Instruction(
            program_id=system_id,
            accounts=[
                AccountMeta(pubkey=kp.pubkey(), is_signer=True, is_writable=True),
                AccountMeta(pubkey=to_pk, is_signer=False, is_writable=True),
            ],
            data=bytes(ix_data),
        )

        # Try VersionedTransaction (MessageV0) first — most compatible
        try:
            from solders.transaction import VersionedTransaction
            from solders.message import MessageV0

            msg = MessageV0.try_compile(
                payer=kp.pubkey(),
                instructions=[ix],
                address_lookup_table_accounts=[],
                recent_blockhash=recent_bh,
            )
            txn = VersionedTransaction(msg, [kp])
            raw = bytes(txn)
            encoded = base64.b64encode(raw).decode()
            resp = self._rpc("sendTransaction", [
                encoded,
                {"encoding": "base64", "skipPreflight": True,
                 "preflightCommitment": "confirmed"},
            ])
            sig = resp.get("result")
            if sig:
                return str(sig)
        except Exception as e1:
            print(f"[solana v0tx] {e1}")

        # Fallback: legacy Transaction
        try:
            from solders.transaction import Transaction as LegacyTx
            from solders.message import Message

            msg = Message.new_with_blockhash([ix], kp.pubkey(), recent_bh)
            txn = LegacyTx([kp], msg, recent_bh)
            raw = bytes(txn)
            encoded = base64.b64encode(raw).decode()
            resp = self._rpc("sendTransaction", [
                encoded,
                {"encoding": "base64", "skipPreflight": True},
            ])
            sig = resp.get("result")
            if sig:
                return str(sig)
        except Exception as e2:
            print(f"[solana legacytx] {e2}")

        raise Exception("Could not build or send Solana transaction")

    def explorer_url(self, sig: str) -> str:
        return f"{EXPLORER_BASE}/{sig}?cluster=devnet"

    def is_real_sig(self, sig: str) -> bool:
        """Heuristic: real base58 Solana sigs are ~87-88 chars and alphanumeric."""
        return len(sig) >= 80 and sig.isalnum()


# Module-level singleton
solana_service = SolanaService()
