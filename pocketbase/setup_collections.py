#!/usr/bin/env python3
"""
PocketBase Collections Setup for SwarmPay
Run this script to create all required collections with proper schema
"""

import requests
import json
import time
from typing import Dict, List, Any

class PocketBaseSetup:
    def __init__(self, base_url: str = "http://localhost:8090"):
        self.base_url = base_url
        self.admin_email = "admin@swarmpay.dev"
        self.admin_password = "admin123456"
        self.token = None
    
    def login_admin(self) -> bool:
        """Login as admin to get auth token"""
        try:
            response = requests.post(f"{self.base_url}/api/admins/auth-with-password", json={
                "identity": self.admin_email,
                "password": self.admin_password
            })
            if response.status_code == 200:
                data = response.json()
                self.token = data["token"]
                print("✓ Admin login successful")
                return True
            else:
                print(f"✗ Admin login failed: {response.text}")
                return False
        except Exception as e:
            print(f"✗ Admin login error: {e}")
            return False
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def create_collection(self, name: str, schema: List[Dict[str, Any]]) -> bool:
        """Create a collection with given schema"""
        try:
            # Check if collection already exists
            existing = requests.get(
                f"{self.base_url}/api/collections/{name}",
                headers=self.get_headers()
            )
            if existing.status_code == 200:
                print(f"⚠ Collection '{name}' already exists, skipping...")
                return True
            
            # Create collection
            collection_data = {
                "name": name,
                "type": "base",
                "schema": schema
            }
            
            response = requests.post(
                f"{self.base_url}/api/collections",
                headers=self.get_headers(),
                json=collection_data
            )
            
            if response.status_code == 200:
                print(f"✓ Collection '{name}' created successfully")
                return True
            else:
                print(f"✗ Failed to create collection '{name}': {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Error creating collection '{name}': {e}")
            return False
    
    def setup_all_collections(self) -> bool:
        """Setup all required collections"""
        if not self.login_admin():
            return False
        
        collections = {
            "wallets": [
                {"name": "id", "type": "text", "required": True, "unique": True},
                {"name": "name", "type": "text", "required": True},
                {"name": "role", "type": "text", "required": True},
                {"name": "eth_address", "type": "text", "required": True, "unique": True},
                {"name": "sol_address", "type": "text", "required": True, "unique": True},
                {"name": "budget_cap", "type": "number", "required": True},
                {"name": "balance", "type": "number", "required": True},
                {"name": "api_key_id", "type": "text", "required": True},
                {"name": "created_at", "type": "date", "required": True}
            ],
            
            "tasks": [
                {"name": "id", "type": "text", "required": True, "unique": True},
                {"name": "description", "type": "text", "required": True},
                {"name": "total_budget", "type": "number", "required": True},
                {"name": "status", "type": "text", "required": True},
                {"name": "coordinator_wallet_id", "type": "text", "required": True},
                {"name": "created_at", "type": "date", "required": True}
            ],
            
            "sub_tasks": [
                {"name": "id", "type": "text", "required": True, "unique": True},
                {"name": "task_id", "type": "text", "required": True},
                {"name": "agent_id", "type": "text", "required": True},
                {"name": "wallet_id", "type": "text", "required": True},
                {"name": "description", "type": "text", "required": True},
                {"name": "budget_allocated", "type": "number", "required": True},
                {"name": "status", "type": "text", "required": True},
                {"name": "output", "type": "text", "required": False},
                {"name": "created_at", "type": "date", "required": True}
            ],
            
            "payments": [
                {"name": "id", "type": "text", "required": True, "unique": True},
                {"name": "from_wallet_id", "type": "text", "required": True},
                {"name": "to_wallet_id", "type": "text", "required": True},
                {"name": "amount", "type": "number", "required": True},
                {"name": "chain_id", "type": "text", "required": True},
                {"name": "status", "type": "text", "required": True},
                {"name": "policy_reason", "type": "text", "required": False},
                {"name": "tx_hash", "type": "text", "required": False},
                {"name": "created_at", "type": "date", "required": True}
            ],
            
            "audit_log": [
                {"name": "id", "type": "text", "required": True, "unique": True},
                {"name": "event_type", "type": "text", "required": True},
                {"name": "entity_id", "type": "text", "required": True},
                {"name": "message", "type": "text", "required": True},
                {"name": "metadata", "type": "json", "required": False},
                {"name": "created_at", "type": "date", "required": True}
            ]
        }
        
        success = True
        for collection_name, schema in collections.items():
            if not self.create_collection(collection_name, schema):
                success = False
            time.sleep(0.1)  # Small delay to avoid overwhelming
        
        if success:
            print("\n✅ All collections created successfully!")
            print("PocketBase is ready for SwarmPay.")
        else:
            print("\n❌ Some collections failed to create. Check the logs above.")
        
        return success

def main():
    """Main setup function"""
    print("🚀 SwarmPay PocketBase Setup")
    print("=" * 40)
    
    setup = PocketBaseSetup()
    
    # Check if PocketBase is running
    try:
        response = requests.get("http://localhost:8090/api/health")
        if response.status_code != 200:
            print("❌ PocketBase is not running on http://localhost:8090")
            print("Please start PocketBase first:")
            print("  cd pocketbase")
            print("  ./pocketbase serve")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to PocketBase on http://localhost:8090")
        print("Please start PocketBase first:")
        print("  cd pocketbase")
        print("  ./pocketbase serve")
        return
    
    # Setup collections
    setup.setup_all_collections()

if __name__ == "__main__":
    main()
