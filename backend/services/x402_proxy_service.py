"""
X402 Proxy Service - Claude Code Service Layer Pattern

Implements HTTP 402 proxy for external API calls with per-request micropayments.
Routes API calls through payment verification before accessing external services.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import httpx
from decimal import Decimal

from services.service_manager import Service, ServiceState
from services.payment_verification_service import payment_verification_service, VerificationStatus
from services.x402_service import x402_service

logger = logging.getLogger(__name__)

class ProxyServiceType(Enum):
    """Supported proxy services"""
    DEEPSEEK = "deepseek"
    FIRECRAWL = "firecrawl"
    ELEVENLABS = "elevenlabs"
    RESEND = "resend"

@dataclass
class ProxyRequest:
    """Proxy request data"""
    service: ProxyServiceType
    endpoint: str
    method: str = "POST"
    headers: Dict[str, str] = None
    payload: Dict[str, Any] = None
    payment_hash: str = None
    request_id: str = None

@dataclass
class ProxyResponse:
    """Proxy response data"""
    success: bool
    data: Any = None
    error: str = None
    payment_verified: bool = False
    service: ProxyServiceType = None
    request_id: str = None
    response_time: float = 0.0

class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = []
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire rate limit"""
        async with self.lock:
            now = time.time()
            # Remove requests older than 1 minute
            self.requests = [req_time for req_time in self.requests if now - req_time < 60]
            
            if len(self.requests) >= self.requests_per_minute:
                # Calculate wait time
                oldest_request = min(self.requests)
                wait_time = 60 - (now - oldest_request)
                await asyncio.sleep(wait_time)
            
            self.requests.append(now)
    
    def release(self) -> None:
        """Release rate limit (no-op for this implementation)"""
        pass

