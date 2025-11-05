"""
Component supervisor and watchdog for monitoring system health and automatic recovery.
Monitors critical components and attempts recovery when failures are detected.
"""
import threading
import time
from typing import Dict, Callable, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import logging_config


logger = logging_config.get_logger('supervisor')


class ComponentStatus(Enum):
    """Status states for monitored components."""
    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"


@dataclass
class ComponentHealth:
    """Health information for a monitored component."""
    name: str
    status: ComponentStatus
    last_check: datetime
    consecutive_failures: int
    total_failures: int
    last_error: Optional[str] = None
    recovery_attempts: int = 0


class ComponentSupervisor:
    """
    Supervisor for monitoring and recovering system components.
    Performs health checks and automatic recovery attempts.
    """
    
    def __init__(self, check_interval: float = 5.0, max_recovery_attempts: int = 3):
        """
        Initialize the component supervisor.
        
        Args:
            check_interval: Seconds between health checks
            max_recovery_attempts: Maximum recovery attempts before giving up
        """
        self.check_interval = check_interval
        self.max_recovery_attempts = max_recovery_attempts
        
        self.components: Dict[str, ComponentHealth] = {}
        self.health_checks: Dict[str, Callable[[], bool]] = {}
        self.recovery_handlers: Dict[str, Callable[[], bool]] = {}
        
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.RLock()
        
        logger.info("Component supervisor initialized", operation="init")
    
    def register_component(
        self,
        name: str,
        health_check: Callable[[], bool],
        recovery_handler: Optional[Callable[[], bool]] = None
    ):
        """
        Register a component for monitoring.
        
        Args:
            name: Unique component name
            health_check: Function that returns True if component is healthy
            recovery_handler: Optional function to attempt component recovery
        """
        with self.lock:
            self.components[name] = ComponentHealth(
                name=name,
                status=ComponentStatus.UNKNOWN,
                last_check=datetime.now(),
                consecutive_failures=0,
                total_failures=0
            )
            self.health_checks[name] = health_check
            if recovery_handler:
                self.recovery_handlers[name] = recovery_handler
            
            logger.info(f"Registered component for monitoring: {name}", 
                       operation="register_component", status="success")
    
    def unregister_component(self, name: str):
        """Unregister a component from monitoring."""
        with self.lock:
            if name in self.components:
                del self.components[name]
                del self.health_checks[name]
                if name in self.recovery_handlers:
                    del self.recovery_handlers[name]
                logger.info(f"Unregistered component: {name}", 
                           operation="unregister_component")
    
    def get_component_status(self, name: str) -> Optional[ComponentHealth]:
        """Get the current health status of a component."""
        with self.lock:
            return self.components.get(name)
    
    def get_all_statuses(self) -> Dict[str, ComponentHealth]:
        """Get health status of all monitored components."""
        with self.lock:
            return dict(self.components)
    
    def _check_component_health(self, name: str) -> bool:
        """
        Check health of a single component.
        
        Args:
            name: Component name
            
        Returns:
            True if component is healthy, False otherwise
        """
        try:
            health_check = self.health_checks.get(name)
            if not health_check:
                logger.warning(f"No health check registered for {name}", 
                             operation="health_check")
                return False
            
            is_healthy = health_check()
            
            with self.lock:
                component = self.components.get(name)
                if not component:
                    return False
                
                component.last_check = datetime.now()
                
                if is_healthy:
                    if component.status in [ComponentStatus.FAILED, ComponentStatus.RECOVERING]:
                        logger.info(f"Component {name} recovered", 
                                  operation="health_check", status="recovered")
                    
                    component.status = ComponentStatus.HEALTHY
                    component.consecutive_failures = 0
                    component.last_error = None
                else:
                    component.consecutive_failures += 1
                    component.total_failures += 1
                    
                    if component.status != ComponentStatus.FAILED:
                        logger.warning(
                            f"Component {name} health check failed "
                            f"(consecutive: {component.consecutive_failures})",
                            operation="health_check", status="unhealthy"
                        )
                    
                    component.status = ComponentStatus.DEGRADED
            
            return is_healthy
            
        except Exception as e:
            logger.exception(f"Error checking health of {name}: {e}", 
                           operation="health_check")
            
            with self.lock:
                component = self.components.get(name)
                if component:
                    component.status = ComponentStatus.FAILED
                    component.last_error = str(e)
                    component.consecutive_failures += 1
                    component.total_failures += 1
            
            return False
    
    def _attempt_recovery(self, name: str) -> bool:
        """
        Attempt to recover a failed component.
        
        Args:
            name: Component name
            
        Returns:
            True if recovery was successful, False otherwise
        """
        recovery_handler = self.recovery_handlers.get(name)
        if not recovery_handler:
            logger.warning(f"No recovery handler registered for {name}", 
                         operation="recovery")
            return False
        
        with self.lock:
            component = self.components.get(name)
            if not component:
                return False
            
            if component.recovery_attempts >= self.max_recovery_attempts:
                logger.error(
                    f"Component {name} exceeded max recovery attempts "
                    f"({self.max_recovery_attempts})",
                    operation="recovery", status="max_attempts_exceeded"
                )
                component.status = ComponentStatus.FAILED
                return False
            
            component.status = ComponentStatus.RECOVERING
            component.recovery_attempts += 1
        
        logger.info(f"Attempting recovery of {name} (attempt {component.recovery_attempts})", 
                   operation="recovery", status="attempting")
        
        try:
            success = recovery_handler()
            
            if success:
                logger.info(f"Successfully recovered {name}", 
                           operation="recovery", status="success")
                with self.lock:
                    component.status = ComponentStatus.HEALTHY
                    component.consecutive_failures = 0
                    component.last_error = None
                return True
            else:
                logger.warning(f"Recovery of {name} returned False", 
                             operation="recovery", status="failed")
                with self.lock:
                    component.status = ComponentStatus.FAILED
                return False
                
        except Exception as e:
            logger.exception(f"Error during recovery of {name}: {e}", 
                           operation="recovery")
            with self.lock:
                component.status = ComponentStatus.FAILED
                component.last_error = str(e)
            return False
    
    def _monitor_loop(self):
        """
        Main monitoring loop that runs in a background thread.
        
        Note: This runs as a daemon thread, which is appropriate because:
        - The supervisor is meant to run continuously while the app is running
        - The stop() method provides graceful shutdown via self.running flag
        - No critical cleanup is required when the supervisor stops
        """
        logger.info("Supervisor monitoring loop started", operation="monitor_loop")
        
        while self.running:
            try:
                # Check all registered components
                for name in list(self.components.keys()):
                    is_healthy = self._check_component_health(name)
                    
                    # Attempt recovery if component is unhealthy
                    if not is_healthy:
                        component = self.get_component_status(name)
                        if component and component.consecutive_failures >= 2:
                            # Only attempt recovery after multiple consecutive failures
                            self._attempt_recovery(name)
                
                # Wait for next check interval
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.exception(f"Error in monitoring loop: {e}", 
                               operation="monitor_loop")
                time.sleep(self.check_interval)
        
        logger.info("Supervisor monitoring loop stopped", operation="monitor_loop")
    
    def start(self):
        """Start the supervisor monitoring thread."""
        if self.running:
            logger.warning("Supervisor already running", operation="start")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("Supervisor started", operation="start", status="success")
    
    def stop(self):
        """Stop the supervisor monitoring thread."""
        if not self.running:
            return
        
        logger.info("Stopping supervisor", operation="stop")
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        logger.info("Supervisor stopped", operation="stop", status="success")
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """
        Get a summary of overall system health.
        
        Returns:
            Dictionary with system health information
        """
        with self.lock:
            total = len(self.components)
            if total == 0:
                return {
                    'status': 'unknown',
                    'total_components': 0,
                    'healthy': 0,
                    'degraded': 0,
                    'failed': 0
                }
            
            healthy = sum(1 for c in self.components.values() 
                         if c.status == ComponentStatus.HEALTHY)
            degraded = sum(1 for c in self.components.values() 
                          if c.status == ComponentStatus.DEGRADED)
            failed = sum(1 for c in self.components.values() 
                        if c.status == ComponentStatus.FAILED)
            
            # Overall system status
            if failed > 0:
                overall = 'critical'
            elif degraded > 0:
                overall = 'degraded'
            elif healthy == total:
                overall = 'healthy'
            else:
                overall = 'unknown'
            
            return {
                'status': overall,
                'total_components': total,
                'healthy': healthy,
                'degraded': degraded,
                'failed': failed,
                'components': {
                    name: {
                        'status': health.status.value,
                        'consecutive_failures': health.consecutive_failures,
                        'total_failures': health.total_failures,
                        'recovery_attempts': health.recovery_attempts,
                        'last_error': health.last_error
                    }
                    for name, health in self.components.items()
                }
            }


# Global supervisor instance
supervisor = ComponentSupervisor()
