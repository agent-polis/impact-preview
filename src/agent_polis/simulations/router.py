"""
Simulation API routes.

These endpoints are the core wedge - simulation-integrated governance.
"""

from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_polis.shared.db import get_db
from agent_polis.shared.security import CurrentAgent
from agent_polis.simulations.models import (
    OutcomePrediction,
    SimulationCreate,
    SimulationListResponse,
    SimulationResponse,
    SimulationRunRequest,
    SimulationResult,
)
from agent_polis.simulations.service import SimulationService

logger = structlog.get_logger()
router = APIRouter()


@router.post("/", response_model=SimulationResponse, status_code=status.HTTP_201_CREATED)
async def create_simulation(
    data: SimulationCreate,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SimulationResponse:
    """
    Create a new simulation scenario.
    
    This creates the simulation but does not execute it.
    Use POST /simulations/{id}/run to execute.
    """
    service = SimulationService(db)
    
    try:
        simulation = await service.create(data, agent)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return service.to_response(simulation)


@router.get("/", response_model=SimulationListResponse)
async def list_simulations(
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
) -> SimulationListResponse:
    """List the current agent's simulations."""
    service = SimulationService(db)
    simulations, total = await service.list_by_creator(
        creator_id=agent.id,
        page=page,
        page_size=page_size,
        status=status_filter,
    )
    
    return SimulationListResponse(
        simulations=[service.to_response(s) for s in simulations],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{simulation_id}", response_model=SimulationResponse)
async def get_simulation(
    simulation_id: UUID,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SimulationResponse:
    """Get a simulation by ID."""
    service = SimulationService(db)
    simulation = await service.get_by_id(simulation_id)
    
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found",
        )
    
    # Check ownership (or make public later)
    if simulation.creator_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this simulation",
        )
    
    return service.to_response(simulation)


@router.post("/{simulation_id}/run", response_model=SimulationResult)
async def run_simulation(
    simulation_id: UUID,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: SimulationRunRequest | None = None,
) -> SimulationResult:
    """
    Execute a simulation in the sandbox.
    
    This is the core functionality - run your scenario in isolation
    before committing to it in the real world.
    """
    service = SimulationService(db)
    simulation = await service.get_by_id(simulation_id)
    
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found",
        )
    
    if simulation.creator_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to run this simulation",
        )
    
    try:
        result = await service.run(
            simulation,
            timeout_override=request.timeout_override if request else None,
            input_overrides=request.input_overrides if request else None,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{simulation_id}/results", response_model=SimulationResult | None)
async def get_simulation_results(
    simulation_id: UUID,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SimulationResult | None:
    """Get the results of a completed simulation."""
    service = SimulationService(db)
    simulation = await service.get_by_id(simulation_id)
    
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found",
        )
    
    if simulation.creator_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this simulation",
        )
    
    if not simulation.result:
        return None
    
    return SimulationResult(**simulation.result)


@router.post("/{simulation_id}/predict")
async def record_prediction(
    simulation_id: UUID,
    prediction: OutcomePrediction,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Record a prediction about the simulation outcome.
    
    Predictions can be compared against actual outcomes later
    to track prediction accuracy and update reputation.
    """
    service = SimulationService(db)
    simulation = await service.get_by_id(simulation_id)
    
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found",
        )
    
    await service.record_prediction(simulation, prediction, agent)
    
    return {"status": "prediction_recorded", "simulation_id": str(simulation_id)}


@router.post("/{simulation_id}/actualize")
async def record_actual_outcome(
    simulation_id: UUID,
    actual: dict[str, Any],
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Record the actual outcome after real-world execution.
    
    This allows comparing simulated predictions with reality,
    which is essential for calibrating the governance system.
    """
    service = SimulationService(db)
    simulation = await service.get_by_id(simulation_id)
    
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found",
        )
    
    if simulation.creator_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this simulation",
        )
    
    await service.record_actual_outcome(simulation, actual, agent)
    
    return {"status": "outcome_recorded", "simulation_id": str(simulation_id)}


@router.get("/{simulation_id}/events")
async def get_simulation_events(
    simulation_id: UUID,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    """
    Get the event history for a simulation.
    
    This provides a complete audit trail of everything that happened
    with this simulation - useful for compliance and debugging.
    """
    from agent_polis.events.store import EventStore
    
    service = SimulationService(db)
    simulation = await service.get_by_id(simulation_id)
    
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation not found",
        )
    
    if simulation.creator_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this simulation",
        )
    
    event_store = EventStore(db)
    events = await event_store.get_stream(f"simulation:{simulation_id}")
    
    return [
        {
            "id": str(e.id),
            "type": e.event_type,
            "data": e.event_data,
            "metadata": e.event_metadata,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
