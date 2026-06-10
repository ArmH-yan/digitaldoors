"""Retry and rate limiting utilities."""

import asyncio
import time
import random
from functools import wraps
from typing import Callable, Any
from src.utils.logging import get_logger

logger = get_logger("retry")


class RateLimiter:
    """Token bucket rate limiter for respectful scraping."""
    
    def __init__(self, requests_per_second: float = 1.0, burst: int = 1):
        self.rate = requests_per_second
        self.burst = burst
        self.tokens = burst
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait until a request token is available."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_refill = now
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


def retry_async(max_retries: int = 3, delay: float = 2.0, backoff: float = 2.0):
    """Decorator for async functions with exponential backoff retry."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        jitter = random.uniform(0.5, 1.5)
                        wait_time = current_delay * jitter
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__}: {e}. "
                            f"Waiting {wait_time:.1f}s"
                        )
                        await asyncio.sleep(wait_time)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"Failed after {max_retries} retries: {func.__name__}: {e}"
                        )
            
            raise last_exception
        return wrapper
    return decorator


def retry_sync(max_retries: int = 3, delay: float = 2.0, backoff: float = 2.0):
    """Decorator for sync functions with exponential backoff retry."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        jitter = random.uniform(0.5, 1.5)
                        wait_time = current_delay * jitter
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__}: {e}. "
                            f"Waiting {wait_time:.1f}s"
                        )
                        time.sleep(wait_time)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"Failed after {max_retries} retries: {func.__name__}: {e}"
                        )
            
            raise last_exception
        return wrapper
    return decorator
