# Code Mapping: v0.1 → v0.2 Pivot

This document maps existing code to its role in the pivoted product.

---

## Directory Structure Comparison

```
CURRENT (v0.1 - Agent Polis)          PIVOT (v0.2 - Impact Preview)
================================      ================================
src/agent_polis/                      src/leviathan/  (or keep name)
├── a2a/                              ├── intercept/
│   ├── router.py      ────────────▶  │   ├── router.py      (action submission)
│   ├── models.py      ────────────▶  │   ├── models.py      (action schemas)
│   └── task_store.py  ────────────▶  │   └── action_store.py (pending actions)
│                                     │
├── agents/            ────────────▶  ├── agents/            (UNCHANGED)
│   ├── router.py                     │   ├── router.py
│   ├── service.py                    │   ├── service.py
│   └── db_models.py                  │   └── db_models.py
│                                     │
├── simulations/                      ├── preview/
│   ├── router.py      ────────────▶  │   ├── router.py      (preview endpoints)
│   ├── service.py     ────────────▶  │   ├── service.py     (impact analysis)
│   ├── sandbox.py     ────────────▶  │   ├── sandbox.py     (dry-run execution)
│   └── models.py      ────────────▶  │   └── models.py      (preview schemas)
│                                     │
├── events/            ────────────▶  ├── events/            (UNCHANGED)
│   ├── store.py                      │   ├── store.py       (audit trail)
│   ├── bus.py                        │   ├── bus.py
│   └── types.py       ────────────▶  │   └── types.py       (new event types)
│                                     │
├── governance/        ────────────▶  │   (REMOVE - not needed for MVP)
│                                     │
├── integrations/                     ├── integrations/
│   └── crewai.py      ────────────▶  │   ├── crewai.py      (interceptor tool)
│                                     │   ├── cursor.py      (NEW)
│                                     │   └── langchain.py   (NEW)
│                                     │
├── shared/            ────────────▶  ├── shared/            (UNCHANGED)
│                                     │
├── ui/                               ├── ui/
│   └── app.py         ────────────▶  │   └── app.py         (approval dashboard)
│                                     │
│                                     ├── diff/              (NEW)
│                                     │   ├── generator.py   (diff output)
│                                     │   └── formatters.py  (display formats)
│                                     │
└── main.py            ────────────▶  └── main.py
```

---

## File-by-File Mapping

### Keep Unchanged (Copy directly)
| File | Reason |
|------|--------|
| `shared/db.py` | Database infrastructure same |
| `shared/redis.py` | Caching/rate limiting same |
| `shared/security.py` | Auth unchanged |
| `shared/middleware.py` | Rate limiting unchanged |
| `shared/logging.py` | Logging unchanged |
| `agents/*` | Agent registration unchanged |
| `events/store.py` | Event sourcing unchanged |
| `events/bus.py` | Event bus unchanged |
| `events/models.py` | DB model unchanged |
| `config.py` | Config pattern same |

### Modify (Adapt for new purpose)
| Current File | New File | Changes |
|--------------|----------|---------|
| `a2a/router.py` | `intercept/router.py` | Endpoints for submitting proposed actions |
| `a2a/models.py` | `intercept/models.py` | Action schema instead of A2A task schema |
| `a2a/task_store.py` | `intercept/action_store.py` | Store pending actions awaiting approval |
| `simulations/router.py` | `preview/router.py` | Preview endpoints instead of simulation |
| `simulations/service.py` | `preview/service.py` | Impact analysis instead of simulation |
| `simulations/sandbox.py` | `preview/sandbox.py` | Dry-run execution (largely same) |
| `simulations/models.py` | `preview/models.py` | Preview/diff schemas |
| `events/types.py` | `events/types.py` | Add ActionProposed, ActionApproved, ActionRejected, ActionExecuted |
| `integrations/crewai.py` | `integrations/crewai.py` | Change from simulation tool to interceptor |
| `ui/app.py` | `ui/app.py` | Change from simulation dashboard to approval dashboard |

### Remove
| File | Reason |
|------|--------|
| `governance/__init__.py` | Not needed for pivot |

