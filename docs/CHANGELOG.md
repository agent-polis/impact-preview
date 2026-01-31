# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - Pivot to Impact Preview

### Planning
- Pivoting from "agent governance" to "impact preview for AI agents"
- See `docs/PIVOT.md` for full pivot plan

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
| 0.2.0 | TBD | Pivot to Impact Preview (Leviathan) |
