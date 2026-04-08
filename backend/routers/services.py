"""
Services Router - API endpoints for Claude Code Service Layer

Provides REST API endpoints for accessing the new services:
- Payment Verification Service
- X402 Proxy Service  
- Balance Service
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel, Field

from services.service_manager import service_manager
from services.payment_verification_service import payment_verification_service, PaymentData, VerificationStatus
from services.x402_proxy_service import x402_proxy_service, ProxyRequest, ProxyServiceType
from services.balance_service import balance_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/services", tags=["services"])

# Pydantic models for API requests/responses

class PaymentVerificationRequest(BaseModel):
    """Request payment verification"""
    tx_hash: str = Field(..., description="Transaction hash to verify")
    task_id: str = Field(..., description="Associated task ID")
    agent_id: str = Field(..., description="Agent ID")
    expected_amount_sol: float = Field(..., description="Expected amount in SOL")
    recipient: str = Field(..., description="Expected recipient address")

class PaymentVerificationResponse(BaseModel):
    """Payment verification response"""
    success: bool
    tx_hash: str
    status: str
    actual_amount: Optional[float]
    confirmed_at: Optional[float]
    error_message: Optional[str]
    solscan_url: str

class ProxyRequestModel(BaseModel):
    """Proxy request model"""
    service: str = Field(..., description="Service name (deepseek, firecrawl, elevenlabs, resend)")
    endpoint: str = Field(..., description="API endpoint")
    method: str = Field(default="POST", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(None, description="Request headers")
    payload: Optional[Dict[str, Any]] = Field(None, description="Request payload")
    payment_hash: str = Field(..., description="Payment verification hash")

class BalanceResponse(BaseModel):
    """Balance response"""
    address: str
    balance_sol: float
    balance_usd: Optional[float]
    last_updated: float
    block_height: Optional[int]

class ServiceStatusResponse(BaseModel):
    """Service status response"""
    services: List[Dict[str, Any]]
    total_services: int
    running_services: int
    failed_services: int

# Payment Verification endpoints

@router.post("/payment-verification/verify", response_model=PaymentVerificationResponse)
async def verify_payment(
    request: PaymentVerificationRequest,
    background_tasks: BackgroundTasks
):
    """
    Verify payment on-chain (fixes B5)
    
    This endpoint queues a payment for verification and returns the result.
    Uses the PaymentVerificationService to check transactions on Solana blockchain.
    """
    try:
        # Create payment data
        from decimal import Decimal
        payment_data = PaymentData(
            tx_hash=request.tx_hash,
            task_id=request.task_id,
            agent_id=request.agent_id,
            expected_amount_sol=Decimal(str(request.expected_amount_sol)),
            recipient=request.recipient,
            timestamp=asyncio.get_event_loop().time()
        )
        
        # Queue for background verification
        background_tasks.add_task(
            payment_verification_service.queue_verification,
            payment_data
        )
        
        # Get immediate verification result (if available)
        result = await payment_verification_service.verify_payment_immediate(payment_data)
        
        return PaymentVerificationResponse(
            success=result.status == VerificationStatus.CONFIRMED,
            tx_hash=result.tx_hash,
            status=result.status.value,
            actual_amount=float(result.actual_amount) if result.actual_amount else None,
            confirmed_at=result.confirmed_at,
            error_message=result.error_message,
            solscan_url=result.solscan_url
        )
        
    except Exception as error:
        logger.error(f"Payment verification failed: {error}")
        raise HTTPException(status_code=500, detail=str(error))

@router.get("/payment-verification/status/{tx_hash}")
async def get_payment_verification_status(tx_hash: str):
    """Get verification status for a specific payment"""
    try:
        result = await payment_verification_service.get_verification_status(tx_hash)
        
        if not result:
            raise HTTPException(status_code=404, detail="Payment verification not found")
        
        return PaymentVerificationResponse(
            success=result.status == VerificationStatus.CONFIRMED,
            tx_hash=result.tx_hash,
            status=result.status.value,
            actual_amount=float(result.actual_amount) if result.actual_amount else None,
            confirmed_at=result.confirmed_at,
            error_message=result.error_message,
            solscan_url=result.solscan_url
        )
        
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"Failed to get payment status: {error}")
        raise HTTPException(status_code=500, detail=str(error))

@router.get("/payment-verification/verified")
async def get_verified_payments(limit: int = 100):
    """Get list of verified payments"""
    try:
        results = await payment_verification_service.get_verified_payments(limit)
        
        return [
            PaymentVerificationResponse(
                success=result.status == VerificationStatus.CONFIRMED,
                tx_hash=result.tx_hash,
                status=result.status.value,
                actual_amount=float(result.actual_amount) if result.actual_amount else None,
                confirmed_at=result.confirmed_at,
                error_message=result.error_message,
                solscan_url=result.solscan_url
            )
            for result in results
        ]
        
    except Exception as error:
        logger.error(f"Failed to get verified payments: {error}")
        raise HTTPException(status_code=500, detail=str(error))

# X402 Proxy endpoints

@router.post("/x402-proxy/request")
async def proxy_request(request: ProxyRequestModel):
    """
    Make proxy request through x402 payment verification
    
    This endpoint routes API calls through the X402 proxy service,
    verifying payments before accessing external APIs.
    """
    try:
        # Convert service string to enum
        service_type = ProxyServiceType(request.service.lower())
        
        # Create proxy request
        proxy_req = ProxyRequest(
            service=service_type,
            endpoint=request.endpoint,
            method=request.method,
            headers=request.headers,
            payload=request.payload,
            payment_hash=request.payment_hash
        )
        
        # Process request
        result = await x402_proxy_service.proxy_request(proxy_req)
        
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "payment_verified": result.payment_verified,
            "service": result.service.value if result.service else None,
            "request_id": result.request_id,
            "response_time": result.response_time
        }
        
    except ValueError as error:
        raise HTTPException(status_code=400, detail=f"Invalid service: {error}")
    except Exception as error:
        logger.error(f"Proxy request failed: {error}")
        raise HTTPException(status_code=500, detail=str(error))

@router.get("/x402-proxy/services")
async def get_proxy_services():
    """Get available proxy services and their configurations"""
    try:
        services = {}
        for service_type in ProxyServiceType:
            config = x402_proxy_service.get_service_config(service_type)
            services[service_type.value] = {
                "cost_per_call": config.get("cost_per_call"),
                "rate_limit": config.get("rate_limit"),
                "base_url": config.get("base_url")
            }
        
        return {"services": services}
        
    except Exception as error:
        logger.error(f"Failed to get proxy services: {error}")
        raise HTTPException(status_code=500, detail=str(error))

@router.get("/x402-proxy/statistics")
async def get_proxy_statistics():
    """Get proxy service statistics"""
    try:
        return x402_proxy_service.get_statistics()
        
    except Exception as error:
        logger.error(f"Failed to get proxy statistics: {error}")
        raise HTTPException(status_code=500, detail=str(error))

# Balance Service endpoints

@router.get("/balance/{address}", response_model=BalanceResponse)
async def get_balance(address: str, force_refresh: bool = False):
    """
    Get real-time balance for an address (fixes B7)
    
    This endpoint returns the current balance from Solana RPC
    with intelligent caching to avoid stale data.
    """
    try:
        balance_info = await balance_service.get_balance(address, force_refresh)
        
        return BalanceResponse(
            address=balance_info.address,
            balance_sol=float(balance_info.balance_sol),
            balance_usd=float(balance_info.balance_usd) if balance_info.balance_usd else None,
            last_updated=balance_info.last_updated,
            block_height=balance_info.block_height
        )
        
    except Exception as error:
        logger.error(f"Failed to get balance: {error}")
        raise HTTPException(status_code=500, detail=str(error))

@router.get("/balance/{address}/usd", response_model=BalanceResponse)
async def get_balance_with_usd(address: str):
    """Get balance with USD conversion"""
    try:
        balance_info = await balance_service.get_balance_with_usd(address)
        
        return BalanceResponse(
            address=balance_info.address,
            balance_sol=float(balance_info.balance_sol),
            balance_usd=float(balance_info.balance_usd) if balance_info.balance_usd else None,
            last_updated=balance_info.last_updated,
            block_height=balance_info.block_height
        )
        
    except Exception as error:
        logger.error(f"Failed to get balance with USD: {error}")
        raise HTTPException(status_code=500, detail=str(error))

@router.post("/balance/multiple")
async def get_multiple_balances(addresses: List[str]):
    """Get balances for multiple addresses in parallel"""
    try:
        balances = await balance_service.get_multiple_balances(addresses)
        
        return {
            address: BalanceResponse(
                address=balance_info.address,
                balance_sol=float(balance_info.balance_sol),
                balance_usd=float(balance_info.balance_usd) if balance_info.balance_usd else None,
                last_updated=balance_info.last_updated,
                block_height=balance_info.block_height
            )
            for address, balance_info in balances.items()
        }
        
    except Exception as error:
        logger.error(f"Failed to get multiple balances: {error}")
        raise HTTPException(status_code=500, detail=str(error))

@router.post("/balance/{address}/invalidate-cache")
async def invalidate_balance_cache(address: str):
    """Invalidate cache for a specific address"""
    try:
        await balance_service.invalidate_cache(address)
        return {"message": f"Cache invalidated for {address}"}
        
    except Exception as error:
        logger.error(f"Failed to invalidate cache: {error}")
        raise HTTPException(status_code=500, detail=str(error))

@router.post("/balance/invalidate-all-cache")
async def invalidate_all_balance_cache():
    """Invalidate all balance cache"""
    try:
        await balance_service.invalidate_all_cache()
        return {"message": "All balance cache invalidated"}
        
    except Exception as error:
        logger.error(f"Failed to invalidate all cache: {error}")
        raise HTTPException(status_code=500, detail=str(error))

@router.get("/balance/statistics")
async def get_balance_statistics():
    """Get balance service statistics"""
    try:
        return balance_service.get_statistics()
        
    except Exception as error:
        logger.error(f"Failed to get balance statistics: {error}")
        raise HTTPException(status_code=500, detail=str(error))

# Service Manager endpoints

@router.get("/status", response_model=ServiceStatusResponse)
async def get_service_status():
    """Get status of all services"""
    try:
        service_statuses = service_manager.get_service_status()
        
        services = []
        running_count = 0
        failed_count = 0
        
        for status in service_statuses:
            services.append({
                "name": status.name,
                "state": status.state.value,
                "last_error": status.last_error,
                "created_at": status.created_at,
                "updated_at": status.updated_at
            })
            
            if status.state.value == "running":
                running_count += 1
            elif status.state.value == "failed":
                failed_count += 1
        
        return ServiceStatusResponse(
            services=services,
            total_services=len(services),
            running_services=running_count,
            failed_services=failed_count
        )
        
    except Exception as error:
        logger.error(f"Failed to get service status: {error}")
        raise HTTPException(status_code=500, detail=str(error))

@router.post("/service/{service_name}/restart")
async def restart_service(service_name: str):
    """Restart a specific service"""
    try:
        await service_manager.stop_service(service_name)
        await asyncio.sleep(2)  # Brief pause
        await service_manager.start_service(service_name)
        
        return {"message": f"Service {service_name} restarted successfully"}
        
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        logger.error(f"Failed to restart service: {error}")
        raise HTTPException(status_code=500, detail=str(error))

@router.get("/health")
async def services_health():
    """Health check for all services"""
    try:
        service_statuses = service_manager.get_service_status()
        
        health_status = {}
        for status in service_statuses:
            service = service_manager.get_service(status.name)
            if service:
                health_status[status.name] = await service.health_check()
        
        return health_status
        
    except Exception as error:
        logger.error(f"Failed to get services health: {error}")
        raise HTTPException(status_code=500, detail=str(error))