### Add New
| New File | Purpose |
|----------|---------|
| `intercept/__init__.py` | Action interception module |
| `intercept/protocol.py` | Defines interception protocol |
| `preview/__init__.py` | Impact preview module |
| `preview/analyzers/` | Different analyzers (file, db, api) |
| `diff/__init__.py` | Diff generation module |
| `diff/generator.py` | Creates readable diffs |
| `diff/formatters.py` | Terminal, HTML, JSON output |
| `integrations/cursor.py` | Cursor extension hooks |
| `integrations/langchain.py` | LangChain/LangGraph integration |

---

## Event Type Changes

### Current Events (v0.1)
```python
AgentRegistered
AgentVerified
SimulationCreated
SimulationStarted
SimulationCompleted
SimulationFailed
```

### Pivoted Events (v0.2)
```python
# Keep
AgentRegistered
AgentVerified

# Rename/Repurpose
SimulationCreated    → ActionProposed
SimulationStarted    → PreviewStarted
SimulationCompleted  → PreviewCompleted

# Add New
ActionApproved       # Human approved the action
ActionRejected       # Human rejected the action
ActionModified       # Human modified before approving
ActionExecuted       # Action was executed after approval
ActionTimedOut       # No response within timeout
```

---

## Database Schema Changes

### Keep
- `events` table (unchanged)
- `agents` table (unchanged)

### Modify
```sql
-- Rename: simulations → actions
ALTER TABLE simulations RENAME TO actions;

-- Modify columns
ALTER TABLE actions RENAME COLUMN scenario_definition TO action_definition;
ALTER TABLE actions RENAME COLUMN e2b_sandbox_id TO preview_sandbox_id;
ALTER TABLE actions ADD COLUMN action_type VARCHAR(50); -- file, db, api
ALTER TABLE actions ADD COLUMN approval_status VARCHAR(20); -- pending, approved, rejected, timeout
ALTER TABLE actions ADD COLUMN approved_by UUID REFERENCES agents(id);
ALTER TABLE actions ADD COLUMN approved_at TIMESTAMPTZ;
ALTER TABLE actions ADD COLUMN executed_at TIMESTAMPTZ;
ALTER TABLE actions ADD COLUMN diff_preview JSONB;
```

### Migration Strategy
1. Create new migration for v0.2.0
2. Rename table and columns
3. Add new columns with defaults
4. Keep old data for audit purposes

---

## API Endpoint Changes

### Current (v0.1)
```
POST /api/v1/simulations           # Create simulation
POST /api/v1/simulations/{id}/run  # Run simulation
GET  /api/v1/simulations/{id}      # Get simulation
```

### Pivoted (v0.2)
```
POST /api/v1/actions               # Submit proposed action
GET  /api/v1/actions/{id}/preview  # Get impact preview
POST /api/v1/actions/{id}/approve  # Approve action
POST /api/v1/actions/{id}/reject   # Reject action
POST /api/v1/actions/{id}/execute  # Execute approved action
GET  /api/v1/actions/{id}/diff     # Get diff preview
GET  /api/v1/actions/pending       # List pending approvals
```

---

## SDK Changes

### Current CrewAI Integration
```python
# Submit code to simulation sandbox
result = polis_tool._run(
    name="test",
    code="result = 2 + 2",
    inputs={},
)
```

### Pivoted Integration
```python
# Intercept action and get approval
from leviathan import ActionInterceptor

interceptor = ActionInterceptor(api_key="...")

# Before any dangerous operation
@interceptor.require_approval(action_type="file_write")
def write_file(path, content):
    # This won't execute until approved
    with open(path, 'w') as f:
        f.write(content)
```

---

## Testing Changes

### Keep
- `test_health.py` - Health checks same
- `test_agents.py` - Agent registration same
- `test_events.py` - Event sourcing same

### Modify
- `test_simulations.py` → `test_preview.py`
- `test_a2a.py` → `test_intercept.py`

### Add
- `test_diff.py` - Diff generation tests
- `test_approval.py` - Approval workflow tests
- `test_analyzers.py` - Impact analyzer tests
