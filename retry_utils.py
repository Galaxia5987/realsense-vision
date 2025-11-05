"""
Retry and recovery utilities for fault-tolerant initialization and operations.
"""
import time
import functools
from typing import Callable, TypeVar, Optional, Type, Tuple
import logging_config


logger = logging_config.get_logger('retry')

T = TypeVar('T')


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
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
                        operation="retry"
                    )
                    result = func(*args, **kwargs)
                    
                    if attempt > 1:
                        logger.info(
                            f"{func.__name__} succeeded on attempt {attempt}",
                            operation="retry", status="success"
                        )
                    
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}",
                            operation="retry", status="max_attempts_exceeded"
                        )
                        raise
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}",
                        operation="retry", status="retrying"
                    )
                    
                    if on_retry:
                        try:
                            on_retry(e, attempt)
                        except Exception as callback_error:
                            logger.exception(
                                f"Error in retry callback: {callback_error}",
                                operation="retry"
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


def safe_init(
    component_name: str,
    init_func: Callable[..., T],
    fallback_value: Optional[T] = None,
    max_attempts: int = 3,
    **init_kwargs
) -> Tuple[Optional[T], Optional[str]]:
    """
    Safely initialize a component with retry logic and detailed logging.
    
    Args:
        component_name: Name of the component being initialized
        init_func: Initialization function to call
        fallback_value: Value to return if initialization fails
        max_attempts: Maximum initialization attempts
        **init_kwargs: Keyword arguments to pass to init_func
    
    Returns:
        Tuple of (initialized_object, error_message)
        - initialized_object is None if initialization failed
        - error_message is None if initialization succeeded
    
    Example:
        camera, error = safe_init(
            "camera",
            RealSenseCamera,
            max_attempts=5,
            width=640,
            height=480
        )
    """
    comp_logger = logging_config.get_logger(component_name)
    
    comp_logger.info(
        f"Initializing {component_name}",
        operation="initialization", status="starting"
    )
    
    for attempt in range(1, max_attempts + 1):
        try:
            comp_logger.debug(
                f"Initialization attempt {attempt}/{max_attempts}",
                operation="initialization"
            )
            
            result = init_func(**init_kwargs)
            
            comp_logger.info(
                f"{component_name} initialized successfully",
                operation="initialization", status="success"
            )
            
            return result, None
            
        except Exception as e:
            error_msg = f"Attempt {attempt}/{max_attempts} failed: {e}"
            
            if attempt == max_attempts:
                comp_logger.error(
                    f"Failed to initialize {component_name} after {max_attempts} attempts",
                    operation="initialization", status="failed"
                )
                comp_logger.exception(str(e), operation="initialization")
                
                if fallback_value is not None:
                    comp_logger.warning(
                        f"Using fallback value for {component_name}",
                        operation="initialization", status="fallback"
                    )
                
                return fallback_value, str(e)
            else:
                comp_logger.warning(
                    error_msg,
                    operation="initialization", status="retrying"
                )
                
                # Exponential backoff
                delay = min(2 ** (attempt - 1), 10)
                time.sleep(delay)
    
    return fallback_value, "Unknown initialization error"


def safe_call(
    func: Callable[..., T],
    default: Optional[T] = None,
    operation_name: Optional[str] = None,
    suppress_errors: bool = True,
    *args,
    **kwargs
) -> T:
    """
    Safely call a function with error handling and logging.
    
    Args:
        func: Function to call
        default: Default value to return on error
        operation_name: Name of the operation for logging
        suppress_errors: If True, return default on error; if False, re-raise
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
    
    Returns:
        Result of func or default value on error
    
    Example:
        result = safe_call(
            camera.get_frame,
            default=None,
            operation_name="get_frame"
        )
    """
    op_name = operation_name or func.__name__
    
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(
            f"Error in {op_name}: {e}",
            operation=op_name, status="error"
        )
        
        if not suppress_errors:
            raise
        
        logger.debug(
            f"Returning default value for {op_name}",
            operation=op_name
        )
        return default
