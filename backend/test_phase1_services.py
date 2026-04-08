#!/usr/bin/env python3
"""
Phase 1 Services Test Script

Tests the Claude Code Service Layer implementation:
- Service Manager
- Payment Verification Service  
- X402 Proxy Service
- Balance Service

Usage:
    python test_phase1_services.py
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from services.service_manager import service_manager, ServiceState
from services.payment_verification_service import payment_verification_service, PaymentData
from services.x402_proxy_service import x402_proxy_service, ProxyRequest, ProxyServiceType
from services.balance_service import balance_service
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

class Phase1Tester:
    """Test suite for Phase 1 services"""
    
    def __init__(self):
        self.test_results = {
            'service_manager': False,
            'payment_verification': False,
            'x402_proxy': False,
            'balance_service': False
        }
    
    async def test_service_manager(self):
        """Test Service Manager functionality"""
        logger.info("Testing Service Manager...")
        
        try:
            # Test service registration
            await service_manager.register_service(payment_verification_service)
            await service_manager.register_service(x402_proxy_service)
            await service_manager.register_service(balance_service)
            
            # Test service status
            status_list = service_manager.get_service_status()
            assert len(status_list) >= 3, "Should have at least 3 services registered"
            
            # Test service access
            payment_service = service_manager.get_service("payment-verification")
            assert payment_service is not None, "Should be able to get payment service"
            
            # Test service state check
            assert service_manager.is_service_running("payment-verification") == False, "Service should not be running yet"
            
            logger.info("Service Manager test passed")
            self.test_results['service_manager'] = True
            return True
            
        except Exception as error:
            logger.error(f"Service Manager test failed: {error}")
            return False
    
    async def test_payment_verification_service(self):
        """Test Payment Verification Service"""
        logger.info("Testing Payment Verification Service...")
        
        try:
            # Test service initialization
            await payment_verification_service.initialize()
            assert payment_verification_service.state == ServiceState.REGISTERED, "Service should be registered"
            
            # Test payment data creation
            payment_data = PaymentData(
                tx_hash="test_tx_hash_123",
                task_id="test_task_123",
                agent_id="test_agent_123",
                expected_amount_sol=Decimal("0.001"),
                recipient="test_recipient_address",
                timestamp=asyncio.get_event_loop().time()
            )
            
            # Test verification queue (should not fail)
            await payment_verification_service.queue_verification(payment_data)
            
            # Test statistics
            stats = payment_verification_service.stats
            assert 'total_verified' in stats, "Should have statistics"
            
            logger.info("Payment Verification Service test passed")
            self.test_results['payment_verification'] = True
            return True
            
        except Exception as error:
            logger.error(f"Payment Verification Service test failed: {error}")
            return False
    
    async def test_x402_proxy_service(self):
        """Test X402 Proxy Service"""
        logger.info("Testing X402 Proxy Service...")
        
        try:
            # Test service initialization
            await x402_proxy_service.initialize()
            assert x402_proxy_service.state == ServiceState.REGISTERED, "Service should be registered"
            
            # Test service configuration
            deepseek_config = x402_proxy_service.get_service_config(ProxyServiceType.DEEPSEEK)
            assert 'base_url' in deepseek_config, "Should have service configuration"
            assert deepseek_config['cost_per_call'] > 0, "Should have cost per call"
            
            # Test statistics
            stats = x402_proxy_service.get_statistics()
            assert 'total_requests' in stats, "Should have statistics"
            assert 'services_count' in stats, "Should have services count"
            
            logger.info("X402 Proxy Service test passed")
            self.test_results['x402_proxy'] = True
            return True
            
        except Exception as error:
            logger.error(f"X402 Proxy Service test failed: {error}")
            return False
    
    async def test_balance_service(self):
        """Test Balance Service"""
        logger.info("Testing Balance Service...")
        
        try:
            # Test service initialization
            await balance_service.initialize()
            assert balance_service.state == ServiceState.REGISTERED, "Service should be registered"
            
            # Test statistics
            stats = balance_service.get_statistics()
            assert 'total_queries' in stats, "Should have statistics"
            assert 'cache_size' in stats, "Should have cache size"
            
            # Test cache operations
            await balance_service.invalidate_all_cache()
            cache_size_after_clear = balance_service.get_statistics()['cache_size']
            assert cache_size_after_clear == 0, "Cache should be empty after clear"
            
            logger.info("Balance Service test passed")
            self.test_results['balance_service'] = True
            return True
            
        except Exception as error:
            logger.error(f"Balance Service test failed: {error}")
            return False
    
    async def test_service_integration(self):
        """Test service integration"""
        logger.info("Testing Service Integration...")
        
        try:
            # Start all services
            await service_manager.start_all_services()
            
            # Wait a moment for services to start
            await asyncio.sleep(2)
            
            # Check service status
            status_list = service_manager.get_service_status()
            running_services = [s for s in status_list if s.state == ServiceState.RUNNING]
            
            if len(running_services) >= 2:  # At least 2 services should be running
                logger.info(f"Service Integration test passed - {len(running_services)} services running")
                return True
            else:
                logger.warning(f"Only {len(running_services)} services running, expected at least 2")
                return False
                
        except Exception as error:
            logger.error(f"Service Integration test failed: {error}")
            return False
        finally:
            # Stop services
            await service_manager.stop_all_services()
    
    async def run_all_tests(self):
        """Run all Phase 1 tests"""
        logger.info("Starting Phase 1 Services Test Suite...")
        
        tests = [
            self.test_service_manager,
            self.test_payment_verification_service,
            self.test_x402_proxy_service,
            self.test_balance_service,
            self.test_service_integration
        ]
        
        for test in tests:
            try:
                result = await test()
                if not result:
                    logger.error(f"Test {test.__name__} failed")
            except Exception as error:
                logger.error(f"Test {test.__name__} crashed: {error}")
        
        # Print results
        logger.info("\n=== PHASE 1 TEST RESULTS ===")
        for test_name, passed in self.test_results.items():
            status = "PASS" if passed else "FAIL"
            logger.info(f"{test_name}: {status}")
        
        total_tests = len(self.test_results)
        passed_tests = sum(self.test_results.values())
        
        logger.info(f"\nSummary: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            logger.info("All Phase 1 tests PASSED! Implementation is ready.")
            return True
        else:
            logger.error("Some Phase 1 tests FAILED. Check implementation.")
            return False

async def main():
    """Main test runner"""
    # Set minimal environment for testing
    os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')
    os.environ.setdefault('ENVIRONMENT', 'development')
    
    tester = Phase1Tester()
    success = await tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
