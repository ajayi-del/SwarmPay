import httpx
import sys
import asyncio

PB_URL = "http://127.0.0.1:8090"
ADMIN_EMAIL = "admin@swarmpay.local"
ADMIN_PASSWORD = "password123456" # minimum 10 characters for PocketBase

# Schema definition exactly as requested
# Note: 'id' and 'created_at' / 'updated_at' are built-in fields in PocketBase base collections.
collections = [
    {
        "name": "wallets",
        "type": "base",
        "schema": [
            {"name": "name", "type": "text"},
            {"name": "role", "type": "text"},
            {"name": "eth_address", "type": "text"},
            {"name": "sol_address", "type": "text"},
            {"name": "budget_cap", "type": "number"},
            {"name": "balance", "type": "number"},
            {"name": "api_key_id", "type": "text"}
        ]
    },
    {
        "name": "tasks",
        "type": "base",
        "schema": [
            {"name": "description", "type": "text"},
            {"name": "total_budget", "type": "number"},
            {"name": "status", "type": "text"},
            {"name": "coordinator_wallet_id", "type": "text"}
        ]
    },
    {
        "name": "sub_tasks",
        "type": "base",
        "schema": [
            {"name": "task_id", "type": "text"},
            {"name": "agent_id", "type": "text"},
            {"name": "wallet_id", "type": "text"},
            {"name": "description", "type": "text"},
            {"name": "budget_allocated", "type": "number"},
            {"name": "status", "type": "text"},
            {"name": "output", "type": "text"}
        ]
    },
    {
        "name": "payments",
        "type": "base",
        "schema": [
            {"name": "from_wallet_id", "type": "text"},
            {"name": "to_wallet_id", "type": "text"},
            {"name": "amount", "type": "number"},
            {"name": "chain_id", "type": "text"},
            {"name": "status", "type": "text"},
            {"name": "policy_reason", "type": "text"},
            {"name": "tx_hash", "type": "text"}
        ]
    },
    {
        "name": "audit_log",
        "type": "base",
        "schema": [
            {"name": "event_type", "type": "text"},
            {"name": "entity_id", "type": "text"},
            {"name": "message", "type": "text"},
            {"name": "metadata", "type": "json"}
        ]
    }
]

async def create_admin(client):
    try:
        response = await client.post('/api/admins', json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "passwordConfirm": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            print(f"✅ Initial admin account created ({ADMIN_EMAIL})")
        else:
            # Note: might already exist
            pass
    except Exception as e:
        pass

async def auth_admin(client):
    response = await client.post('/api/admins/auth-with-password', json={
        "identity": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    
    if response.status_code != 200:
        print("❌ Failed to authenticate with PocketBase. Ensure it's running and admin matches.")
        sys.exit(1)
        
    token = response.json().get('token')
    return token

async def create_collections(client, token):
    headers = {"Authorization": token}
    
    for coll in collections:
        print(f"Creating collection '{coll['name']}'...")
        # Add basic API rules to allow read/write for the demo without authentication handling for now
        coll_data = coll.copy()
        coll_data.update({
            "listRule": "",
            "viewRule": "",
            "createRule": "",
            "updateRule": "",
            "deleteRule": ""
        })
        
        response = await client.post('/api/collections', headers=headers, json=coll_data)
        
        if response.status_code == 200:
            print(f"✅ Collection '{coll['name']}' created successfully.")
        elif response.status_code == 400 and "already exists" in response.text.lower() or "validation_not_unique" in response.text.lower():
            print(f"⚠️ Collection '{coll['name']}' already exists.")
        else:
            print(f"❌ Failed to create '{coll['name']}': {response.text}")

async def main():
    print("🚀 Initializing SwarmPay PocketBase Schema")
    async with httpx.AsyncClient(base_url=PB_URL) as client:
        # Check if pocketbase is alive
        try:
            await client.get('/api/health')
        except httpx.ConnectError:
            print("❌ Connections failed. Is PocketBase running on http://127.0.0.1:8090?")
            sys.exit(1)

        await create_admin(client)
        token = await auth_admin(client)
        await create_collections(client, token)
        print("🎉 PocketBase schema setup complete!")

if __name__ == "__main__":
    asyncio.run(main())
