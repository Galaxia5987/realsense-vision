"""
Retry and recovery utilities for fault-tolerant initialization and operations.
"""

import functools
import time
from typing import Callable, Optional, Tuple, Type, TypeVar

import app.core.logging_config as logging_config

logger = logging_config.get_logger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    Decorator for retrying a function with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry
        max_delay: Maximum delay between retries
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback called on each retry with (exception, attempt_number)

    Example:
        @retry_with_backoff(max_attempts=5, initial_delay=2.0)
        def connect_to_camera():
            # Connection logic that may fail
            pass
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    logger.debug(
                        f"Attempting {func.__name__} (attempt {attempt}/{max_attempts})",
                        operation="retry",
                    )
                    result = func(*args, **kwargs)

                    if attempt > 1:
                        logger.info(
                            f"{func.__name__} succeeded on attempt {attempt}",
                            operation="retry",
                            status="success",
                        )

                    return result

                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}",
                            operation="retry",
                            status="max_attempts_exceeded",
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}",
                        operation="retry",
                        status="retrying",
                    )

                    if on_retry:
                        try:
                            on_retry(e, attempt)
                        except Exception as callback_error:
                            logger.exception(
                                f"Error in retry callback: {callback_error}",
                                operation="retry",
                            )

                    # Wait before next retry
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)

            # This should not be reached, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__} failed with unknown error")

        return wrapper

    return decorator
