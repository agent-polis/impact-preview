"""
FastAPI middleware for rate limiting and request tracking.
"""

import time
from typing import Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from agent_polis.config import settings
from agent_polis.shared.redis import get_redis, RateLimiter

logger = structlog.get_logger()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis sliding window.
    
    Limits requests by API key (authenticated) or IP (unauthenticated).
    """
    
    # Paths that bypass rate limiting
    EXEMPT_PATHS = {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/.well-known/agent.json",
    }
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Skip rate limiting for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        
        # Skip in development if Redis isn't available
        try:
            redis_client = await get_redis()
            limiter = RateLimiter(redis_client)
        except Exception as e:
            logger.warning("Rate limiting disabled - Redis unavailable", error=str(e))
            return await call_next(request)
        
        # Determine rate limit key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Authenticated: limit by API key
            limit_key = f"ratelimit:key:{api_key[:16]}"
            max_requests = settings.rate_limit_requests * 2  # Higher limit for authenticated
        else:
            # Unauthenticated: limit by IP
            client_ip = request.client.host if request.client else "unknown"
            limit_key = f"ratelimit:ip:{client_ip}"
            max_requests = settings.rate_limit_requests
        
        # Check rate limit - gracefully degrade if Redis fails
        try:
            is_allowed, remaining, reset_in = await limiter.is_allowed(
                key=limit_key,
                max_requests=max_requests,
                window_seconds=settings.rate_limit_window,
            )
        except Exception as e:
            logger.warning("Rate limiting disabled - Redis connection failed", error=str(e))
            return await call_next(request)
        
        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                key=limit_key,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": reset_in,
                },
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_in),
                    "Retry-After": str(reset_in),
                },
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_in)
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all requests with timing.
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        start_time = time.perf_counter()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Log request
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            client_ip=request.client.host if request.client else None,
        )
        
        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response
