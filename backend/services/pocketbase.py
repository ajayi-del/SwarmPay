"""
PocketBase Service - Handles all database operations
"""

import httpx
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

class PocketBaseService:
    def __init__(self, base_url: str = "http://localhost:8090"):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=30.0)
    
    def create(self, collection: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a record in a collection"""
        try:
            response = self.client.post(f"/api/collections/{collection}/records", json=data)
            if not response.is_success:
                print(f"PocketBase create error in {collection}: {response.status_code} {response.text}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"PocketBase create error in {collection}: {e}")
            raise
    
    def get(self, collection: str, record_id: str) -> Dict[str, Any]:
        """Get a specific record"""
        try:
            response = self.client.get(f"/api/collections/{collection}/records/{record_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"PocketBase get error in {collection}: {e}")
            raise
    
    def list(self, collection: str, filter_params: Optional[str] = None,
             limit: int = 50, sort: Optional[str] = None) -> List[Dict[str, Any]]:
        """List records from a collection"""
        try:
            params: Dict[str, Any] = {"perPage": limit}
            if filter_params:
                params["filter"] = filter_params
            if sort:
                params["sort"] = sort

            response = self.client.get(f"/api/collections/{collection}/records", params=params)
            response.raise_for_status()
            return response.json().get("items", [])
        except httpx.HTTPError as e:
            print(f"PocketBase list error in {collection}: {e}")
            raise
    
    def update(self, collection: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a record"""
        try:
            response = self.client.patch(f"/api/collections/{collection}/records/{record_id}", json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"PocketBase update error in {collection}: {e}")
            raise
    
    def delete(self, collection: str, record_id: str) -> bool:
        """Delete a record"""
        try:
            response = self.client.delete(f"/api/collections/{collection}/records/{record_id}")
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            print(f"PocketBase delete error in {collection}: {e}")
            return False
    
    def get_full_task(self, task_id: str) -> Dict[str, Any]:
        """Get task with coordinator_wallet, sub_tasks, and payments."""
        try:
            task = self.get("tasks", task_id)
            coordinator_wallet = self.get("wallets", task["coordinator_wallet_id"])
            sub_tasks = self.list("sub_tasks", filter_params=f"task_id='{task_id}'",
                                  sort="created")

            wallet_ids = [st["wallet_id"] for st in sub_tasks if st.get("wallet_id")]
            payments: List[Dict[str, Any]] = []
            if wallet_ids:
                payment_filter = "||".join(f"to_wallet_id='{wid}'" for wid in wallet_ids)
                payments = self.list("payments", filter_params=payment_filter,
                                     sort="created")

            return {
                "task": task,
                "coordinator_wallet": coordinator_wallet,
                "sub_tasks": sub_tasks,
                "payments": payments,
            }
        except Exception as e:
            print(f"Error getting full task: {e}")
            raise

# Data models for type safety
class Wallet(BaseModel):
    id: str
    name: str
    role: str
    eth_address: str
    sol_address: str
    budget_cap: float
    balance: float
    api_key_id: str
    created_at: str

class Task(BaseModel):
    id: str
    description: str
    total_budget: float
    status: str
    coordinator_wallet_id: str
    created_at: str

class SubTask(BaseModel):
    id: str
    task_id: str
    agent_id: str
    wallet_id: str
    description: str
    budget_allocated: float
    status: str
    output: Optional[str] = None
    created_at: str

class Payment(BaseModel):
    id: str
    from_wallet_id: str
    to_wallet_id: str
    amount: float
    chain_id: str
    status: str
    policy_reason: Optional[str] = None
    tx_hash: Optional[str] = None
    created_at: str

class AuditLog(BaseModel):
    id: str
    event_type: str
    entity_id: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: str
