"""
Redis client for caching and rate limiting.
"""

from typing import Optional
import redis.asyncio as redis
import structlog

from agent_polis.config import settings

logger = structlog.get_logger()

# Global Redis client
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get the Redis client, creating it if necessary."""
    global _redis_client
    
    if _redis_client is None:
        _redis_client = redis.from_url(
            str(settings.redis_url),
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Redis client initialized", url=str(settings.redis_url).split("@")[-1])
    
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis_client
    
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")


class RateLimiter:
    """
    Token bucket rate limiter using Redis.
    
    Limits requests per time window using sliding window algorithm.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Check if a request is allowed under rate limits.
        
        Args:
            key: Unique identifier (e.g., "agent:{id}" or "ip:{addr}")
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining_requests, reset_in_seconds)
        """
        import time
        
        now = time.time()
        window_start = now - window_seconds
        
        pipe = self.redis.pipeline()
        
        # Remove old entries outside window
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests in window
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Set expiry on the key
        pipe.expire(key, window_seconds)
        
        results = await pipe.execute()
        current_count = results[1]
        
        remaining = max(0, max_requests - current_count - 1)
        is_allowed = current_count < max_requests
        
        # Calculate reset time
        if current_count > 0:
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                reset_in = int(oldest[0][1] + window_seconds - now)
            else:
                reset_in = window_seconds
        else:
            reset_in = window_seconds
        
        return is_allowed, remaining, max(0, reset_in)
    
    async def get_usage(
        self,
        key: str,
        window_seconds: int,
    ) -> int:
        """Get current usage count for a key."""
        import time
        
        now = time.time()
        window_start = now - window_seconds
        
        # Clean and count
        await self.redis.zremrangebyscore(key, 0, window_start)
        return await self.redis.zcard(key)
