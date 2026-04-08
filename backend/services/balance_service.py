"""
Balance Service - Claude Code Service Layer Pattern

Fixes B7: Coordinator wallet balance in DB not decremented after payments.
Implements real-time balance queries from Solana RPC with caching.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from services.service_manager import Service, ServiceState
from services.solana_service import solana_service

logger = logging.getLogger(__name__)

@dataclass
class BalanceInfo:
    """Balance information for an address"""
    address: str
    balance_sol: Decimal
    balance_usd: Optional[Decimal]
    last_updated: float
    block_height: Optional[int]

class BalanceService(Service):
    """
    Balance Service implementing Claude Code Service pattern
    
    Provides real-time balance queries from Solana RPC with intelligent
    caching to eliminate stale balance issues.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "balance-service"
        self.version = "1.0.0"
        self.auto_start = True
        
        # Balance cache
        self.balance_cache: Dict[str, BalanceInfo] = {}
        self.cache_ttl = 30  # 30 seconds cache TTL
        
        # Rate limiting
        self.rate_limit_interval = 1.0  # 1 second between queries
        self.last_query_time = 0.0
        
        # Statistics
        self.stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'failed_queries': 0,
            'average_query_time': 0.0
        }
    
    async def initialize(self) -> None:
        """Initialize balance service"""
        logger.info("Initializing Balance Service...")
        
        # Test Solana connection
        if not solana_service._available:
            logger.warning("Solana service not available, balance queries will be limited")
        
        # Clear cache
        self.balance_cache.clear()
        
        logger.info("Balance Service initialized")
    
    async def start(self) -> None:
        """Start the balance service"""
        logger.info("Starting Balance Service...")
        
        # Start cache cleanup task
        asyncio.create_task(self._cache_cleanup_loop())
        
        logger.info("Balance Service started")
    
    async def stop(self) -> None:
        """Stop the balance service"""
        logger.info("Stopping Balance Service...")
        
        # Clear cache
        self.balance_cache.clear()
        
        logger.info("Balance Service stopped")
    
    async def health_check(self) -> bool:
        """Check service health"""
        try:
            # Test Solana service availability
            return solana_service._available
        except Exception as error:
            logger.error(f"Health check failed: {error}")
            return False
    
    async def get_balance(self, address: str, force_refresh: bool = False) -> BalanceInfo:
        """
        Get real-time balance from Solana RPC with caching
        
        Args:
            address: Solana address to query
            force_refresh: Force refresh from RPC, ignoring cache
        
        Returns:
            BalanceInfo object with balance details
        """
        start_time = time.time()
        
        try:
            # Update statistics
            self.stats['total_queries'] += 1
            
            # Check cache first (unless force refresh)
            if not force_refresh:
                cached_balance = self._get_from_cache(address)
                if cached_balance:
                    self.stats['cache_hits'] += 1
                    return cached_balance
            
            self.stats['cache_misses'] += 1
            
            # Rate limiting
            await self._rate_limit()
            
            # Query from Solana RPC
            balance_info = await self._query_balance_from_rpc(address)
            
            # Cache the result
            self._cache_balance(address, balance_info)
            
            # Update query time statistics
            query_time = time.time() - start_time
            self.stats['average_query_time'] = (
                (self.stats['average_query_time'] * (self.stats['total_queries'] - 1) + query_time) /
                self.stats['total_queries']
            )
            
            return balance_info
        
        except Exception as error:
            logger.error(f"Failed to get balance for {address}: {error}")
            self.stats['failed_queries'] += 1
            
            # Return cached balance if available (even if stale)
            cached_balance = self._get_from_cache(address, ignore_ttl=True)
            if cached_balance:
                logger.warning(f"Returning stale cached balance for {address}")
                return cached_balance
            
            # Return zero balance as fallback
            return BalanceInfo(
                address=address,
                balance_sol=Decimal('0'),
                balance_usd=None,
                last_updated=time.time(),
                block_height=None
            )
    
    async def get_multiple_balances(self, addresses: list[str]) -> Dict[str, BalanceInfo]:
        """Get balances for multiple addresses in parallel"""
        # Create parallel tasks
        tasks = [self.get_balance(address) for address in addresses]
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build results dictionary
        balances = {}
        for address, result in zip(addresses, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get balance for {address}: {result}")
                balances[address] = BalanceInfo(
                    address=address,
                    balance_sol=Decimal('0'),
                    balance_usd=None,
                    last_updated=time.time(),
                    block_height=None
                )
            else:
                balances[address] = result
        
        return balances
    
    async def invalidate_cache(self, address: str) -> None:
        """Invalidate cache for a specific address"""
        if address in self.balance_cache:
            del self.balance_cache[address]
            logger.debug(f"Invalidated cache for {address}")
    
    async def invalidate_all_cache(self) -> None:
        """Invalidate all cached balances"""
        self.balance_cache.clear()
        logger.info("Invalidated all balance cache")
    
    async def check_budget_cap(self, coordinator_address: str, amount: Decimal) -> bool:
        """
        Check if coordinator has sufficient balance (OWS budget cap rule)
        
        Args:
            coordinator_address: Address of coordinator wallet
            amount: Amount to check against balance
        
        Returns:
            True if sufficient balance, False otherwise
        """
        try:
            balance_info = await self.get_balance(coordinator_address)
            return balance_info.balance_sol >= amount
        except Exception as error:
            logger.error(f"Budget cap check failed: {error}")
            return False
    
    async def get_balance_with_usd(self, address: str) -> BalanceInfo:
        """Get balance with USD conversion"""
        balance_info = await self.get_balance(address)
        
        # Add USD conversion if not present
        if balance_info.balance_usd is None:
            try:
                # Get SOL/USD rate (you might want to cache this too)
                usd_rate = await self._get_sol_usd_rate()
                balance_info.balance_usd = balance_info.balance_sol * usd_rate
            except Exception as error:
                logger.warning(f"Failed to get USD rate: {error}")
                balance_info.balance_usd = None
        
        return balance_info
    
    def _get_from_cache(self, address: str, ignore_ttl: bool = False) -> Optional[BalanceInfo]:
        """Get balance from cache"""
        cached = self.balance_cache.get(address)
        if not cached:
            return None
        
        # Check TTL unless ignored
        if not ignore_ttl and (time.time() - cached.last_updated) > self.cache_ttl:
            del self.balance_cache[address]
            return None
        
        return cached
    
    def _cache_balance(self, address: str, balance_info: BalanceInfo) -> None:
        """Cache balance information"""
        self.balance_cache[address] = balance_info
    
    async def _rate_limit(self) -> None:
        """Rate limit RPC queries"""
        now = time.time()
        time_since_last = now - self.last_query_time
        
        if time_since_last < self.rate_limit_interval:
            await asyncio.sleep(self.rate_limit_interval - time_since_last)
        
        self.last_query_time = time.time()
    
    async def _query_balance_from_rpc(self, address: str) -> BalanceInfo:
        """Query balance from Solana RPC"""
        try:
            # Get balance in lamports
            balance_lamports = await solana_service.get_balance(address)
            balance_sol = Decimal(str(balance_lamports)) / Decimal('1e9')
            
            # Get block height for freshness
            block_height = await solana_service.get_block_height() if solana_service._available else None
            
            return BalanceInfo(
                address=address,
                balance_sol=balance_sol,
                balance_usd=None,  # Will be calculated on demand
                last_updated=time.time(),
                block_height=block_height
            )
        
        except Exception as error:
            logger.error(f"RPC query failed for {address}: {error}")
            raise
    
    async def _get_sol_usd_rate(self) -> Decimal:
        """Get SOL/USD exchange rate"""
        try:
            # Try to get from Meteora service
            from services.meteora_service import meteora_service
            rate = await meteora_service.get_sol_usdc_rate()
            return Decimal(str(rate))
        except Exception as error:
            logger.warning(f"Failed to get SOL/USD rate from Meteora: {error}")
            
            # Fallback to hardcoded rate (should be replaced with MoonPay in Phase 2)
            return Decimal('79.0')  # This is the hardcoded rate mentioned in B6
    
    async def _cache_cleanup_loop(self) -> None:
        """Background task to clean up expired cache entries"""
        while True:
            try:
                now = time.time()
                expired_keys = []
                
                for address, balance_info in self.balance_cache.items():
                    if (now - balance_info.last_updated) > self.cache_ttl:
                        expired_keys.append(address)
                
                for key in expired_keys:
                    del self.balance_cache[key]
                
                if expired_keys:
                    logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
                
                await asyncio.sleep(60)  # Run every minute
                
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.error(f"Cache cleanup error: {error}")
                await asyncio.sleep(60)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            **self.stats,
            'cache_size': len(self.balance_cache),
            'cache_ttl': self.cache_ttl,
            'cache_hit_rate': (
                self.stats['cache_hits'] / max(self.stats['total_queries'], 1)
            )
        }

# Global service instance
balance_service = BalanceService()
