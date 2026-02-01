"""
CrewAI integration for Agent Polis.

This module provides tools and callbacks that allow CrewAI agents to use
Agent Polis for simulation-based governance.

Usage:
    from agent_polis.integrations.crewai import AgentPolisTool, SimulationCallback
    
    # As a tool
    tool = AgentPolisTool(api_url="http://localhost:8000", api_key="ap_...")
    
    # As a callback
    callback = SimulationCallback(api_url="http://localhost:8000", api_key="ap_...")
"""

from typing import Any, Type

import httpx

# Try to import CrewAI - it's optional
try:
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    BaseTool = object
    BaseModel = object
    Field = lambda **kwargs: None


class SimulationInput(BaseModel if CREWAI_AVAILABLE else object):
    """Input schema for simulation tool."""
    
    name: str = Field(description="Name of the simulation scenario")
    description: str = Field(description="Description of what to simulate")
    code: str = Field(description="Python code to execute in sandbox")
    inputs: dict = Field(default_factory=dict, description="Input variables for the code")
    timeout_seconds: int = Field(default=60, description="Execution timeout")


class AgentPolisTool(BaseTool if CREWAI_AVAILABLE else object):
    """
    CrewAI tool for running simulations via Agent Polis.
    
    This allows agents to test scenarios in a sandbox before committing.
    Use this for decision-making, risk assessment, and plan validation.
    """
    
    name: str = "agent_polis_simulate"
    description: str = (
        "Run a simulation in Agent Polis to test a scenario before committing to it. "
        "Useful for validating plans, testing code changes, or assessing risks. "
        "The simulation runs in an isolated sandbox environment."
    )
    args_schema: Type[BaseModel] = SimulationInput if CREWAI_AVAILABLE else None
    
    api_url: str = "http://localhost:8000"
    api_key: str = ""
    timeout: int = 120
    
    def __init__(self, api_url: str = "http://localhost:8000", api_key: str = "", **kwargs):
        """
        Initialize the Agent Polis tool.
        
        Args:
            api_url: Base URL of the Agent Polis API
            api_key: API key for authentication
        """
        if CREWAI_AVAILABLE:
            super().__init__(**kwargs)
        self.api_url = api_url
        self.api_key = api_key
    
    def _run(
        self,
        name: str,
        description: str,
        code: str,
        inputs: dict | None = None,
        timeout_seconds: int = 60,
    ) -> str:
        """
        Run a simulation synchronously.
        
        Returns a summary of the simulation result.
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            }
            
            # Create simulation
            create_response = httpx.post(
                f"{self.api_url}/api/v1/simulations",
                headers=headers,
                json={
                    "scenario": {
                        "name": name,
                        "description": description,
                        "code": code,
                        "inputs": inputs or {},
                        "timeout_seconds": timeout_seconds,
                    }
                },
                timeout=self.timeout,
            )
            
            if create_response.status_code != 201:
                return f"Failed to create simulation: {create_response.text}"
            
            sim_data = create_response.json()
            sim_id = sim_data["id"]
            
            # Run simulation
            run_response = httpx.post(
                f"{self.api_url}/api/v1/simulations/{sim_id}/run",
                headers=headers,
                json={},
                timeout=timeout_seconds + 30,
            )
            
            if run_response.status_code != 200:
                return f"Failed to run simulation: {run_response.text}"
            
            result = run_response.json()
            
            # Format result
            if result.get("success"):
                output_str = str(result.get("output", "No output"))
                stdout_str = result.get("stdout", "")
                return (
                    f"Simulation '{name}' completed successfully.\n"
                    f"Duration: {result.get('duration_ms', 'unknown')}ms\n"
                    f"Output: {output_str}\n"
                    f"Stdout: {stdout_str[:500] if stdout_str else 'None'}"
                )
            else:
                return (
                    f"Simulation '{name}' failed.\n"
                    f"Error: {result.get('error', 'Unknown error')}\n"
                    f"Stderr: {result.get('stderr', 'None')[:500]}"
                )
                
        except httpx.TimeoutException:
            return f"Simulation timed out after {self.timeout} seconds"
        except Exception as e:
            return f"Simulation error: {str(e)}"


class AgentPolisClient:
    """
    Standalone client for Agent Polis API.
    
    Use this when you need more control than the CrewAI tool provides.
    """
    
    def __init__(self, api_url: str = "http://localhost:8000", api_key: str = ""):
        """
        Initialize the client.
        
        Args:
            api_url: Base URL of the Agent Polis API
            api_key: API key for authentication
        """
        self.api_url = api_url
        self.api_key = api_key
        self._client = httpx.Client(
            base_url=api_url,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key,
            },
            timeout=120,
        )
    
    def health_check(self) -> dict:
        """Check API health."""
        response = self._client.get("/health")
        response.raise_for_status()
        return response.json()
    
    def get_agent_card(self) -> dict:
        """Get the A2A agent card."""
        response = self._client.get("/.well-known/agent.json")
        response.raise_for_status()
        return response.json()
    
    def get_me(self) -> dict:
        """Get current agent profile."""
        response = self._client.get("/api/v1/agents/me")
        response.raise_for_status()
        return response.json()
    
    def create_simulation(
        self,
        name: str,
        code: str,
        description: str | None = None,
        inputs: dict | None = None,
        timeout_seconds: int = 60,
    ) -> dict:
        """Create a new simulation."""
        response = self._client.post(
            "/api/v1/simulations",
            json={
                "scenario": {
                    "name": name,
                    "description": description or "",
                    "code": code,
                    "inputs": inputs or {},
                    "timeout_seconds": timeout_seconds,
                }
            },
        )
        response.raise_for_status()
        return response.json()
    
    def run_simulation(
        self,
        simulation_id: str,
        timeout_override: int | None = None,
        input_overrides: dict | None = None,
    ) -> dict:
        """Run a simulation."""
        body = {}
        if timeout_override:
            body["timeout_override"] = timeout_override
        if input_overrides:
            body["input_overrides"] = input_overrides
        
        response = self._client.post(
            f"/api/v1/simulations/{simulation_id}/run",
            json=body,
        )
        response.raise_for_status()
        return response.json()
    
    def get_simulation(self, simulation_id: str) -> dict:
        """Get simulation details."""
        response = self._client.get(f"/api/v1/simulations/{simulation_id}")
        response.raise_for_status()
        return response.json()
    
    def list_simulations(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> dict:
        """List simulations."""
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        
        response = self._client.get("/api/v1/simulations", params=params)
        response.raise_for_status()
        return response.json()
    
    def simulate_and_run(
        self,
        name: str,
        code: str,
        description: str | None = None,
        inputs: dict | None = None,
        timeout_seconds: int = 60,
    ) -> dict:
        """Create and immediately run a simulation."""
        sim = self.create_simulation(
            name=name,
            code=code,
            description=description,
            inputs=inputs,
            timeout_seconds=timeout_seconds,
        )
        return self.run_simulation(sim["id"])
    
    def close(self):
        """Close the client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_crewai_tool(api_url: str, api_key: str) -> "AgentPolisTool":
    """
    Factory function to create an Agent Polis tool for CrewAI.
    
    Args:
        api_url: Base URL of the Agent Polis API
        api_key: API key for authentication
        
    Returns:
        Configured AgentPolisTool instance
        
    Raises:
        ImportError: If CrewAI is not installed
    """
    if not CREWAI_AVAILABLE:
        raise ImportError(
            "CrewAI is not installed. Install it with: pip install impact-preview[crewai]"
        )
    
    return AgentPolisTool(api_url=api_url, api_key=api_key)
