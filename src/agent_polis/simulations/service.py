"""
Simulation service - business logic for simulation management.
"""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_polis.agents.db_models import Agent
from agent_polis.config import settings
from agent_polis.events.bus import publish_event
from agent_polis.events.store import EventStore
from agent_polis.events.types import (
    OutcomeActualized,
    OutcomePredicted,
    SimulationCompleted,
    SimulationCreated,
    SimulationFailed,
    SimulationMetered,
    SimulationStarted,
)
from agent_polis.simulations.db_models import Simulation
from agent_polis.simulations.models import (
    OutcomePrediction,
    ScenarioDefinition,
    SimulationCreate,
    SimulationResponse,
    SimulationResult,
    SimulationStatus,
)
from agent_polis.simulations.sandbox import SandboxExecutor, get_sandbox_executor

logger = structlog.get_logger()


class SimulationService:
    """Service for simulation management operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.event_store = EventStore(session)
        self.executor = get_sandbox_executor()
    
    async def create(
        self,
        data: SimulationCreate,
        creator: Agent,
    ) -> Simulation:
        """
        Create a new simulation.
        
        Does not execute the simulation - use run() for that.
        """
        # Check rate limits
        if not creator.can_run_simulation(settings.free_tier_simulations_per_month):
            raise ValueError(
                f"Monthly simulation limit ({settings.free_tier_simulations_per_month}) exceeded"
            )
        
        # Create simulation record
        simulation = Simulation(
            creator_id=creator.id,
            proposal_id=data.proposal_id,
            status="pending",
            scenario_definition=data.scenario.model_dump(),
            callback_url=data.callback_url,
        )
        
        self.session.add(simulation)
        await self.session.flush()
        
        # Record event
        event = SimulationCreated(
            stream_id=f"simulation:{simulation.id}",
            data={
                "simulation_id": str(simulation.id),
                "creator_id": str(creator.id),
                "scenario_name": data.scenario.name,
                "proposal_id": str(data.proposal_id) if data.proposal_id else None,
            },
        )
        await self.event_store.append(event, actor_id=str(creator.id))
        await publish_event(event)
        
        logger.info(
            "Simulation created",
            simulation_id=str(simulation.id),
            creator=creator.name,
            scenario=data.scenario.name,
        )
        
        return simulation
    
    async def run(
        self,
        simulation: Simulation,
        timeout_override: int | None = None,
        input_overrides: dict | None = None,
    ) -> SimulationResult:
        """
        Execute a simulation in the sandbox.
        
        This is the core functionality - running scenarios in isolation.
        """
        if simulation.status not in ["pending", "failed"]:
            raise ValueError(f"Simulation already {simulation.status}")
        
        # Update status
        simulation.status = "running"
        simulation.started_at = datetime.now(timezone.utc)
        await self.session.flush()
        
        # Record start event
        start_event = SimulationStarted(
            stream_id=f"simulation:{simulation.id}",
            data={
                "simulation_id": str(simulation.id),
            },
        )
        await self.event_store.append(start_event)
        await publish_event(start_event)
        
        # Parse scenario
        scenario = ScenarioDefinition(**simulation.scenario_definition)
        
        # Apply overrides
        timeout = timeout_override or scenario.timeout_seconds
        inputs = {**scenario.inputs}
        if input_overrides:
            inputs.update(input_overrides)
        
        # Execute in sandbox
        try:
            if not scenario.code:
                raise ValueError("No code provided in scenario")
            
            result = await self.executor.execute(
                code=scenario.code,
                inputs=inputs,
                environment=scenario.environment,
                timeout_seconds=timeout,
            )
            
            # Update simulation with result
            simulation.result = result.model_dump(mode='json')
            simulation.status = "completed" if result.success else "failed"
            simulation.completed_at = datetime.now(timezone.utc)
            
            # Increment agent's simulation count
            creator = await self.session.get(Agent, simulation.creator_id)
            if creator:
                creator.increment_simulation_count()
                creator.update_last_active()
            
            # Record completion/failure event
            if result.success:
                event = SimulationCompleted(
                    stream_id=f"simulation:{simulation.id}",
                    data={
                        "simulation_id": str(simulation.id),
                        "duration_ms": result.duration_ms,
                        "has_output": result.output is not None,
                    },
                )
            else:
                event = SimulationFailed(
                    stream_id=f"simulation:{simulation.id}",
                    data={
                        "simulation_id": str(simulation.id),
                        "error": result.error,
                    },
                )
            
            await self.event_store.append(event)
            await publish_event(event)
            
            # Record metering event
            meter_event = SimulationMetered(
                stream_id=f"agent:{simulation.creator_id}",
                data={
                    "agent_id": str(simulation.creator_id),
                    "simulation_id": str(simulation.id),
                    "duration_ms": result.duration_ms,
                    "success": result.success,
                },
            )
            await self.event_store.append(meter_event)
            await publish_event(meter_event)
            
            logger.info(
                "Simulation executed",
                simulation_id=str(simulation.id),
                success=result.success,
                duration_ms=result.duration_ms,
            )
            
            # Send webhook callback if configured
            if simulation.callback_url:
                await self._send_callback(simulation, result)
            
            return result
            
        except Exception as e:
            # Handle execution errors
            simulation.status = "failed"
            simulation.completed_at = datetime.now(timezone.utc)
            simulation.result = {
                "success": False,
                "error": str(e),
            }
            
            event = SimulationFailed(
                stream_id=f"simulation:{simulation.id}",
                data={
                    "simulation_id": str(simulation.id),
                    "error": str(e),
                },
            )
            await self.event_store.append(event)
            await publish_event(event)
            
            logger.error(
                "Simulation failed",
                simulation_id=str(simulation.id),
                error=str(e),
                exc_info=e,
            )
            
            raise
    
    async def record_prediction(
        self,
        simulation: Simulation,
        prediction: OutcomePrediction,
        predictor: Agent,
    ) -> None:
        """Record an outcome prediction for a simulation."""
        simulation.predicted_outcome = prediction.model_dump()
        
        event = OutcomePredicted(
            stream_id=f"simulation:{simulation.id}",
            data={
                "simulation_id": str(simulation.id),
                "predictor_id": str(predictor.id),
                "predicted_success": prediction.predicted_success,
                "confidence": prediction.confidence,
            },
        )
        await self.event_store.append(event, actor_id=str(predictor.id))
        await publish_event(event)
        
        logger.info(
            "Prediction recorded",
            simulation_id=str(simulation.id),
            predictor=predictor.name,
            predicted_success=prediction.predicted_success,
        )
    
    async def record_actual_outcome(
        self,
        simulation: Simulation,
        actual: dict,
        recorder: Agent,
    ) -> None:
        """Record the actual outcome after real-world execution."""
        simulation.actual_outcome = actual
        
        event = OutcomeActualized(
            stream_id=f"simulation:{simulation.id}",
            data={
                "simulation_id": str(simulation.id),
                "recorder_id": str(recorder.id),
                "actual": actual,
            },
        )
        await self.event_store.append(event, actor_id=str(recorder.id))
        await publish_event(event)
        
        # TODO: Compare prediction vs actual, update predictor reputation
        
        logger.info(
            "Actual outcome recorded",
            simulation_id=str(simulation.id),
            recorder=recorder.name,
        )
    
    async def get_by_id(self, simulation_id: UUID) -> Simulation | None:
        """Get a simulation by ID."""
        result = await self.session.execute(
            select(Simulation).where(Simulation.id == simulation_id)
        )
        return result.scalar_one_or_none()
    
    async def list_by_creator(
        self,
        creator_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[Simulation], int]:
        """List simulations by creator."""
        query = select(Simulation).where(Simulation.creator_id == creator_id)
        count_query = select(func.count(Simulation.id)).where(
            Simulation.creator_id == creator_id
        )
        
        if status:
            query = query.where(Simulation.status == status)
            count_query = count_query.where(Simulation.status == status)
        
        # Get total
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get page
        query = (
            query
            .order_by(Simulation.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        
        result = await self.session.execute(query)
        simulations = result.scalars().all()
        
        return list(simulations), total
    
    async def _send_callback(
        self,
        simulation: Simulation,
        result: SimulationResult,
    ) -> None:
        """Send webhook callback for completed simulation."""
        import httpx
        
        if not simulation.callback_url:
            return
        
        payload = {
            "event": "simulation.completed",
            "simulation_id": str(simulation.id),
            "status": simulation.status,
            "success": result.success,
            "result": result.model_dump(mode='json') if result else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    simulation.callback_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                logger.info(
                    "Webhook callback sent",
                    simulation_id=str(simulation.id),
                    url=simulation.callback_url,
                    status_code=response.status_code,
                )
        except Exception as e:
            logger.error(
                "Webhook callback failed",
                simulation_id=str(simulation.id),
                url=simulation.callback_url,
                error=str(e),
            )
    
    def to_response(self, simulation: Simulation) -> SimulationResponse:
        """Convert a Simulation to SimulationResponse."""
        return SimulationResponse(
            id=simulation.id,
            creator_id=simulation.creator_id,
            proposal_id=simulation.proposal_id,
            status=SimulationStatus(simulation.status),
            scenario=ScenarioDefinition(**simulation.scenario_definition),
            result=SimulationResult(**simulation.result) if simulation.result else None,
            prediction=OutcomePrediction(**simulation.predicted_outcome)
                if simulation.predicted_outcome else None,
            actual_outcome=simulation.actual_outcome,
            e2b_sandbox_id=simulation.e2b_sandbox_id,
            created_at=simulation.created_at,
            started_at=simulation.started_at,
            completed_at=simulation.completed_at,
        )
