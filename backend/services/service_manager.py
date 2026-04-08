"""
Service Manager - Claude Code Service Layer Pattern Implementation

Based on Claude Code book's Service Layer pattern for managing external integrations,
API communications, and core system services.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from abc import ABC, abstractmethod
import time

logger = logging.getLogger(__name__)

class ServiceState(Enum):
    """Service lifecycle states"""
    REGISTERED = "registered"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"

class ServiceStatus:
    """Service status information"""
    def __init__(self, name: str, state: ServiceState, last_error: Optional[str] = None):
        self.name = name
        self.state = state
        self.last_error = last_error
        self.created_at = time.time()
        self.updated_at = time.time()

class Service(ABC):
    """Base service interface following Claude Code pattern"""
    
    def __init__(self):
        self.name: str = ""
        self.version: str = "1.0.0"
        self.auto_start: bool = True
        self.state: ServiceState = ServiceState.REGISTERED
        self.last_error: Optional[str] = None
        self._start_time: Optional[float] = None
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize service resources"""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the service"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the service"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check service health"""
        pass
    
    def get_status(self) -> ServiceStatus:
        """Get current service status"""
        return ServiceStatus(self.name, self.state, self.last_error)

class ServiceManager:
    """
    Service Manager implementing Claude Code Service Layer pattern
    
    Provides centralized service lifecycle management, health monitoring,
    and orchestration for all SwarmPay services.
    """
    
    def __init__(self):
        self.services: Dict[str, Service] = {}
        self.service_states: Dict[str, ServiceState] = {}
        self.startup_tasks: List[asyncio.Task] = []
        self.health_check_interval = 30  # 30 seconds
        self._health_check_task: Optional[asyncio.Task] = None
    
    async def register_service(self, service: Service) -> None:
        """Register a service with the manager"""
        if service.name in self.services:
            logger.warning(f"Service {service.name} already registered, updating...")
        
        self.services[service.name] = service
        self.service_states[service.name] = ServiceState.REGISTERED
        service.state = ServiceState.REGISTERED
        
        logger.info(f"Service {service.name} registered (v{service.version})")
        
        # Auto-start if enabled
        if service.auto_start:
            await self.start_service(service.name)
    
    async def unregister_service(self, service_name: str) -> None:
        """Unregister a service"""
        if service_name in self.services:
            service = self.services[service_name]
            await self.stop_service(service_name)
            del self.services[service_name]
            del self.service_states[service_name]
            logger.info(f"Service {service_name} unregistered")
    
    async def start_service(self, service_name: str) -> None:
        """Start a specific service"""
        service = self.services.get(service_name)
        if not service:
            raise ValueError(f"Service not found: {service_name}")
        
        if self.service_states[service_name] == ServiceState.RUNNING:
            logger.warning(f"Service {service_name} already running")
            return
        
        try:
            self.service_states[service_name] = ServiceState.STARTING
            service.state = ServiceState.STARTING
            service._start_time = time.time()
            
            # Initialize service
            await service.initialize()
            
            # Start service
            await service.start()
            
            self.service_states[service_name] = ServiceState.RUNNING
            service.state = ServiceState.RUNNING
            
            logger.info(f"Service {service_name} started successfully")
            
        except Exception as error:
            self.service_states[service_name] = ServiceState.FAILED
            service.state = ServiceState.FAILED
            service.last_error = str(error)
            logger.error(f"Failed to start service {service_name}: {error}")
            raise
    
    async def stop_service(self, service_name: str) -> None:
        """Stop a specific service"""
        service = self.services.get(service_name)
        if not service:
            raise ValueError(f"Service not found: {service_name}")
        
        if self.service_states[service_name] != ServiceState.RUNNING:
            logger.warning(f"Service {service_name} not running")
            return
        
        try:
            self.service_states[service_name] = ServiceState.STOPPING
            service.state = ServiceState.STOPPING
            
            await service.stop()
            
            self.service_states[service_name] = ServiceState.STOPPED
            service.state = ServiceState.STOPPED
            
            logger.info(f"Service {service_name} stopped successfully")
            
        except Exception as error:
            self.service_states[service_name] = ServiceState.FAILED
            service.state = ServiceState.FAILED
            service.last_error = str(error)
            logger.error(f"Failed to stop service {service_name}: {error}")
    
    async def start_all_services(self) -> None:
        """Start all registered services in parallel (Claude Code Parallel Prefetch)"""
        logger.info("Starting all services...")
        
        # Create startup tasks for all services
        startup_tasks = []
        for service_name in self.services:
            if self.services[service_name].auto_start:
                task = asyncio.create_task(self.start_service(service_name))
                startup_tasks.append(task)
        
        # Wait for all services to start
        results = await asyncio.gather(*startup_tasks, return_exceptions=True)
        
        # Log results
        failed_services = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                service_name = list(self.services.keys())[i]
                failed_services.append(service_name)
                logger.error(f"Service {service_name} failed to start: {result}")
        
        if failed_services:
            logger.warning(f"Failed to start services: {failed_services}")
        else:
            logger.info("All services started successfully")
        
        # Start health monitoring
        await self.start_health_monitoring()
    
    async def stop_all_services(self) -> None:
        """Stop all services"""
        logger.info("Stopping all services...")
        
        # Stop health monitoring first
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Stop all services
        stop_tasks = []
        for service_name in self.services:
            task = asyncio.create_task(self.stop_service(service_name))
            stop_tasks.append(task)
        
        await asyncio.gather(*stop_tasks, return_exceptions=True)
        logger.info("All services stopped")
    
    def get_service(self, service_name: str) -> Optional[Service]:
        """Get a service by name"""
        return self.services.get(service_name)
    
    def is_service_running(self, service_name: str) -> bool:
        """Check if a service is running"""
        return self.service_states.get(service_name) == ServiceState.RUNNING
    
    def get_service_status(self) -> List[ServiceStatus]:
        """Get status of all services"""
        return [service.get_status() for service in self.services.values()]
    
    async def start_health_monitoring(self) -> None:
        """Start background health monitoring"""
        if self._health_check_task:
            return
        
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Health monitoring started")
    
    async def _health_check_loop(self) -> None:
        """Background health check loop"""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.error(f"Health check error: {error}")
                await asyncio.sleep(5)
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on all running services"""
        for service_name, service in self.services.items():
            if self.service_states[service_name] == ServiceState.RUNNING:
                try:
                    is_healthy = await service.health_check()
                    if not is_healthy:
                        logger.warning(f"Service {service_name} health check failed")
                        # Attempt to restart the service
                        await self._restart_service(service_name)
                except Exception as error:
                    logger.error(f"Health check error for {service_name}: {error}")
    
    async def _restart_service(self, service_name: str) -> None:
        """Restart a failed service"""
        logger.info(f"Restarting service {service_name}...")
        try:
            await self.stop_service(service_name)
            await asyncio.sleep(2)  # Brief pause
            await self.start_service(service_name)
            logger.info(f"Service {service_name} restarted successfully")
        except Exception as error:
            logger.error(f"Failed to restart service {service_name}: {error}")

# Global service manager instance
service_manager = ServiceManager()
