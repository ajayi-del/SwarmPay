"""
PocketBase collections for Reputation System
Based on Claude Code Agent Swarms data patterns
"""

import asyncio
import httpx
import json

async def setup_reputation_collections():
    """Setup reputation-related collections"""
    
    base_url = "http://localhost:8090"
    admin_email = "admin@swarmpay.local"
    admin_password = "password123456"
    
    async with httpx.AsyncClient() as client:
        # Login as admin
        login_response = await client.post(f"{base_url}/api/collections/users/auth-with-password", 
                                          json={
                                              "identity": admin_email,
                                              "password": admin_password
                                          })
        
        if login_response.status_code != 200:
            print("❌ Admin login failed")
            return
        
        token = login_response.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        print("🔧 Setting up reputation collections...")
        
        # 1. Update agents collection with reputation field
        agents_collection = {
            "name": "agents",
            "type": "base",
            "schema": [
                {
                    "name": "id",
                    "type": "text",
                    "required": True,
                    "unique": True
                },
                {
                    "name": "name",
                    "type": "text",
                    "required": True
                },
                {
                    "name": "role",
                    "type": "text",
                    "required": True
                },
                {
                    "name": "wallet_id",
                    "type": "text",
                    "required": True
                },
                {
                    "name": "api_key_id",
                    "type": "text",
                    "required": True
                },
                {
                    "name": "status",
                    "type": "select",
                    "required": True,
                    "options": [
                        {"value": "idle", "label": "Idle"},
                        {"value": "busy", "label": "Busy"},
                        {"value": "error", "label": "Error"},
                        {"value": "swept", "label": "Swept"}
                    ]
                },
                {
                    "name": "reputation",
                    "type": "number",
                    "required": False,
                    "default": 3.0,
                    "min": 1.0,
                    "max": 5.0
                },
                {
                    "name": "last_reputation_update",
                    "type": "number",
                    "required": False
                },
                {
                    "name": "total_earned",
                    "type": "number",
                    "required": False,
                    "default": 0.0
                },
                {
                    "name": "tasks_completed",
                    "type": "number",
                    "required": False,
                    "default": 0
                },
                {
                    "name": "created_at",
                    "type": "autodate",
                    "required": True
                }
            ]
        }
        
        # Create/update agents collection
        response = await client.put(f"{base_url}/api/collections/agents", 
                                  json=agents_collection, headers=headers)
        
        if response.status_code in [200, 204]:
            print("✅ Agents collection updated for reputation")
        else:
            print(f"❌ Failed to update agents collection: {response.text}")
        
        # 2. Update audit_log collection for reputation events
        audit_collection = {
            "name": "audit_log",
            "type": "base",
            "schema": [
                {
                    "name": "agent_id",
                    "type": "text",
                    "required": True
                },
                {
                    "name": "event_type",
                    "type": "select",
                    "required": True,
                    "options": [
                        {"value": "TASK_CREATED", "label": "Task Created"},
                        {"value": "TASK_COMPLETED", "label": "Task Completed"},
                        {"value": "TASK_FAILED", "label": "Task Failed"},
                        {"value": "PAYMENT_SENT", "label": "Payment Sent"},
                        {"value": "PAYMENT_BLOCKED", "label": "Payment Blocked"},
                        {"value": "REPUTATION_CHANGE", "label": "Reputation Change"},
                        {"value": "PEER_PAYMENT", "label": "Peer Payment"},
                        {"value": "SECURITY_SWEEP", "label": "Security Sweep"}
                    ]
                },
                {
                    "name": "event_data",
                    "type": "json",
                    "required": False
                },
                {
                    "name": "amount",
                    "type": "number",
                    "required": False
                },
                {
                    "name": "reason",
                    "type": "text",
                    "required": False
                },
                {
                    "name": "timestamp",
                    "type": "number",
                    "required": True
                },
                {
                    "name": "created_at",
                    "type": "autodate",
                    "required": True
                }
            ]
        }
        
        # Create/update audit_log collection
        response = await client.put(f"{base_url}/api/collections/audit_log", 
                                  json=audit_collection, headers=headers)
        
        if response.status_code in [200, 204]:
            print("✅ Audit log collection updated for reputation events")
        else:
            print(f"❌ Failed to update audit_log collection: {response.text}")
        
        # 3. Create reputation_history collection
        reputation_history_collection = {
            "name": "reputation_history",
            "type": "base",
            "schema": [
                {
                    "name": "agent_id",
                    "type": "text",
                    "required": True
                },
                {
                    "name": "previous_reputation",
                    "type": "number",
                    "required": True
                },
                {
                    "name": "new_reputation",
                    "type": "number",
                    "required": True
                },
                {
                    "name": "change",
                    "type": "text",
                    "required": True
                },
                {
                    "name": "event_type",
                    "type": "select",
                    "required": True,
                    "options": [
                        {"value": "TASK_SUCCESS", "label": "Task Success"},
                        {"value": "TASK_FAILED", "label": "Task Failed"},
                        {"value": "MANUAL_ADJUSTMENT", "label": "Manual Adjustment"}
                    ]
                },
                {
                    "name": "task_id",
                    "type": "text",
                    "required": False
                },
                {
                    "name": "timestamp",
                    "type": "number",
                    "required": True
                },
                {
                    "name": "created_at",
                    "type": "autodate",
                    "required": True
                }
            ]
        }
        
        # Create reputation_history collection
        response = await client.put(f"{base_url}/api/collections/reputation_history", 
                                  json=reputation_history_collection, headers=headers)
        
        if response.status_code in [200, 204]:
            print("✅ Reputation history collection created")
        else:
            print(f"❌ Failed to create reputation_history collection: {response.text}")
        
        # 4. Set open API rules for demo
        rules = [
            {
                "name": "agents_public_read",
                "type": "api",
                "collections": ["agents"],
                "actions": ["read"],
                "filter": ""
            },
            {
                "name": "audit_log_public_read", 
                "type": "api",
                "collections": ["audit_log"],
                "actions": ["read"],
                "filter": ""
            },
            {
                "name": "reputation_history_public_read",
                "type": "api", 
                "collections": ["reputation_history"],
                "actions": ["read"],
                "filter": ""
            }
        ]
        
        for rule in rules:
            response = await client.post(f"{base_url}/api/collections/rules", 
                                        json=rule, headers=headers)
            if response.status_code in [200, 204]:
                print(f"✅ Created rule: {rule['name']}")
            else:
                print(f"❌ Failed to create rule: {rule['name']}")
        
        print("\n🎉 Reputation collections setup complete!")

if __name__ == "__main__":
    asyncio.run(setup_reputation_collections())
