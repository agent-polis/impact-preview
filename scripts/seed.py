#!/usr/bin/env python3
"""
Seed script for development data.

Usage:
    python scripts/seed.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_polis.shared.db import async_session_factory, init_db
from agent_polis.agents.service import AgentService
from agent_polis.agents.models import AgentCreate
from agent_polis.simulations.service import SimulationService
from agent_polis.simulations.models import SimulationCreate, ScenarioDefinition


async def seed_data():
    """Create development seed data."""
    print("Initializing database...")
    await init_db()
    
    async with async_session_factory() as session:
        agent_service = AgentService(session)
        sim_service = SimulationService(session)
        
        # Create demo agent
        print("Creating demo agent...")
        try:
            agent, api_key = await agent_service.register(
                AgentCreate(
                    name="demo-agent",
                    description="A demonstration agent for testing Agent Polis features",
                )
            )
            print(f"  Created agent: {agent.name}")
            print(f"  API Key: {api_key}")
            print("  (Save this key - it won't be shown again!)")
        except ValueError as e:
            print(f"  Agent already exists or error: {e}")
            # Get existing agent
            agent = await agent_service.get_by_name("demo-agent")
            if agent:
                print(f"  Using existing agent: {agent.name}")
        
        if agent:
            # Create sample simulations
            print("\nCreating sample simulations...")
            
            scenarios = [
                {
                    "name": "Hello World",
                    "description": "Simple test simulation",
                    "code": "result = {'message': 'Hello from Agent Polis!'}",
                    "inputs": {},
                },
                {
                    "name": "Math Operations",
                    "description": "Test basic math in sandbox",
                    "code": """
# Test math operations
a = inputs.get('a', 10)
b = inputs.get('b', 5)

result = {
    'sum': a + b,
    'difference': a - b,
    'product': a * b,
    'quotient': a / b if b != 0 else None,
}
print(f"Calculated results for a={a}, b={b}")
""",
                    "inputs": {"a": 42, "b": 7},
                },
                {
                    "name": "Data Processing",
                    "description": "Process a list of items",
                    "code": """
items = inputs.get('items', [1, 2, 3, 4, 5])

processed = [x * 2 for x in items]
total = sum(processed)

result = {
    'original': items,
    'processed': processed,
    'total': total,
}
""",
                    "inputs": {"items": [10, 20, 30, 40, 50]},
                },
            ]
            
            for scenario_data in scenarios:
                try:
                    simulation = await sim_service.create(
                        SimulationCreate(
                            scenario=ScenarioDefinition(**scenario_data, timeout_seconds=60),
                        ),
                        creator=agent,
                    )
                    print(f"  Created simulation: {scenario_data['name']} ({simulation.id})")
                except Exception as e:
                    print(f"  Error creating {scenario_data['name']}: {e}")
        
        await session.commit()
    
    print("\nSeed complete!")
    print("\nTo run the server:")
    print("  uvicorn agent_polis.main:app --reload")
    print("\nOr use Docker:")
    print("  docker-compose up -d")


if __name__ == "__main__":
    asyncio.run(seed_data())
