#!/usr/bin/env python3
"""
Backfill script to populate `ows_did` for all existing agent wallets.
Derives a `did:key` from the wallet's existing `sol_address`.
"""

import base58
import base64
import os
import sys

from services.pocketbase import PocketBaseService

def sol_address_to_did_key(sol_address: str) -> str:
    """Derive a did:key from a base58 Solana public key."""
    if not sol_address:
        return ""
    try:
        pubkey_bytes = base58.b58decode(sol_address)
        # Multicodec prefix for Ed25519: 0xed01
        multicodec = b'\xed\x01' + pubkey_bytes
        encoded = base64.urlsafe_b64encode(multicodec).rstrip(b'=').decode()
        return f"did:key:z{encoded}"
    except Exception as e:
        print(f"Error encoding {sol_address}: {e}")
        return ""

def main():
    pb = PocketBaseService()
    try:
        # We need to fetch all wallets, limit 200 is fine if the DB is small
        wallets = pb.list("wallets", limit=200)
    except Exception as e:
        print(f"Failed to fetch wallets: {e}")
        sys.exit(1)

    updated_count = 0
    for wallet in wallets:
        if wallet.get("ows_did"):
            continue # already backfilled
        
        sol_addr = wallet.get("sol_address", "")
        if sol_addr:
            did_key = sol_address_to_did_key(sol_addr)
            if did_key:
                try:
                    pb.update("wallets", wallet["id"], {"ows_did": did_key})
                    updated_count += 1
                    print(f"Updated {wallet['name']} with DID: {did_key}")
                except Exception as e:
                    print(f"Failed to update wallet {wallet['id']}: {e}")

    print(f"Backfill complete! Updated {updated_count} wallets.")

if __name__ == "__main__":
    # Ensure package runs in backend dir
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