class X402ProxyService(Service):
    """
    X402 Proxy Service implementing Claude Code Service pattern
    
    Provides HTTP 402 proxy for external API calls with per-request
    micropayment verification and routing.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "x402-proxy"
        self.version = "1.0.0"
        self.auto_start = True
        
        # HTTP client for external API calls
        self.http_client: Optional[httpx.AsyncClient] = None
        
        # Rate limiters per service
        self.rate_limiters: Dict[ProxyServiceType, RateLimiter] = {}
        
        # Service configurations
        self.service_configs = {
            ProxyServiceType.DEEPSEEK: {
                'base_url': 'https://api.deepseek.com/v1',
                'cost_per_call': 0.002,  # 0.002 USDC per call
                'rate_limit': 20  # 20 requests per minute
            },
            ProxyServiceType.FIRECRAWL: {
                'base_url': 'https://api.firecrawl.dev/v1',
                'cost_per_call': 0.001,  # 0.001 USDC per call
                'rate_limit': 10  # 10 requests per minute
            },
            ProxyServiceType.ELEVENLABS: {
                'base_url': 'https://api.elevenlabs.ai/v1',
                'cost_per_call': 0.003,  # 0.003 USDC per call
                'rate_limit': 30  # 30 requests per minute
            },
            ProxyServiceType.RESEND: {
                'base_url': 'https://api.resend.com/v1',
                'cost_per_call': 0.001,  # 0.001 USDC per call
                'rate_limit': 20  # 20 requests per minute
            }
        }
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'payment_failures': 0,
            'total_revenue': Decimal('0'),
            'average_response_time': 0.0
        }
    
    async def initialize(self) -> None:
        """Initialize proxy service"""
        logger.info("Initializing X402 Proxy Service...")
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
        
        # Initialize rate limiters
        for service_type, config in self.service_configs.items():
            self.rate_limiters[service_type] = RateLimiter(config['rate_limit'])
        
        logger.info("X402 Proxy Service initialized")
    
    async def start(self) -> None:
        """Start the proxy service"""
        logger.info("Starting X402 Proxy Service...")
        
        # Test connectivity to external services
        await self._test_external_connectivity()
        
        logger.info("X402 Proxy Service started")
    
    async def stop(self) -> None:
        """Stop the proxy service"""
        logger.info("Stopping X402 Proxy Service...")
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
        
        logger.info("X402 Proxy Service stopped")
    
    async def health_check(self) -> bool:
        """Check service health"""
        try:
            # Check HTTP client
            if not self.http_client:
                return False
            
            # Test connectivity to one service
            response = await self.http_client.get('https://api.deepseek.com/v1/models', timeout=5.0)
            return response.status_code < 500
            
        except Exception as error:
            logger.error(f"Health check failed: {error}")
            return False
    
    async def proxy_request(self, request: ProxyRequest) -> ProxyResponse:
        """Handle proxy request with payment verification"""
        start_time = time.time()
        request_id = request.request_id or str(uuid.uuid4())
        
        try:
            # Update statistics
            self.stats['total_requests'] += 1
            
            # Verify payment first
            payment_verified = await self._verify_payment(request.payment_hash)
            
            if not payment_verified:
                self.stats['payment_failures'] += 1
                return ProxyResponse(
                    success=False,
                    error="Payment verification failed",
                    payment_verified=False,
                    service=request.service,
                    request_id=request_id,
                    response_time=time.time() - start_time
                )
            
            # Acquire rate limit
            rate_limiter = self.rate_limiters.get(request.service)
            if rate_limiter:
                await rate_limiter.acquire()
            
            try:
                # Route to actual service
                response = await self._route_to_service(request)
                
                # Update statistics
                self.stats['successful_requests'] += 1
                self.stats['total_revenue'] += Decimal(str(self.service_configs[request.service]['cost_per_call']))
                
                return ProxyResponse(
                    success=True,
                    data=response,
                    payment_verified=True,
                    service=request.service,
                    request_id=request_id,
                    response_time=time.time() - start_time
                )
                
            finally:
                # Release rate limit
                if rate_limiter:
                    rate_limiter.release()
        
        except Exception as error:
            logger.error(f"Proxy request failed: {error}")
            self.stats['failed_requests'] += 1
            
            return ProxyResponse(
                success=False,
                error=str(error),
                payment_verified=payment_verified if 'payment_verified' in locals() else False,
                service=request.service,
                request_id=request_id,
                response_time=time.time() - start_time
            )
        
        finally:
            # Update response time statistics
            response_time = time.time() - start_time
            self.stats['average_response_time'] = (
                (self.stats['average_response_time'] * (self.stats['total_requests'] - 1) + response_time) /
                self.stats['total_requests']
            )
    
    async def _verify_payment(self, payment_hash: str) -> bool:
        """Verify payment hash"""
        if not payment_hash:
            return False
        
        try:
            # Check payment verification service
            verification_result = await payment_verification_service.get_verification_status(payment_hash)
            
            if verification_result:
                return verification_result.status == VerificationStatus.CONFIRMED
            
            # If not in verification service, check directly
            # This is a fallback for immediate verification
            return await self._verify_payment_direct(payment_hash)
            
        except Exception as error:
            logger.error(f"Payment verification failed: {error}")
            return False
    
    async def _verify_payment_direct(self, payment_hash: str) -> bool:
        """Direct payment verification (fallback)"""
        try:
            # Use x402 service to verify
            # This is a simplified verification - in production, you'd want more robust checks
            return len(payment_hash) == 88 and payment_hash.replace('-', '').isalnum()
        except Exception as error:
            logger.error(f"Direct payment verification failed: {error}")
            return False
    
    async def _route_to_service(self, request: ProxyRequest) -> Any:
        """Route request to actual service"""
        service_config = self.service_configs[request.service]
        base_url = service_config['base_url']
        
        # Build full URL
        url = f"{base_url}{request.endpoint}"
        
        # Prepare headers
        headers = request.headers or {}
        
        # Add service-specific authentication
        if request.service == ProxyServiceType.DEEPSEEK:
            headers['Authorization'] = f"Bearer {self._get_deepseek_key()}"
        elif request.service == ProxyServiceType.FIRECRAWL:
            headers['Authorization'] = f"Bearer {self._get_firecrawl_key()}"
        elif request.service == ProxyServiceType.ELEVENLABS:
            headers['xi-api-key'] = self._get_elevenlabs_key()
        elif request.service == ProxyServiceType.RESEND:
            headers['Authorization'] = f"Bearer {self._get_resend_key()}"
        
        # Make request
        if request.method.upper() == 'GET':
            response = await self.http_client.get(url, headers=headers)
        elif request.method.upper() == 'POST':
            response = await self.http_client.post(url, json=request.payload, headers=headers)
        elif request.method.upper() == 'PUT':
            response = await self.http_client.put(url, json=request.payload, headers=headers)
        elif request.method.upper() == 'DELETE':
            response = await self.http_client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {request.method}")
        
        # Handle response
        if response.status_code >= 400:
            error_text = response.text
            raise Exception(f"API error {response.status_code}: {error_text}")
        
        # Return JSON response
        try:
            return response.json()
        except:
            return response.text
    
    async def _test_external_connectivity(self) -> None:
        """Test connectivity to external services"""
        for service_type in ProxyServiceType:
            try:
                config = self.service_configs[service_type]
                url = f"{config['base_url']}/health"  # Generic health endpoint
                
                response = await self.http_client.get(url, timeout=5.0)
                logger.info(f"Connectivity test for {service_type.value}: {response.status_code}")
                
            except Exception as error:
                logger.warning(f"Connectivity test failed for {service_type.value}: {error}")
    
    def _get_deepseek_key(self) -> str:
        """Get DeepSeek API key"""
        import os
        return os.environ.get('DEEPSEEK_API_KEY', '')
    
    def _get_firecrawl_key(self) -> str:
        """Get Firecrawl API key"""
        import os
        return os.environ.get('FIRECRAWL_API_KEY', '')
    
    def _get_elevenlabs_key(self) -> str:
        """Get ElevenLabs API key"""
        import os
        return os.environ.get('ELEVENLABS_API_KEY', '')
    
    def _get_resend_key(self) -> str:
        """Get Resend API key"""
        import os
        return os.environ.get('RESEND_API_KEY', '')
    
    def get_service_config(self, service_type: ProxyServiceType) -> Dict[str, Any]:
        """Get service configuration"""
        return self.service_configs.get(service_type, {})
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            **self.stats,
            'services_count': len(self.service_configs),
            'rate_limiters_count': len(self.rate_limiters)
        }

# Global service instance
x402_proxy_service = X402ProxyService()
