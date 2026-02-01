"""
Pytest configuration and fixtures for Agent Polis tests.
"""

import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from agent_polis.main import app
from agent_polis.shared.db import Base, get_db
from agent_polis.config import settings

# Import all models to ensure they're registered with Base
from agent_polis.agents.db_models import Agent
from agent_polis.events.models import Event
from agent_polis.actions.db_models import Action


# Use in-memory SQLite for tests (or test PostgreSQL if available)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database session override."""
    
    async def override_get_db():
        yield test_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, 
        base_url="http://test",
        follow_redirects=True,  # Handle FastAPI trailing slash redirects
    ) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sync_client(test_session: AsyncSession) -> Generator[TestClient, None, None]:
    """Create a synchronous test client."""
    
    async def override_get_db():
        yield test_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_agent(client: AsyncClient) -> dict:
    """Create and return a registered agent with API key."""
    response = await client.post(
        "/api/v1/agents/register",
        json={
            "name": f"test-agent-{uuid4().hex[:8]}",
            "description": "Test agent for unit tests",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def auth_headers(registered_agent: dict) -> dict:
    """Get authentication headers for a registered agent."""
    return {"X-API-Key": registered_agent["api_key"]}


# Alias for backward compatibility and clarity
@pytest_asyncio.fixture
async def async_client(client: AsyncClient) -> AsyncClient:
    """Alias for client fixture."""
    return client
