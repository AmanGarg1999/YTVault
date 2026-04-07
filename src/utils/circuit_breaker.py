"""
Circuit Breaker pattern for knowledgeVault-YT.

Prevents cascading failures by "tripping" when a service (Ollama, yt-dlp, etc.)
is consistently failing, allowing the system to fail fast and recover gracefully.
"""

import time
import logging
import threading
from enum import Enum
from functools import wraps
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Service is failing, block requests
    HALF_OPEN = "HALF_OPEN" # Testing if service recovered

class CircuitBreaker:
    """Stateful circuit breaker to wrap fragile external calls."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exceptions: tuple = (Exception,)
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self._lock = threading.Lock()

    def __call__(self, fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return self.call(fn, *args, **kwargs)
        return wrapper

    def call(self, fn: Callable, *args, **kwargs) -> Any:
        """Execute the function, respecting the circuit state."""
        with self._lock:
            # Check if we should move from OPEN to HALF_OPEN
            if self.state == CircuitState.OPEN:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    logger.info(f"Circuit '{self.name}' moving to HALF_OPEN (timeout elapsed)")
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise RuntimeError(
                        f"Circuit '{self.name}' is OPEN. Failing fast. "
                        f"Retry in {int(self.recovery_timeout - elapsed)}s"
                    )

        try:
            result = fn(*args, **kwargs)
            
            # If we reach here, the call succeeded
            with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    logger.info(f"Circuit '{self.name}' recovered! Moving to CLOSED")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
            return result

        except self.expected_exceptions as e:
            with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
                    if self.state != CircuitState.OPEN:
                        logger.error(f"Circuit '{self.name}' TRIPPED (OPEN) after {self.failure_count} failures. Error: {e}")
                    self.state = CircuitState.OPEN
                
                raise e

# ---------------------------------------------------------------------------
# Global Registry of Circuit Breakers
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, CircuitBreaker] = {}

def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    if name not in _REGISTRY:
        _REGISTRY[name] = CircuitBreaker(name, **kwargs)
    return _REGISTRY[name]
