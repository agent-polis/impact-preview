"""
Agent service - business logic for agent management.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_polis.agents.db_models import Agent
from agent_polis.agents.models import AgentCreate, AgentProfile, AgentStats
from agent_polis.events.store import EventStore
from agent_polis.events.types import AgentRegistered, AgentReputationChanged
from agent_polis.events.bus import publish_event
from agent_polis.shared.security import generate_api_key, hash_api_key

logger = structlog.get_logger()


class AgentService:
    """Service for agent management operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.event_store = EventStore(session)
    
    async def register(self, data: AgentCreate) -> tuple[Agent, str]:
        """
        Register a new agent.
        
        Returns:
            Tuple of (Agent, api_key) - API key is only available at registration
        """
        # Check if name already exists
        existing = await self.session.execute(
            select(Agent).where(Agent.name == data.name.lower())
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Agent name '{data.name}' is already taken")
        
        # Generate API key
        api_key = generate_api_key()
        api_key_hash = hash_api_key(api_key)
        
        # Create agent
        agent = Agent(
            name=data.name.lower(),
            description=data.description,
            api_key_hash=api_key_hash,
            status="active",  # Auto-activate for MVP; add verification later
        )
        
        self.session.add(agent)
        await self.session.flush()
        
        # Record event
        event = AgentRegistered(
            stream_id=f"agent:{agent.id}",
            data={
                "agent_id": str(agent.id),
                "name": agent.name,
                "description": agent.description,
            },
        )
        await self.event_store.append(event)
        await publish_event(event)
        
        logger.info(
            "Agent registered",
            agent_id=str(agent.id),
            name=agent.name,
        )
        
        return agent, api_key
    
    async def get_by_id(self, agent_id: UUID) -> Agent | None:
        """Get an agent by ID."""
        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_name(self, name: str) -> Agent | None:
        """Get an agent by name."""
        result = await self.session.execute(
            select(Agent).where(Agent.name == name.lower())
        )
        return result.scalar_one_or_none()
    
    async def get_profile(self, agent: Agent) -> AgentProfile:
        """Get an agent's public profile with simulation count."""
        # Count simulations
        from agent_polis.simulations.db_models import Simulation
        result = await self.session.execute(
            select(func.count(Simulation.id))
            .where(Simulation.creator_id == agent.id)
        )
        simulation_count = result.scalar() or 0
        
        return AgentProfile(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            reputation_score=float(agent.reputation_score),
            verified=agent.verified,
            verification_method=agent.verification_method,
            status=agent.status,
            created_at=agent.created_at,
            last_active_at=agent.last_active_at,
            simulation_count=simulation_count,
        )
    
    async def get_stats(self, agent: Agent, monthly_limit: int) -> AgentStats:
        """Get agent usage statistics."""
        from agent_polis.simulations.db_models import Simulation
        
        # Total simulations
        total_result = await self.session.execute(
            select(func.count(Simulation.id))
            .where(Simulation.creator_id == agent.id)
        )
        total = total_result.scalar() or 0
        
        # Successful simulations
        success_result = await self.session.execute(
            select(func.count(Simulation.id))
            .where(Simulation.creator_id == agent.id)
            .where(Simulation.status == "completed")
        )
        successful = success_result.scalar() or 0
        
        # Failed simulations
        failed_result = await self.session.execute(
            select(func.count(Simulation.id))
            .where(Simulation.creator_id == agent.id)
            .where(Simulation.status == "failed")
        )
        failed = failed_result.scalar() or 0
        
        # TODO: Calculate prediction accuracy from outcome comparisons
        prediction_accuracy = None
        
        return AgentStats(
            total_simulations=total,
            successful_simulations=successful,
            failed_simulations=failed,
            prediction_accuracy=prediction_accuracy,
            simulations_this_month=agent.simulations_this_month,
            monthly_limit=monthly_limit,
        )
    
    async def update_reputation(
        self,
        agent: Agent,
        delta: Decimal,
        reason: str,
    ) -> None:
        """Update an agent's reputation score."""
        old_score = agent.reputation_score
        agent.reputation_score += delta
        
        # Ensure non-negative
        if agent.reputation_score < 0:
            agent.reputation_score = Decimal("0.00")
        
        # Record event
        event = AgentReputationChanged(
            stream_id=f"agent:{agent.id}",
            data={
                "agent_id": str(agent.id),
                "delta": str(delta),
                "old_score": str(old_score),
                "new_score": str(agent.reputation_score),
                "reason": reason,
            },
        )
        await self.event_store.append(event)
        await publish_event(event)
        
        logger.info(
            "Agent reputation updated",
            agent_id=str(agent.id),
            delta=str(delta),
            new_score=str(agent.reputation_score),
            reason=reason,
        )
    
    async def list_agents(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[AgentProfile], int]:
        """
        List agents with pagination.
        
        Returns:
            Tuple of (profiles, total_count)
        """
        # Build query
        query = select(Agent)
        count_query = select(func.count(Agent.id))
        
        if status:
            query = query.where(Agent.status == status)
            count_query = count_query.where(Agent.status == status)
        
        # Get total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get page of agents
        query = (
            query
            .order_by(Agent.reputation_score.desc(), Agent.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        
        result = await self.session.execute(query)
        agents = result.scalars().all()
        
        # Convert to profiles
        profiles = [await self.get_profile(a) for a in agents]
        
        return profiles, total
