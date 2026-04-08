#!/usr/bin/env python3
"""
Phase 2/3 schema migration for SwarmPay.
Usage: POCKETBASE_ADMIN_EMAIL=admin@example.com POCKETBASE_ADMIN_PASSWORD=... python migrations/phase2_schema.py

Modifies `wallets` collection and creates `x402_calls` and `swarm_loans`.
"""

import httpx
import os
import sys

URL = os.environ.get("POCKETBASE_URL", "http://localhost:8090")
EMAIL = os.environ.get("POCKETBASE_ADMIN_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("POCKETBASE_ADMIN_PASSWORD", "admin123456")

def main():
    with httpx.Client(base_url=URL) as client:
        # 1. Authenticate as Admin
        try:
            r = client.post("/api/admins/auth-with-password", json={
                "identity": EMAIL,
                "password": PASSWORD
            })
            r.raise_for_status()
            token = r.json()["token"]
        except httpx.HTTPError as e:
            print(f"Failed to authenticate as admin: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(e.response.text)
            sys.exit(1)

        headers = {"Authorization": f"User {token}"} # PB Admin token

        # 2. Update `wallets`
        r = client.get("/api/collections/wallets", headers=headers)
        if r.status_code == 200:
            wallet_col = r.json()
            schema = wallet_col.get("schema", [])
            existing_fields = {f["name"] for f in schema}
            
            new_fields = [
                {"system": False, "id": "owsdid001", "name": "ows_did", "type": "text", "required": False, "presentable": False, "unique": False, "options": {"min": None, "max": None, "pattern": ""}},
                {"system": False, "id": "mpagent001", "name": "moonpay_agent_id", "type": "text", "required": False, "presentable": False, "unique": False, "options": {"min": None, "max": None, "pattern": ""}},
                {"system": False, "id": "fiatbal001", "name": "fiat_balance_usd", "type": "number", "required": False, "presentable": False, "unique": False, "options": {"min": None, "max": None, "noDecimal": False}},
                {"system": False, "id": "topupthr001", "name": "auto_topup_threshold_usd", "type": "number", "required": False, "presentable": False, "unique": False, "options": {"min": None, "max": None, "noDecimal": False}},
                {"system": False, "id": "humveto001", "name": "human_veto_required", "type": "bool", "required": False, "presentable": False, "unique": False, "options": {}},
            ]
            
            added = False
            for f in new_fields:
                if f["name"] not in existing_fields:
                    schema.append(f)
                    added = True
            
            if added:
                wallet_col["schema"] = schema
                u = client.patch(f"/api/collections/wallets", json=wallet_col, headers=headers)
                print(f"Updated 'wallets' schema: {u.status_code}")
            else:
                print("Wallets schema already up to date.")
        else:
            print("Wallets collection not found.")

        # 3. Create `x402_calls`
        x402_schema = {
            "name": "x402_calls",
            "type": "base",
            "system": False,
            "schema": [
                {"system": False, "id": "tskid001", "name": "task_id", "type": "text", "required": True, "unique": False},
                {"system": False, "id": "agtid001", "name": "agent_id", "type": "text", "required": True, "unique": False},
                {"system": False, "id": "srvnm001", "name": "service_name", "type": "text", "required": True, "unique": False},
                {"system": False, "id": "reqhsh001", "name": "request_hash", "type": "text", "required": False, "unique": False},
                {"system": False, "id": "amtsol001", "name": "amount_sol", "type": "number", "required": True, "unique": False},
                {"system": False, "id": "slscntx001", "name": "solscan_tx", "type": "text", "required": False, "unique": False},
                {"system": False, "id": "stts001", "name": "status", "type": "select", "required": True, "unique": False, "options": {"maxSelect": 1, "values": ["signed_mock", "signed", "confirmed", "failed"]}},
            ],
            "listRule": "",
            "viewRule": "",
            "createRule": "",
            "updateRule": "",
            "deleteRule": "",
        }
        r = client.post("/api/collections", json=x402_schema, headers=headers)
        if r.status_code in (200, 204):
            print("Created 'x402_calls' collection")
        elif r.status_code == 400 and "name" in r.text:
            print("'x402_calls' already exists")
        else:
            print(f"Failed to create x402_calls: {r.text}")

        # 4. Create `swarm_loans`
        loans_schema = {
            "name": "swarm_loans",
            "type": "base",
            "system": False,
            "schema": [
                {"system": False, "id": "bwagt001", "name": "borrower_agent_id", "type": "text", "required": True, "unique": False},
                {"system": False, "id": "ldpol001", "name": "lender_pool", "type": "json", "required": False, "unique": False},
                {"system": False, "id": "amtusd001", "name": "amount_usd", "type": "number", "required": True, "unique": False},
                {"system": False, "id": "intrat001", "name": "interest_rate", "type": "number", "required": True, "unique": False},
                {"system": False, "id": "repusd001", "name": "repaid_usd", "type": "number", "required": False, "unique": False},
                {"system": False, "id": "lnstts001", "name": "status", "type": "select", "required": True, "unique": False, "options": {"maxSelect": 1, "values": ["active", "repaid", "defaulted"]}},
            ],
            "listRule": "",
            "viewRule": "",
            "createRule": "",
            "updateRule": "",
            "deleteRule": "",
        }
        r = client.post("/api/collections", json=loans_schema, headers=headers)
        if r.status_code in (200, 204):
            print("Created 'swarm_loans' collection")
        elif r.status_code == 400 and "name" in r.text:
            print("'swarm_loans' already exists")
        else:
            print(f"Failed to create swarm_loans: {r.text}")

        print("Migration complete.")

if __name__ == "__main__":
    main()
