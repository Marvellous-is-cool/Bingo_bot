import asyncio
import logging
from functools import wraps
import aiohttp
from typing import Any, Callable, TypeVar, Awaitable

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('highrise_bot')

T = TypeVar('T')

async def with_retry(coro_func: Callable[..., Awaitable[T]], *args: Any, 
                    max_retries: int = 3, initial_delay: float = 1.0, 
                    backoff_factor: float = 2.0, **kwargs: Any) -> T:
    """
    Execute a coroutine function with retry logic.
    
    Args:
        coro_func: The coroutine function to execute
        args: Positional arguments to pass to the function
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Factor by which the delay increases with each retry
        kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the coroutine function
        
    Raises:
        The last exception encountered after all retries are exhausted
    """
    retries = 0
    delay = initial_delay
    
    while True:
        try:
            return await coro_func(*args, **kwargs)
        except (aiohttp.ClientError, asyncio.TimeoutError, 
                ConnectionError, OSError) as e:
            retries += 1
            
            if retries > max_retries:
                logger.error(f"Failed after {max_retries} retries: {e}")
                raise
                
            logger.warning(f"Connection error ({e}), retrying in {delay:.2f}s "
                          f"(attempt {retries}/{max_retries})")
            
            # Wait before retry with exponential backoff
            await asyncio.sleep(delay)
            delay *= backoff_factor

def retry_on_connection_error(max_retries: int = 3, initial_delay: float = 1.0, 
                             backoff_factor: float = 2.0):
    """
    Decorator to retry a coroutine function on connection errors.
    
    Usage:
        @retry_on_connection_error(max_retries=5)
        async def fetch_data():
            # Your code here
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await with_retry(
                func, *args, max_retries=max_retries, 
                initial_delay=initial_delay, 
                backoff_factor=backoff_factor, **kwargs
            )
        return wrapper
    return decorator
