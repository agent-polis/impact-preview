"""
Agent Polis - Impact Preview for AI Agents

See exactly what will change before any AI agent action executes.
Like "terraform plan" for autonomous AI agents.
"""

__version__ = "0.2.1"
__author__ = "Agent Polis Contributors"

from agent_polis.main import app
from agent_polis.sdk import AgentPolisClient, ActionRejectedError, ActionTimedOutError

__all__ = [
    "app",
    "__version__",
    # SDK
    "AgentPolisClient",
    "ActionRejectedError",
    "ActionTimedOutError",
]
