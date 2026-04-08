"""
Payment Verification Service - Claude Code Service Layer Pattern

Fixes B5: x402 payments shown in UI are LLM-generated, not verified on-chain.
Implements real-time on-chain verification using Claude Code Service pattern.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from decimal import Decimal

from services.service_manager import Service, ServiceState
from services.solana_service import solana_service
from services.pocketbase import pb

logger = logging.getLogger(__name__)

class VerificationStatus(Enum):
    """Payment verification status"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    NOT_FOUND = "not_found"
    INVALID = "invalid"

@dataclass
class PaymentData:
    """Payment data for verification"""
    tx_hash: str
    task_id: str
    agent_id: str
    expected_amount_sol: Decimal
    recipient: str
    timestamp: float

@dataclass
class VerificationResult:
    """Result of payment verification"""
    tx_hash: str
    status: VerificationStatus
    actual_amount: Optional[Decimal]
    confirmed_at: Optional[float]
    error_message: Optional[str]
    solscan_url: str

class PaymentVerificationService(Service):
    """
    Payment Verification Service implementing Claude Code Service pattern
    
    Provides real-time on-chain verification of x402 payments to eliminate
    LLM-generated fake payments in the UI.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "payment-verification"
        self.version = "1.0.0"
        self.auto_start = True
        
        # Verification queue and processing
        self.verification_queue = asyncio.Queue()
        self.verification_task: Optional[asyncio.Task] = None
        self.verification_results: Dict[str, VerificationResult] = {}
        
        # Configuration
        self.verification_timeout = 60  # 60 seconds
        self.max_retries = 3
        self.retry_delay = 5  # 5 seconds
        
        # Statistics
        self.stats = {
            'total_verified': 0,
            'successful': 0,
            'failed': 0,
            'average_verification_time': 0.0
        }
    
    async def initialize(self) -> None:
        """Initialize verification service"""
        logger.info("Initializing Payment Verification Service...")
        
        # Test Solana connection
        if not solana_service._available:
            logger.warning("Solana service not available, verification will be limited")
        
        # Initialize verification results cache
        self.verification_results.clear()
        
        logger.info("Payment Verification Service initialized")
    
    async def start(self) -> None:
        """Start the verification service"""
        logger.info("Starting Payment Verification Service...")
        
        # Start verification loop
        self.verification_task = asyncio.create_task(self._verification_loop())
        
        # Start cleanup task for old results
        asyncio.create_task(self._cleanup_loop())
        
        logger.info("Payment Verification Service started")
    
    async def stop(self) -> None:
        """Stop the verification service"""
        logger.info("Stopping Payment Verification Service...")
        
        # Cancel verification task
        if self.verification_task:
            self.verification_task.cancel()
            try:
                await self.verification_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Payment Verification Service stopped")
    
    async def health_check(self) -> bool:
        """Check service health"""
        try:
            # Check if verification loop is running
            if not self.verification_task or self.verification_task.done():
                return False
            
            # Check Solana service availability
            return solana_service._available
        except Exception as error:
            logger.error(f"Health check failed: {error}")
            return False
    
    async def queue_verification(self, payment_data: PaymentData) -> None:
        """Queue payment for verification"""
        await self.verification_queue.put(payment_data)
        logger.debug(f"Queued verification for payment {payment_data.tx_hash}")
    
    async def verify_payment_immediate(self, payment_data: PaymentData) -> VerificationResult:
        """Verify payment immediately (synchronous)"""
        return await self._verify_payment_on_chain(payment_data)
    
    async def get_verification_status(self, tx_hash: str) -> Optional[VerificationResult]:
        """Get verification status for a payment"""
        return self.verification_results.get(tx_hash)
    
    async def get_verified_payments(self, limit: int = 100) -> List[VerificationResult]:
        """Get list of verified payments"""
        verified = [
            result for result in self.verification_results.values()
            if result.status == VerificationStatus.CONFIRMED
        ]
        
        # Sort by confirmation time (newest first)
        verified.sort(key=lambda x: x.confirmed_at or 0, reverse=True)
        
        return verified[:limit]
    
    async def _verification_loop(self) -> None:
        """Main verification processing loop"""
        logger.info("Payment verification loop started")
        
        while True:
            try:
                # Get payment from queue
                payment_data = await self.verification_queue.get()
                
                # Verify payment
                result = await self._verify_payment_on_chain(payment_data)
                
                # Store result
                self.verification_results[payment_data.tx_hash] = result
                
                # Update statistics
                self._update_stats(result)
                
                # Log result
                if result.status == VerificationStatus.CONFIRMED:
                    logger.info(f"Payment verified: {payment_data.tx_hash}")
                else:
                    logger.warning(f"Payment verification failed: {payment_data.tx_hash} - {result.error_message}")
                
                # Mark task as done
                self.verification_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.error(f"Verification loop error: {error}")
                await asyncio.sleep(1)
    
    async def _verify_payment_on_chain(self, payment_data: PaymentData) -> VerificationResult:
        """Verify payment on Solana blockchain"""
        start_time = time.time()
        
        try:
            # Get transaction from Solana
            tx = await solana_service.get_transaction(payment_data.tx_hash)
            
            if not tx:
                return VerificationResult(
                    tx_hash=payment_data.tx_hash,
                    status=VerificationStatus.NOT_FOUND,
                    actual_amount=None,
                    confirmed_at=None,
                    error_message="Transaction not found on-chain",
                    solscan_url=solana_service.explorer_url(payment_data.tx_hash)
                )
            
            # Extract transaction details
            actual_amount = self._extract_amount(tx)
            memo = self._extract_memo(tx)
            
            # Verify transaction details
            validation_errors = []
            
            # Check amount
            if actual_amount != payment_data.expected_amount_sol:
                validation_errors.append(f"Amount mismatch: expected {payment_data.expected_amount_sol}, got {actual_amount}")
            
            # Check recipient
            if not self._verify_recipient(tx, payment_data.recipient):
                validation_errors.append("Recipient mismatch")
            
            # Check memo (should contain task_id)
            if memo and payment_data.task_id not in memo:
                validation_errors.append(f"Task ID mismatch: expected {payment_data.task_id} in memo")
            
            # Determine status
            if validation_errors:
                return VerificationResult(
                    tx_hash=payment_data.tx_hash,
                    status=VerificationStatus.INVALID,
                    actual_amount=actual_amount,
                    confirmed_at=time.time(),
                    error_message="; ".join(validation_errors),
                    solscan_url=solana_service.explorer_url(payment_data.tx_hash)
                )
            else:
                # Update database with confirmed payment
                await self._update_payment_record(payment_data, VerificationStatus.CONFIRMED)
                
                return VerificationResult(
                    tx_hash=payment_data.tx_hash,
                    status=VerificationStatus.CONFIRMED,
                    actual_amount=actual_amount,
                    confirmed_at=time.time(),
                    error_message=None,
                    solscan_url=solana_service.explorer_url(payment_data.tx_hash)
                )
        
        except Exception as error:
            logger.error(f"On-chain verification failed for {payment_data.tx_hash}: {error}")
            
            # Update database with failed status
            await self._update_payment_record(payment_data, VerificationStatus.FAILED)
            
            return VerificationResult(
                tx_hash=payment_data.tx_hash,
                status=VerificationStatus.FAILED,
                actual_amount=None,
                confirmed_at=None,
                error_message=str(error),
                solscan_url=solana_service.explorer_url(payment_data.tx_hash)
            )
        
        finally:
            # Update verification time statistics
            verification_time = time.time() - start_time
            self.stats['total_verified'] += 1
            self.stats['average_verification_time'] = (
                (self.stats['average_verification_time'] * (self.stats['total_verified'] - 1) + verification_time) /
                self.stats['total_verified']
            )
    
    def _extract_amount(self, tx: Dict[str, Any]) -> Optional[Decimal]:
        """Extract SOL amount from transaction"""
        try:
            # Extract from transaction meta data
            if 'meta' in tx and 'postBalances' in tx['meta'] and 'preBalances' in tx['meta']:
                pre_balances = tx['meta']['preBalances']
                post_balances = tx['meta']['postBalances']
                
                # Find the first balance change (simplified)
                for i, (pre, post) in enumerate(zip(pre_balances, post_balances)):
                    if pre != post:
                        diff = int(post) - int(pre)
                        if diff < 0:  # SOL sent
                            return Decimal(str(abs(diff) / 1e9))  # Convert lamports to SOL
            
            return None
        except Exception as error:
            logger.error(f"Failed to extract amount: {error}")
            return None
    
    def _extract_memo(self, tx: Dict[str, Any]) -> Optional[str]:
        """Extract memo from transaction"""
        try:
            # Look for memo instruction in transaction
            if 'transaction' in tx and 'message' in tx['transaction']:
                message = tx['transaction']['message']
                if 'instructions' in message:
                    for instruction in message['instructions']:
                        if 'programIdIndex' in instruction:
                            # Check if this is a memo program
                            if instruction.get('programIdIndex') == 4:  # Memo program index
                                # Extract memo data
                                if 'data' in instruction:
                                    import base64
                                    memo_data = base64.b64decode(instruction['data']).decode('utf-8')
                                    return memo_data
            
            return None
        except Exception as error:
            logger.error(f"Failed to extract memo: {error}")
            return None
    
    def _verify_recipient(self, tx: Dict[str, Any], expected_recipient: str) -> bool:
        """Verify transaction recipient"""
        try:
            # Extract recipient from transaction
            if 'transaction' in tx and 'message' in tx['transaction']:
                message = tx['transaction']['message']
                if 'accountKeys' in message:
                    # First account is usually the sender, second is recipient
                    accounts = message['accountKeys']
                    if len(accounts) >= 2:
                        recipient = accounts[1]  # Simplified - might need more complex logic
                        return recipient == expected_recipient
            
            return False
        except Exception as error:
            logger.error(f"Failed to verify recipient: {error}")
            return False
    
    async def _update_payment_record(self, payment_data: PaymentData, status: VerificationStatus) -> None:
        """Update payment record in database"""
        try:
            # Update x402_calls table with verification status
            update_data = {
                'status': status.value,
                'verified_at': time.time() if status == VerificationStatus.CONFIRMED else None
            }
            
            from services.pocketbase import _safe_filter
            # Find existing record
            records = await asyncio.to_thread(
                pb.list, 'x402_calls', filter_params=_safe_filter('solscan_tx', payment_data.tx_hash)
            )
            
            if records:
                await asyncio.to_thread(pb.update, 'x402_calls', records[0]["id"], update_data)
            else:
                # Create new record if not exists
                new_record = {
                    'task_id': payment_data.task_id,
                    'agent_id': payment_data.agent_id,
                    'service_name': 'x402_proxy',
                    'solscan_tx': payment_data.tx_hash,
                    'status': status.value,
                    'amount_sol': float(payment_data.expected_amount_sol),
                }
                
                await asyncio.to_thread(pb.create, 'x402_calls', new_record)
        
        except Exception as error:
            logger.error(f"Failed to update payment record: {error}")
    
    def _update_stats(self, result: VerificationResult) -> None:
        """Update verification statistics"""
        if result.status == VerificationStatus.CONFIRMED:
            self.stats['successful'] += 1
        else:
            self.stats['failed'] += 1
    
    async def _cleanup_loop(self) -> None:
        """Cleanup old verification results"""
        while True:
            try:
                # Remove results older than 1 hour
                cutoff_time = time.time() - 3600
                
                to_remove = [
                    tx_hash for tx_hash, result in self.verification_results.items()
                    if (result.confirmed_at or 0) < cutoff_time
                ]
                
                for tx_hash in to_remove:
                    del self.verification_results[tx_hash]
                
                if to_remove:
                    logger.debug(f"Cleaned up {len(to_remove)} old verification results")
                
                await asyncio.sleep(300)  # Run every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.error(f"Cleanup loop error: {error}")
                await asyncio.sleep(60)

# Global service instance
payment_verification_service = PaymentVerificationService()
