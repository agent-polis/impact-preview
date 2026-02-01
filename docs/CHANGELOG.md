# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-01-30 - Impact Preview Pivot

### Changed - Strategic Pivot
This release pivots the project from "agent governance" to "impact preview for AI agents."
The new focus solves a more immediate market pain: developers want AI agents but don't trust them.

### Added
- **Actions Module**: Core system for submitting, analyzing, and approving agent actions
  - `ActionRequest`, `ActionPreview`, `ActionResponse` models
  - `ActionType` enum (file_write, file_delete, db_query, shell_command, etc.)
  - `ApprovalStatus` workflow states (pending, approved, rejected, executed)
  - `RiskLevel` assessment (low, medium, high, critical)
- **Impact Analyzer**: Generates previews of what actions will change
  - File operation analysis with diff generation
  - Risk pattern detection (production, credentials, system files)
  - Shell command risk assessment
  - Database query classification (coming v0.3)
- **Diff Generator**: Human-readable diffs for file changes
  - Unified diff format
  - Terminal-colored output
  - Plain text format
  - Summary statistics
- **Actions API**: RESTful endpoints for the approval workflow
  - `POST /api/v1/actions` - Submit action
  - `GET /api/v1/actions/pending` - List pending
  - `GET /api/v1/actions/{id}/preview` - Get impact preview
  - `GET /api/v1/actions/{id}/diff` - Get diff output
  - `POST /api/v1/actions/{id}/approve` - Approve
  - `POST /api/v1/actions/{id}/reject` - Reject
  - `POST /api/v1/actions/{id}/execute` - Execute
- **Python SDK**: Easy integration for agent developers
  - `AgentPolisClient` class
  - `@require_approval` decorator
  - `wait_for_approval()` method
  - Error classes: `ActionRejectedError`, `ActionTimedOutError`
- **New Event Types**: For action audit trail
  - `ActionProposed`, `ActionPreviewGenerated`
  - `ActionApproved`, `ActionRejected`, `ActionModified`
  - `ActionExecuted`, `ActionFailed`, `ActionTimedOut`
- **Updated Streamlit UI**: Approval dashboard
  - Pending approvals view
  - Action details with diff display
  - Approve/reject controls
  - Risk level indicators
- **Database Migration**: `actions` table for v0.2

### Changed
- Rebranded from "governance layer" to "impact preview"
- Updated README with new positioning
- Version bumped to 0.2.0
- Agent card updated with new capabilities

### Kept (from v0.1)
- Event sourcing infrastructure (perfect for audit trails)
- Agent registration and authentication
- Rate limiting middleware
- PostgreSQL + Redis stack
- FastAPI async architecture
- Docker/CI/CD infrastructure

### Deprecated
- Legacy A2A/simulations routes (still available but marked as legacy)

---

## [0.1.0] - 2026-01-30

### Added
- Initial MVP release as "Agent Polis"
- A2A protocol server with agent discovery
- Agent registration with API key authentication
- Simulation execution via E2B sandbox
- Event-sourced audit trail with hash chaining
- Rate limiting middleware with Redis
- Metering for usage tracking
- Streamlit demo UI
- CrewAI integration SDK
- PostgreSQL schema with Alembic migrations
- Docker and docker-compose configurations
- GitHub Actions CI/CD
- Deployment configs for Railway and Render

### Architecture
- FastAPI async backend
- Event sourcing for immutable audit trail
- Modular structure: agents, simulations, events, a2a

### Documentation
- README with quickstart guide
- API reference
- Example scripts (quickstart.py, crewai_example.py)

---

## Version History

| Version | Date | Focus |
|---------|------|-------|
| 0.1.0 | 2026-01-30 | Initial MVP (Agent Polis - Governance) |
| 0.2.0 | 2026-01-30 | Pivot to Impact Preview (File Operations) |
| 0.3.0 | TBD | Database operation preview |
| 0.4.0 | TBD | API call preview |
| 0.5.0 | TBD | IDE integrations (Cursor, VS Code) |
| 1.0.0 | TBD | Production ready |
