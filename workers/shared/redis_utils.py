"""
Redis Utilities for Clawd Bot
- Caching
- Rate Limiting
- Job Queue
"""

import os
import json
import logging
import functools
import hashlib
from typing import Any, Optional, Callable
from datetime import timedelta
import redis

logger = logging.getLogger('clawd.redis')

# Environment Variables
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

# Global Redis client
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True
        )
    
    return _redis_client


def is_redis_available() -> bool:
    """Check if Redis is available."""
    try:
        client = get_redis_client()
        return client.ping()
    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.warning(f"Redis not available: {e}")
        return False


# =============================================================================
# Caching
# =============================================================================

class CacheKeys:
    """Cache key prefixes."""
    WEATHER = "cache:weather"
    CALENDAR = "cache:calendar"
    GITHUB = "cache:github"
    GARMIN_HEALTH = "cache:garmin:health"
    GARMIN_ACTIVITIES = "cache:garmin:activities"


def cache_get(key: str) -> Optional[Any]:
    """Get value from cache."""
    try:
        client = get_redis_client()
        data = client.get(key)
        if data:
            return json.loads(data)
        return None
    except (redis.RedisError, json.JSONDecodeError) as e:
        logger.error(f"Cache get error for {key}: {e}")
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    """Set value in cache with TTL."""
    try:
        client = get_redis_client()
        data = json.dumps(value, default=str)
        client.setex(key, ttl_seconds, data)
        return True
    except redis.RedisError as e:
        logger.error(f"Cache set error for {key}: {e}")
        return False


def cache_delete(key: str) -> bool:
    """Delete key from cache."""
    try:
        client = get_redis_client()
        client.delete(key)
        return True
    except redis.RedisError as e:
        logger.error(f"Cache delete error for {key}: {e}")
        return False


