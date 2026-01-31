"""
Agent Polis - FastAPI Application Entry Point.

This module creates and configures the FastAPI application with all routers,
middleware, and event handlers.
"""

import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent_polis.config import settings
from agent_polis.shared.db import init_db, close_db
from agent_polis.shared.logging import setup_logging
from agent_polis.shared.redis import close_redis

# Set up structured logging
setup_logging(settings.log_level, settings.log_format)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("Starting Agent Polis", version="0.1.0", env=settings.app_env)
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Agent Polis")
    await close_db()
    await close_redis()
    logger.info("Connections closed")


# Create FastAPI application
app = FastAPI(
    title="Agent Polis",
    description="Governance and coordination layer for AI agents with simulation-integrated decision-making",
    version="0.1.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting and logging middleware
from agent_polis.shared.middleware import RateLimitMiddleware, RequestLoggingMiddleware

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.app_env,
    }


# A2A Discovery endpoint (required for A2A protocol)
@app.get("/.well-known/agent.json", tags=["A2A"])
async def agent_card() -> dict:
    """
    A2A Agent Card - describes this agent's capabilities.
    
    This endpoint is required for A2A protocol discovery.
    Other agents use this to understand what this polis can do.
    """
    return {
        "name": "Agent Polis",
        "description": "Governance and coordination layer for AI agents with simulation-integrated decision-making",
        "version": "0.1.0",
        "protocol": "a2a/1.0",
        "capabilities": [
            "simulation",
            "governance",
            "coordination",
        ],
        "endpoints": {
            "tasks": "/a2a/tasks",
            "simulations": "/api/v1/simulations",
            "agents": "/api/v1/agents",
        },
        "contact": {
            "url": "https://github.com/agent-polis/agent-polis",
        },
    }


# Import and include routers
from agent_polis.a2a.router import router as a2a_router
from agent_polis.agents.router import router as agents_router
from agent_polis.simulations.router import router as simulations_router

app.include_router(a2a_router, prefix="/a2a", tags=["A2A Protocol"])
app.include_router(agents_router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(simulations_router, prefix="/api/v1/simulations", tags=["Simulations"])


def cli() -> None:
    """Command-line interface entry point."""
    import uvicorn
    
    uvicorn.run(
        "agent_polis.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    cli()
