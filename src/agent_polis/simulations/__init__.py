"""
Simulation module - the core wedge of Agent Polis.

This module provides simulation-integrated governance: the ability to test
scenarios in a sandbox before committing to them. This is what differentiates
Agent Polis from other governance solutions.
"""

from agent_polis.simulations.router import router
from agent_polis.simulations.models import (
    SimulationCreate,
    SimulationResponse,
    SimulationRunRequest,
    SimulationResult,
)
from agent_polis.simulations.service import SimulationService

__all__ = [
    "router",
    "SimulationCreate",
    "SimulationResponse",
    "SimulationRunRequest",
    "SimulationResult",
    "SimulationService",
]
