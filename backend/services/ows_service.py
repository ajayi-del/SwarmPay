"""
OWS Service - Handles all Open Wallet Standard operations
"""

import subprocess
import json
import uuid
import base64
import os
from typing import Dict, Any, Optional
from datetime import datetime

class OWSService:
    def __init__(self):
        self.base_url = "http://localhost:8080"  # OWS daemon default
    
    def create_wallet(self, name: str) -> Dict[str, Any]:
        """Create a new OWS wallet"""
        try:
            # Try OWS Python SDK first
            try:
                from open_wallet_standard import Wallet
                wallet = Wallet.create(name=name)
                return {
                    "id": wallet.id,
                    "name": wallet.name,
                    "eth_address": wallet.eth_address,
                    "sol_address": wallet.sol_address
                }
            except ImportError:
                # Fallback to subprocess
                result = subprocess.run([
                    "ows", "wallet", "create", 
                    "--name", name, 
                    "--output", "json"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    wallet_data = json.loads(result.stdout)
                    return wallet_data
                else:
                    raise Exception(f"OWS wallet creation failed: {result.stderr}")
                    
        except Exception as e:
            print(f"Error creating OWS wallet: {e}")
            # Return mock data for demo purposes
            wallet_id = str(uuid.uuid4())
            return {
                "id": wallet_id,
                "name": name,
                "eth_address": f"0x{wallet_id[:8]}{'0' * 32}",
                "sol_address": f"{wallet_id[:8]}{'0' * 44}"
            }
    
    def create_api_key(self, wallet_id: str, budget_cap: float) -> str:
        """Create a scoped API key for a wallet"""
        try:
            # Try OWS Python SDK first
            try:
                from open_wallet_standard import APIKey
                api_key = APIKey.create(
                    wallet_id=wallet_id,
                    budget_cap=budget_cap,
                    permissions=["sign_payment"]
                )
                return api_key.key
            except ImportError:
                # Fallback to subprocess
                result = subprocess.run([
                    "ows", "api-key", "create",
                    "--wallet", wallet_id,
                    "--budget-cap", str(budget_cap),
                    "--permissions", "sign_payment",
                    "--output", "json"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    api_data = json.loads(result.stdout)
                    return api_data["key"]
                else:
                    raise Exception(f"OWS API key creation failed: {result.stderr}")
                    
        except Exception as e:
            print(f"Error creating OWS API key: {e}")
            # Return mock API key for demo purposes
            return f"ows_mock_{uuid.uuid4().hex[:32]}"
    
    def sign_payment(self, from_wallet: str, to_wallet: str, amount: float, chain_id: str = "eip155:1") -> Dict[str, Any]:
        """Sign a payment transaction"""
        try:
            # Try OWS Python SDK first
            try:
                from open_wallet_standard import Transaction
                tx = Transaction.sign_payment(
                    from_wallet=from_wallet,
                    to_wallet=to_wallet,
                    amount=amount,
                    chain_id=chain_id
                )
                return {
                    "status": "signed",
                    "tx_hash": tx.hash,
                    "chain_id": chain_id
                }
            except ImportError:
                # Fallback to subprocess
                result = subprocess.run([
                    "ows", "payment", "sign",
                    "--from", from_wallet,
                    "--to", to_wallet,
                    "--amount", str(amount),
                    "--chain", chain_id,
                    "--output", "json"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    tx_data = json.loads(result.stdout)
                    return tx_data
                else:
                    raise Exception(f"OWS payment signing failed: {result.stderr}")
                    
        except Exception as e:
            print(f"Error signing OWS payment: {e}")
            # Return mock signed transaction for demo purposes
            return {
                "status": "signed",
                "tx_hash": f"0x{uuid.uuid4().hex}",
                "chain_id": chain_id
            }
    
    def revoke_api_key(self, wallet_id: str) -> bool:
        """Revoke the OWS API key scoped to a wallet."""
        try:
            try:
                from open_wallet_standard import APIKey
                APIKey.revoke(wallet_id=wallet_id)
                return True
            except ImportError:
                result = subprocess.run(
                    ["ows", "api-key", "revoke", "--wallet", wallet_id, "--output", "json"],
                    capture_output=True, text=True,
                )
                return result.returncode == 0
        except Exception as e:
            print(f"Error revoking OWS API key for {wallet_id}: {e}")
            return True  # Treated as success in mock mode

    def get_wallet_balance(self, wallet_id: str) -> float:
        """Get wallet balance"""
        try:
            # Try OWS Python SDK first
            try:
                from open_wallet_standard import Wallet
                wallet = Wallet.get(wallet_id)
                return wallet.balance
            except ImportError:
                # Fallback to subprocess
                result = subprocess.run([
                    "ows", "wallet", "balance",
                    "--wallet", wallet_id,
                    "--output", "json"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    balance_data = json.loads(result.stdout)
                    return float(balance_data["balance"])
                else:
                    raise Exception(f"OWS balance check failed: {result.stderr}")
                    
        except Exception as e:
            print(f"Error getting OWS wallet balance: {e}")
            # Return mock balance for demo purposes
            return 1.0  # 1 ETH default for demo

    def evaluate_and_sign_lit_action(self, from_wallet: Dict[str, Any], to_wallet: Dict[str, Any], amount: float, sub_task: Dict[str, Any], reputation: float, data_to_sign: str = "mock_hash") -> Dict[str, Any]:
        """
        Executes the Lit Protocol Action (ows_policy.js) via the lit_orchestrator Node wrapper.
        Returns the policy evaluation and conditionally the signature if allowed.
        """
        try:
            payload = {
                "amount": amount,
                "sub_task": sub_task,
                "reputation": reputation,
                "from_wallet": from_wallet,
                "to_wallet": to_wallet,
                "dataToSign": data_to_sign
            }
            payload_b64 = base64.b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8')
            
            # Find orchestrator path
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            orchestrator_path = os.path.join(base_dir, "contracts", "lit_orchestrator.js")
            
            result = subprocess.run(
                ["node", orchestrator_path, payload_b64],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"Lit Orchestrator stderr: {result.stderr}")
                return {"allow": False, "reason": "Lit Execution Error", "is_probation": False}
                
            try:
                # The node script outputs JSON on the last line
                output_lines = result.stdout.strip().split('\n')
                response = json.loads(output_lines[-1])
                
                if not response.get("success"):
                    return {"allow": False, "reason": response.get("error", "Unknown Lit Error"), "is_probation": False}
                
                policy = response.get("policy_result", {})
                signature = response.get("signature")
                
                return {
                    "allow": policy.get("allow", False),
                    "reason": policy.get("reason"),
                    "is_probation": policy.get("is_probation", False),
                    "effective_cap": policy.get("effective_cap"),
                    "tx_hash": signature
                }
            except json.JSONDecodeError:
                print(f"Failed to parse Lit orchestrator output: {result.stdout}")
                return {"allow": False, "reason": "Invalid Lit Action Output", "is_probation": False}
                
        except Exception as e:
            print(f"Error calling Lit Action: {e}")
            return {"allow": False, "reason": str(e), "is_probation": False}
