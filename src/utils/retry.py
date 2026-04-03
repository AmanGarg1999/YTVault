"""
Retry and resilience utilities for knowledgeVault-YT.

Provides a configurable retry decorator that reads backoff settings
from settings.yaml and a circuit breaker for repeated failures.
"""

import logging
import time
from functools import wraps
from typing import Optional

from src.config import get_settings

logger = logging.getLogger(__name__)


def with_retry(config_key: str, default_retries: int = 2,
               default_backoff: list[float] = None):
    """Decorator for retrying functions with configurable backoff.

    Reads retry config from settings.yaml['retry'][config_key].

    Args:
        config_key: Key in settings.yaml retry section
                    (e.g., "yt_dlp_metadata", "ollama_inference").
        default_retries: Fallback max retries if config key missing.
        default_backoff: Fallback backoff delays in seconds.

    Usage:
        @with_retry("ollama_inference")
        def call_ollama(prompt):
            return ollama.chat(...)
    """
    if default_backoff is None:
        default_backoff = [1, 3, 10]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            settings = get_settings()
            retry_cfg = settings.get("retry", {}).get(config_key, {})
            max_retries = retry_cfg.get("max_retries", default_retries)
            backoff = retry_cfg.get("backoff", default_backoff)

            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt >= max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} "
                            f"attempts: {e}"
                        )
                        raise

                    delay = backoff[min(attempt, len(backoff) - 1)]
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries + 1} "
                        f"failed: {e}. Retrying in {delay}s..."
                    )
                    time.sleep(delay)

            raise last_exception  # Should not reach here

        return wrapper
    return decorator


class CircuitBreaker:
    """Simple circuit breaker for external service calls.

    After `failure_threshold` consecutive failures, the breaker opens
    and subsequent calls fail fast for `recovery_timeout` seconds.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func, *args, **kwargs):
        """Execute a function through the circuit breaker."""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker half-open: attempting recovery")
            else:
                raise RuntimeError(
                    f"Circuit breaker OPEN: service unavailable "
                    f"(next retry in "
                    f"{self.recovery_timeout - (time.time() - self.last_failure_time):.0f}s)"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(
                f"Circuit breaker OPEN after {self.failure_count} failures. "
                f"Will retry after {self.recovery_timeout}s."
            )
