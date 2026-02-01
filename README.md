# 🔍 Agent Polis

**Impact Preview for AI Agents - "Terraform plan" for autonomous AI actions**

<!-- mcp-name: io.github.agent-polis/impact-preview -->

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

## 🚀 Quick Start (2 minutes)

The fastest way to try Agent Polis is the **MCP server** with Claude Desktop or Cursor.

### 1. Install & Run

```bash
pip install impact-preview
impact-preview-mcp
```

### 2. Configure Claude Desktop

Add to your config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
    "mcpServers": {
        "impact-preview": {
            "url": "http://localhost:8000/mcp"
        }
    }
}
```

### 3. Try It

Ask Claude to edit a file - it now has these tools:

| Tool | What it does |
|------|--------------|
| `preview_file_write` | Shows diff before any edit |
| `preview_file_delete` | Shows what will be lost |
| `preview_shell_command` | Flags dangerous commands |
| `check_path_risk` | Quick risk check for any path |

**Example prompt:**
> "Preview what would happen if you changed the database URL in config.yaml to point to production"

Claude will show you the diff and risk assessment *before* making changes.

---

## 📦 Full Server Installation

For the complete approval workflow with dashboard and API:

```bash
# Using Docker (recommended)
docker-compose up -d

# Or locally
pip install impact-preview
impact-preview
```

### Register an Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name": "my-agent", "description": "My AI coding assistant"}'
```

### Submit Action → Review → Approve

```bash
# Submit
curl -X POST http://localhost:8000/api/v1/actions \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action_type": "file_write", "target": "/app/config.yaml", "description": "Update DB URL", "payload": {"content": "db: prod"}}'

# Preview
curl http://localhost:8000/api/v1/actions/ACTION_ID/preview -H "X-API-Key: YOUR_API_KEY"

# Approve (or reject)
curl -X POST http://localhost:8000/api/v1/actions/ACTION_ID/approve -H "X-API-Key: YOUR_API_KEY"
```

---

## 🐍 SDK Integration

Wrap your agent's dangerous operations:

```python
from agent_polis import AgentPolisClient

client = AgentPolisClient(api_url="http://localhost:8000", api_key="YOUR_KEY")

# Decorator approach - blocks until human approves
@client.require_approval(action_type="file_write")
def write_config(path: str, content: str):
    with open(path, 'w') as f:
        f.write(content)

# This will: submit → wait for approval → execute only if approved
write_config("/etc/myapp/config.yaml", "new content")
```

## 🖥️ Dashboard

Launch the Streamlit dashboard to review pending actions:

```bash
pip install impact-preview[ui]
streamlit run src/agent_polis/ui/app.py
```

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
git clone https://github.com/agent-polis/Leviathan.git
cd Leviathan
pip install -e .[dev]
pre-commit install
pytest
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

Built for developers who want AI agents they can actually trust.
