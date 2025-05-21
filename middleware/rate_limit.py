from fastapi import Request, HTTPException, status
import time
from typing import Dict, Tuple, Optional
import redis
import logging
from app.config import settings
from app.cache import redis_client

logger = logging.getLogger(__name__)

# In-memory rate limit store as fallback if Redis is not available
in_memory_rate_limits: Dict[str, Tuple[int, float]] = {}

async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware to prevent abuse
    
    Uses Redis if available, otherwise falls back to in-memory storage
    """
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)
    
    # Skip rate limiting for certain paths
    if request.url.path in ["/", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)
    
    # Get client identifier (IP or user ID if authenticated)
    client_id = _get_client_identifier(request)
    
    # Check rate limit
    if not await _check_rate_limit(client_id):
        logger.warning(f"Rate limit exceeded for client: {client_id}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
    
    # Process request
    return await call_next(request)

def _get_client_identifier(request: Request) -> str:
    """
    Get a unique identifier for the client
    
    Uses user ID if authenticated, otherwise falls back to IP address
    """
    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    
    # Fall back to client IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Get the first IP in the chain (client IP)
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host
    
    return f"ip:{client_ip}"

async def _check_rate_limit(client_id: str) -> bool:
    """
    Check if client has exceeded rate limit
    
    Returns True if request is allowed, False if rate limit exceeded
    """
    current_time = time.time()
    window_size = settings.RATE_LIMIT_PERIOD_SECONDS
    max_requests = settings.RATE_LIMIT_REQUESTS
    
    # Use Redis if available
    if redis_client:
        try:
            key = f"ratelimit:{client_id}"
            
            # Use Redis pipeline for atomic operations
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, current_time - window_size)
            pipe.zcard(key)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.expire(key, window_size)
            results = pipe.execute()
            
            request_count = results[1]
            return request_count <= max_requests
        except redis.RedisError as e:
            logger.error(f"Redis rate limit error: {str(e)}")
            # Fall back to in-memory rate limiting
    
    # In-memory rate limiting (fallback)
    if client_id in in_memory_rate_limits:
        count, window_start = in_memory_rate_limits[client_id]
        
        # Reset window if expired
        if current_time - window_start > window_size:
            in_memory_rate_limits[client_id] = (1, current_time)
            return True
        
        # Increment count if within window
        if count < max_requests:
            in_memory_rate_limits[client_id] = (count + 1, window_start)
            return True
        
        return False
    else:
        # First request from this client
        in_memory_rate_limits[client_id] = (1, current_time)
        return True
