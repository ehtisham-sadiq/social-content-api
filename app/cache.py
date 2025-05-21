import json
from typing import Any, Optional, Union, Dict, List, TypeVar, Generic, Callable
import redis
from functools import wraps
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Redis client if enabled
redis_client = None
if settings.REDIS_ENABLED and settings.REDIS_URL:
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        redis_client.ping()  # Test connection
        logger.info("Redis cache initialized successfully")
    except redis.RedisError as e:
        logger.error(f"Failed to initialize Redis: {str(e)}")
        redis_client = None

T = TypeVar('T')

class Cache:
    """
    Cache utility for storing and retrieving data from Redis
    """
    
    @staticmethod
    def is_available() -> bool:
        """Check if Redis cache is available"""
        return redis_client is not None
    
    @staticmethod
    def get(key: str) -> Optional[str]:
        """Get a value from cache"""
        if not Cache.is_available():
            return None
        
        try:
            return redis_client.get(key)
        except redis.RedisError as e:
            logger.error(f"Redis get error: {str(e)}")
            return None
    
    @staticmethod
    def get_json(key: str) -> Optional[Any]:
        """Get a JSON value from cache"""
        value = Cache.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
        return None
    
    @staticmethod
    def set(key: str, value: str, expire: int = 3600) -> bool:
        """Set a value in cache with expiration in seconds"""
        if not Cache.is_available():
            return False
        
        try:
            return redis_client.set(key, value, ex=expire)
        except redis.RedisError as e:
            logger.error(f"Redis set error: {str(e)}")
            return False
    
    @staticmethod
    def set_json(key: str, value: Any, expire: int = 3600) -> bool:
        """Set a JSON value in cache with expiration in seconds"""
        try:
            json_value = json.dumps(value)
            return Cache.set(key, json_value, expire)
        except (TypeError, json.JSONEncodeError) as e:
            logger.error(f"JSON encode error: {str(e)}")
            return False
    
    @staticmethod
    def delete(key: str) -> bool:
        """Delete a value from cache"""
        if not Cache.is_available():
            return False
        
        try:
            return redis_client.delete(key) > 0
        except redis.RedisError as e:
            logger.error(f"Redis delete error: {str(e)}")
            return False
    
    @staticmethod
    def flush() -> bool:
        """Flush all cache"""
        if not Cache.is_available():
            return False
        
        try:
            return redis_client.flushdb()
        except redis.RedisError as e:
            logger.error(f"Redis flush error: {str(e)}")
            return False

def cached(prefix: str, expire: int = 3600, key_builder: Optional[Callable] = None):
    """
    Decorator for caching function results
    
    Args:
        prefix: Cache key prefix
        expire: Cache expiration time in seconds
        key_builder: Optional function to build cache key from function arguments
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not Cache.is_available():
                return await func(*args, **kwargs)
            
            # Build cache key
            if key_builder:
                key = f"{prefix}:{key_builder(*args, **kwargs)}"
            else:
                # Default key builder uses function name and arguments
                key_parts = [prefix, func.__name__]
                
                # Add positional arguments to key
                if len(args) > 1:  # Skip self/cls for methods
                    for arg in args[1:]:
                        if hasattr(arg, 'id'):  # Handle objects with ID
                            key_parts.append(str(arg.id))
                        elif isinstance(arg, (str, int, float, bool)):
                            key_parts.append(str(arg))
                
                # Add keyword arguments to key
                for k, v in sorted(kwargs.items()):
                    if isinstance(v, (str, int, float, bool)):
                        key_parts.append(f"{k}:{v}")
                
                key = ":".join(key_parts)
            
            # Try to get from cache
            cached_value = Cache.get_json(key)
            if cached_value is not None:
                return cached_value
            
            # Call function and cache result
            result = await func(*args, **kwargs)
            Cache.set_json(key, result, expire)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not Cache.is_available():
                return func(*args, **kwargs)
            
            # Build cache key
            if key_builder:
                key = f"{prefix}:{key_builder(*args, **kwargs)}"
            else:
                # Default key builder uses function name and arguments
                key_parts = [prefix, func.__name__]
                
                # Add positional arguments to key
                if len(args) > 1:  # Skip self/cls for methods
                    for arg in args[1:]:
                        if hasattr(arg, 'id'):  # Handle objects with ID
                            key_parts.append(str(arg.id))
                        elif isinstance(arg, (str, int, float, bool)):
                            key_parts.append(str(arg))
                
                # Add keyword arguments to key
                for k, v in sorted(kwargs.items()):
                    if isinstance(v, (str, int, float, bool)):
                        key_parts.append(f"{k}:{v}")
                
                key = ":".join(key_parts)
            
            # Try to get from cache
            cached_value = Cache.get_json(key)
            if cached_value is not None:
                return cached_value
            
            # Call function and cache result
            result = func(*args, **kwargs)
            Cache.set_json(key, result, expire)
            return result
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
