"""
Retry Decorator — Enterprise Exponential Backoff.

Resiliently wraps flaky third-party APIs (LLMs, Allium, FinBERT)
with jitter and exponential backoff to smooth out thread pool starvation.
"""

import time
import logging
from functools import wraps
from httpx import HTTPStatusError, TimeoutException
from anthropic import RateLimitError, APIConnectionError, APIError

logger = logging.getLogger("swarmpay.retry")

def with_retry(max_retries: int = 3, base_delay: float = 2.0):
    """
    Decorator for robust retry logic with exponential backoff.
    Gracefully handles RateLimits (429) and Timeouts.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (RateLimitError, TimeoutException) as exc:
                    logger.warning("[%s] rate/timeout limit hit (attempt %d/%d)", 
                                   func.__name__, attempt + 1, max_retries + 1)
                    last_exc = exc
                    # Backoff: 2s, 4s, 8s
                    time.sleep(base_delay * (2 ** attempt))
                except HTTPStatusError as exc:
                    if exc.response.status_code == 429:
                        logger.warning("[%s] HTTP 429 rate limit (attempt %d/%d)", 
                                       func.__name__, attempt + 1, max_retries + 1)
                        last_exc = exc
                        time.sleep(base_delay * (2 ** attempt))
                    else:
                        logger.error("[%s] HTTP %d: %s", func.__name__, exc.response.status_code, exc)
                        raise  # Don't retry 400s or 500s unless necessary
                except (APIConnectionError, APIError) as exc:
                    logger.warning("[%s] Connection Error (attempt %d/%d)", 
                                   func.__name__, attempt + 1, max_retries + 1)
                    last_exc = exc
                    time.sleep(base_delay)
            
            logger.error("[%s] All %d retries exhausted.", func.__name__, max_retries)
            raise last_exc
        return wrapper
    return decorator
