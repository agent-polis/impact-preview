# 🔍 Agent Polis

**Impact Preview for AI Agents - "Terraform plan" for autonomous AI actions**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

> See exactly what will change before any AI agent action executes.

Agent Polis intercepts proposed actions from autonomous AI agents, analyzes their impact, shows you a diff preview of what will change, and only executes after human approval. Stop worrying about your AI agent deleting your production database.

## 🎯 The Problem

Autonomous AI agents are powerful but dangerous. Recent incidents:

- **Replit Agent** deleted a production database, then lied about it
- **Cursor YOLO mode** deleted an entire system including itself
- **Claude Code** learned to bypass safety restrictions via shell scripts

Developers want to use AI agents but don't trust them. Current solutions show what agents *want* to do, not what *will* happen. There's no "terraform plan" equivalent for AI agent actions.

## 🚀 The Solution

```
AI Agent proposes action → Agent Polis analyzes impact → Human reviews diff → Approve/Reject → Execute
```

```diff
# Example: Agent wants to write to config.yaml
- database_url: postgresql://localhost:5432/dev
+ database_url: postgresql://prod-server:5432/production
! WARNING: Production database URL detected (CRITICAL RISK)
```

## ✨ Features

- **Impact Preview**: See file diffs, risk assessment, and warnings before execution
- **Approval Workflow**: Approve, reject, or modify proposed actions
- **Risk Assessment**: Automatic detection of high-risk operations (production data, system files, etc.)
- **Audit Trail**: Event-sourced log of every proposed and executed action
- **SDK Integration**: Easy `@require_approval` decorator for your agent code
- **Dashboard**: Streamlit UI for reviewing and approving actions

## 📦 Installation

```bash
pip install agent-polis
```

## 🏃 Quick Start

### 1. Start the Server

```bash
# Using Docker (recommended)
docker-compose up -d

# Or locally
pip install -e .
agent-polis
```

### 2. Register an Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name": "my-agent", "description": "My AI coding assistant"}'
```

Save the returned API key.

### 3. Submit an Action for Approval

```bash
curl -X POST http://localhost:8000/api/v1/actions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "action_type": "file_write",
    "target": "/app/config.yaml",
    "description": "Update database connection string",
    "payload": {
      "content": "database_url: postgresql://prod:5432/mydb"
    }
  }'
```

### 4. Review the Impact Preview

```bash
curl http://localhost:8000/api/v1/actions/ACTION_ID/preview \
  -H "X-API-Key: YOUR_API_KEY"
```

Response:
```json
{
  "risk_level": "high",
  "risk_factors": ["Production pattern detected: prod"],
  "file_changes": [{
    "path": "/app/config.yaml",
    "operation": "modify",
    "diff": "...",
    "lines_added": 1,
    "lines_removed": 1
  }],
  "warnings": ["This change affects production configuration"]
}
```

### 5. Approve or Reject

```bash
# Approve
curl -X POST http://localhost:8000/api/v1/actions/ACTION_ID/approve \
  -H "X-API-Key: YOUR_API_KEY"

# Or reject
curl -X POST http://localhost:8000/api/v1/actions/ACTION_ID/reject \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"reason": "Too risky for production"}'
```

## 🐍 SDK Usage

Use the SDK to wrap your agent's dangerous operations:

```python
from agent_polis.sdk import AgentPolisClient

client = AgentPolisClient(
    api_url="http://localhost:8000",
    api_key="YOUR_API_KEY"
)

# Decorator approach - blocks until approved
@client.require_approval(action_type="file_write")
def write_config(path: str, content: str):
    with open(path, 'w') as f:
        f.write(content)

# Now this will:
# 1. Submit for approval
# 2. Wait for human to approve/reject
# 3. Execute only if approved
write_config("/etc/myapp/config.yaml", "new content")

# Or manual approach
action = client.submit_action(
    action_type="file_delete",
    target="/important/file.txt",
    description="Clean up old data",
)

# Show preview to user
preview = client.get_preview(action["id"])
print(f"Risk: {preview['risk_level']}")
print(f"Changes: {preview['summary']}")

# Wait for approval
client.wait_for_approval(action["id"], timeout=300)

# Execute after approval
client.execute(action["id"])
```

## 🖥️ Dashboard

Launch the Streamlit dashboard to review pending actions:

```bash
streamlit run src/agent_polis/ui/app.py
```

![Dashboard Screenshot](docs/images/dashboard.png)

## 📚 API Reference

### Actions API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/actions` | POST | Submit action for approval |
| `/api/v1/actions` | GET | List your actions |
| `/api/v1/actions/pending` | GET | List pending approvals |
| `/api/v1/actions/{id}` | GET | Get action details |
| `/api/v1/actions/{id}/preview` | GET | Get impact preview |
| `/api/v1/actions/{id}/diff` | GET | Get diff output |
| `/api/v1/actions/{id}/approve` | POST | Approve action |
| `/api/v1/actions/{id}/reject` | POST | Reject action |
| `/api/v1/actions/{id}/execute` | POST | Execute approved action |

### Action Types

- `file_write` - Write content to a file
- `file_create` - Create a new file
- `file_delete` - Delete a file
- `file_move` - Move/rename a file
- `db_query` - Execute a database query (read)
- `db_execute` - Execute a database statement (write)
- `api_call` - Make an HTTP request
- `shell_command` - Run a shell command
- `custom` - Custom action type

### Risk Levels

- **Low**: Read operations, safe changes
- **Medium**: Write operations to non-critical files
- **High**: Delete operations, system files
- **Critical**: Production data, irreversible changes

## 🔧 Configuration

```bash
# .env
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/agent_polis
REDIS_URL=redis://localhost:6379/0

# Optional
FREE_TIER_ACTIONS_PER_MONTH=100
LOG_LEVEL=INFO
```

## 🗺️ Roadmap

| Version | Focus | Status |
|---------|-------|--------|
| v0.2.0 | File operation preview | Current |
| v0.3.0 | Database operation preview | Planned |
| v0.4.0 | API call preview | Planned |
| v0.5.0 | IDE integrations (Cursor, VS Code) | Planned |
| v1.0.0 | Production ready | Planned |

## 🤝 Contributing

```bash
git clone https://github.com/agent-polis/agent-polis.git
cd agent-polis
pip install -e .[dev]
pre-commit install
pytest
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

Built for developers who want AI agents they can actually trust.
