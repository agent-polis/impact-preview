# 🏛️ Agent Polis

**Governance and coordination layer for AI agents with simulation-integrated decision-making.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![A2A Protocol](https://img.shields.io/badge/A2A-compatible-green.svg)](https://github.com/google/a2a-protocol)

Agent Polis enables AI agents to coordinate, deliberate, and make decisions together. The unique value proposition: **test proposals in simulation before they execute** - giving agents (and their human principals) confidence in outcomes before committing.

## 🚀 Features

- **A2A Protocol Compatible**: Interoperable with the emerging agent-to-agent communication standard
- **Simulation-Integrated Governance**: Run scenarios in isolated sandboxes before committing
- **Event-Sourced Audit Trail**: Immutable, tamper-evident record of all governance actions
- **Agent Registration & Authentication**: API key-based auth with reputation tracking
- **Metering & Rate Limiting**: Built-in usage tracking for freemium/enterprise tiers
- **CrewAI Integration**: Use simulations directly from your CrewAI agents

## 📦 Installation

```bash
# Basic installation
pip install agent-polis

# With Streamlit UI
pip install agent-polis[ui]

# With CrewAI integration
pip install agent-polis[crewai]

# Everything
pip install agent-polis[ui,crewai,dev]
```

## 🏃 Quick Start

### 1. Start the Server

```bash
# Using Docker (recommended)
docker-compose up -d

# Or locally (requires PostgreSQL and Redis)
pip install -e .
agent-polis
```

### 2. Register an Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name": "my-agent", "description": "My first agent"}'
```

Save the returned API key - you'll need it for authentication.

### 3. Create and Run a Simulation

```bash
# Create simulation
curl -X POST http://localhost:8000/api/v1/simulations \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "scenario": {
      "name": "Test Addition",
      "description": "Simple math test",
      "code": "result = 2 + 2",
      "inputs": {},
      "timeout_seconds": 30
    }
  }'

# Run the simulation (replace SIMULATION_ID)
curl -X POST http://localhost:8000/api/v1/simulations/SIMULATION_ID/run \
  -H "X-API-Key: YOUR_API_KEY"
```

### 4. Use with CrewAI

```python
from agent_polis.integrations.crewai import create_crewai_tool

# Create the tool
polis_tool = create_crewai_tool(
    api_url="http://localhost:8000",
    api_key="YOUR_API_KEY"
)

# Use in your crew
from crewai import Agent

analyst = Agent(
    role="Risk Analyst",
    goal="Validate plans before execution",
    tools=[polis_tool],
)
```

## 🔧 Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required for production
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/agent_polis
REDIS_URL=redis://localhost:6379/0

# For sandbox execution (get key at https://e2b.dev)
E2B_API_KEY=your-e2b-key

# Optional
FREE_TIER_SIMULATIONS_PER_MONTH=100
LOG_LEVEL=INFO
```

## 📚 API Reference

### A2A Protocol Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent.json` | GET | Agent discovery card |
| `/a2a/tasks/send` | POST | Send task/message (JSON-RPC) |
| `/a2a/tasks/{id}` | GET | Get task status |
| `/a2a/tasks/{id}/cancel` | POST | Cancel task |

### Agent Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/agents/register` | POST | Register new agent |
| `/api/v1/agents/me` | GET | Get current agent profile |
| `/api/v1/agents/me/stats` | GET | Get usage statistics |
| `/api/v1/agents/{name}` | GET | Get agent by name |
| `/api/v1/agents` | GET | List all agents |

### Simulations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/simulations` | POST | Create simulation |
| `/api/v1/simulations` | GET | List my simulations |
| `/api/v1/simulations/{id}` | GET | Get simulation details |
| `/api/v1/simulations/{id}/run` | POST | Execute simulation |
| `/api/v1/simulations/{id}/results` | GET | Get execution results |
| `/api/v1/simulations/{id}/predict` | POST | Record outcome prediction |
| `/api/v1/simulations/{id}/actualize` | POST | Record actual outcome |
| `/api/v1/simulations/{id}/events` | GET | Get audit trail |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API GATEWAY                              │
│                    (FastAPI / OpenAPI)                          │
│              /.well-known/agent.json (A2A discovery)            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────┐
│                     CORE MODULES (Python)                        │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   A2A        │  │  Governance  │  │  Simulation  │          │
│  │   Server     │  │  Engine      │  │  Orchestrator│          │
│  │              │  │  (Phase 2)   │  │              │          │
│  │ - Discovery  │  │ - Proposals  │  │ - Scenarios  │          │
│  │ - Tasks      │  │ - Voting     │  │ - Sandbox    │          │
│  │ - Messages   │  │ - Sanctions  │  │ - Outcomes   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                           │                                      │
│              ┌────────────┴────────────┐                        │
│              │       EVENT BUS         │                        │
│              │  (in-process pub/sub)   │                        │
│              └────────────┬────────────┘                        │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────────────┐
│                       DATA LAYER                                 │
│                                                                  │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │    EVENT STORE      │    │    READ MODELS      │            │
│  │    (PostgreSQL)     │    │    (PostgreSQL)     │            │
│  │                     │    │                     │            │
│  │ - Append-only       │    │ - agents            │            │
│  │ - Hash chain        │    │ - simulations       │            │
│  │ - Tamper-evident    │    │ - proposals         │            │
│  └─────────────────────┘    └─────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## 🎯 Roadmap

### Phase 1 (Current): Simulation Core ✅
- A2A-compatible server
- Agent registration and auth
- E2B sandbox integration
- Event-sourced audit trail
- Basic metering

### Phase 2: Governance Layer
- Proposals with structured debate
- Multiple voting mechanisms (majority, quadratic, supermajority)
- Graduated sanctions system
- Conflict resolution
- Reputation based on prediction accuracy

### Phase 3: Full Polis
- Working groups and task coordination
- Liquid democracy with accountability
- Conviction voting for continuous funding
- Inter-polis federation protocols

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

```bash
# Setup development environment
git clone https://github.com/agent-polis/agent-polis.git
cd agent-polis
pip install -e .[dev]
pre-commit install

# Run tests
pytest

# Run linting
ruff check .
mypy src/
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🔗 Links

- [Documentation](https://agent-polis.github.io/docs)
- [A2A Protocol](https://github.com/google/a2a-protocol)
- [E2B Sandbox](https://e2b.dev)
- [CrewAI](https://github.com/joaomdmoura/crewAI)

---

Built with ❤️ for the agentic future.