def cached(key_prefix: str, ttl_seconds: int = 300):
    """
    Decorator for caching function results.
    
    Usage:
        @cached("weather", ttl_seconds=600)
        async def get_weather(city):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Build cache key from function arguments
            key_parts = [key_prefix]
            if args:
                key_parts.extend(str(a) for a in args)
            if kwargs:
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_value = cache_get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                cache_set(cache_key, result, ttl_seconds)
                logger.debug(f"Cache set: {cache_key}")
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            key_parts = [key_prefix]
            if args:
                key_parts.extend(str(a) for a in args)
            if kwargs:
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            
            cache_key = ":".join(key_parts)
            
            cached_value = cache_get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            result = func(*args, **kwargs)
            if result is not None:
                cache_set(cache_key, result, ttl_seconds)
                logger.debug(f"Cache set: {cache_key}")
            
            return result
        
        # Return appropriate wrapper based on function type
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# Rate Limiting
# =============================================================================

class RateLimiter:
    """
    Token bucket rate limiter using Redis.
    
    Usage:
        limiter = RateLimiter("garmin_api", max_requests=10, window_seconds=60)
        if limiter.allow():
            # Make API call
        else:
            # Wait or skip
    """
    
    def __init__(self, name: str, max_requests: int, window_seconds: int):
        self.name = name
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key = f"ratelimit:{name}"
    
    def allow(self) -> bool:
        """Check if request is allowed and consume a token."""
        try:
            client = get_redis_client()
            
            # Use a Lua script for atomic operation
            lua_script = """
            local key = KEYS[1]
            local max_requests = tonumber(ARGV[1])
            local window = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            
            -- Remove old entries
            redis.call('ZREMRANGEBYSCORE', key, 0, now - window * 1000)
            
            -- Count current requests
            local count = redis.call('ZCARD', key)
            
            if count < max_requests then
                -- Add new request
                redis.call('ZADD', key, now, now .. '-' .. math.random())
                redis.call('EXPIRE', key, window)
                return 1
            else
                return 0
            end
            """
            
            import time
            now_ms = int(time.time() * 1000)
            
            result = client.eval(
                lua_script,
                1,
                self.key,
                self.max_requests,
                self.window_seconds,
                now_ms
            )
            
            return bool(result)
            
        except redis.RedisError as e:
            logger.error(f"Rate limiter error: {e}")
            # Allow on error to prevent blocking
            return True
    
    def remaining(self) -> int:
        """Get remaining requests in current window."""
        try:
            client = get_redis_client()
            import time
            now_ms = int(time.time() * 1000)
            window_start = now_ms - (self.window_seconds * 1000)
            
            # Remove old and count
            client.zremrangebyscore(self.key, 0, window_start)
            count = client.zcard(self.key)
            
            return max(0, self.max_requests - count)
            
        except redis.RedisError:
            return self.max_requests
    
    def wait_time(self) -> float:
        """Get seconds to wait before next request is allowed."""
        try:
            client = get_redis_client()
            
            # Get oldest entry
            oldest = client.zrange(self.key, 0, 0, withscores=True)
            if not oldest:
                return 0
            
            import time
            oldest_ms = oldest[0][1]
            now_ms = time.time() * 1000
            
            wait_ms = (oldest_ms + self.window_seconds * 1000) - now_ms
            return max(0, wait_ms / 1000)
            
        except redis.RedisError:
            return 0


# Pre-configured rate limiters
garmin_limiter = RateLimiter("garmin_api", max_requests=15, window_seconds=60)
weather_limiter = RateLimiter("weather_api", max_requests=60, window_seconds=60)
github_limiter = RateLimiter("github_api", max_requests=30, window_seconds=60)


# =============================================================================
# Job Queue
# =============================================================================

class JobQueue:
    """
    Simple job queue using Redis lists.
    
    Usage:
        queue = JobQueue("sync_tasks")
        queue.push({"task": "sync_garmin", "date": "2026-01-26"})
        job = queue.pop()
    """
    
    def __init__(self, name: str):
        self.name = name
        self.key = f"queue:{name}"
        self.processing_key = f"queue:{name}:processing"
    
    def push(self, job: dict) -> bool:
        """Add job to queue."""
        try:
            client = get_redis_client()
            client.lpush(self.key, json.dumps(job, default=str))
            logger.info(f"Job pushed to {self.name}: {job}")
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to push job: {e}")
            return False
    
    def pop(self, timeout: int = 0) -> Optional[dict]:
        """
        Get job from queue.
        
        Args:
            timeout: Seconds to wait for job (0 = no wait)
        """
        try:
            client = get_redis_client()
            
            if timeout > 0:
                # Blocking pop with timeout
                result = client.brpoplpush(self.key, self.processing_key, timeout)
            else:
                # Non-blocking pop
                result = client.rpoplpush(self.key, self.processing_key)
            
            if result:
                return json.loads(result)
            return None
            
        except redis.RedisError as e:
            logger.error(f"Failed to pop job: {e}")
            return None
    
    def complete(self, job: dict) -> bool:
        """Mark job as completed (remove from processing)."""
        try:
            client = get_redis_client()
            client.lrem(self.processing_key, 1, json.dumps(job, default=str))
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to complete job: {e}")
            return False
    
    def fail(self, job: dict, error: str) -> bool:
        """Mark job as failed and store for retry/inspection."""
        try:
            client = get_redis_client()
            
            # Remove from processing
            client.lrem(self.processing_key, 1, json.dumps(job, default=str))
            
            # Add to failed queue with error info
            failed_job = {**job, "error": error, "failed_at": str(datetime.datetime.now())}
            client.lpush(f"{self.key}:failed", json.dumps(failed_job, default=str))
            
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to mark job as failed: {e}")
            return False
    
    def size(self) -> int:
        """Get queue size."""
        try:
            client = get_redis_client()
            return client.llen(self.key)
        except redis.RedisError:
            return 0
    
    def processing_count(self) -> int:
        """Get number of jobs being processed."""
        try:
            client = get_redis_client()
            return client.llen(self.processing_key)
        except redis.RedisError:
            return 0


# Pre-configured queues
sync_queue = JobQueue("sync_tasks")
notification_queue = JobQueue("notifications")


# =============================================================================
# Health Check
# =============================================================================

def redis_health_check() -> dict:
    """Get Redis health status."""
    try:
        client = get_redis_client()
        info = client.info()
        
        return {
            "status": "healthy",
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "N/A"),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
            "total_commands_processed": info.get("total_commands_processed", 0)
        }
    except redis.RedisError as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


import datetime
