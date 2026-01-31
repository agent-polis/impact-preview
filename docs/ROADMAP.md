# Roadmap

## Current Focus: Pivot to Impact Preview

We're pivoting from "agent governance" to "impact preview for AI agents" based on market research showing strong demand for this capability following high-profile incidents (Replit database deletion, Cursor YOLO mode failures).

---

## Phase 1: Core Impact Preview (v0.2.0)

**Goal**: Minimal viable impact preview for file operations

### Must Have
- [ ] Action interception protocol (how agents send proposed actions)
- [ ] File operation detection (read, write, delete, move)
- [ ] Diff preview generation (show what will change)
- [ ] Simple approval flow (approve/reject via API)
- [ ] Audit log of all previews and decisions

### Should Have  
- [ ] CLI tool for local development workflow
- [ ] Basic Streamlit dashboard for reviewing pending actions
- [ ] Timeout handling (auto-reject if no response)

### Nice to Have
- [ ] Slack/Discord notification for pending approvals
- [ ] Bulk approve/reject for batch operations

---

## Phase 2: Database Operations (v0.3.0)

**Goal**: Preview impact of database changes

### Must Have
- [ ] SQL query parsing and classification (SELECT/INSERT/UPDATE/DELETE)
- [ ] Transaction dry-run (execute in transaction, show results, rollback)
- [ ] Row count impact ("will affect 1,247 rows")
- [ ] Sample data preview (show 5 example rows that will change)

### Should Have
- [ ] Schema change preview (ALTER, DROP, CREATE)
- [ ] Foreign key cascade warnings
- [ ] Index impact analysis

---

## Phase 3: External API Calls (v0.4.0)

**Goal**: Preview and control external API interactions

### Must Have
- [ ] HTTP request interception
- [ ] Request/response logging
- [ ] Side-effect classification (GET = safe, POST/PUT/DELETE = dangerous)
- [ ] Cost estimation for paid APIs (OpenAI, etc.)

### Should Have
- [ ] Mock response capability (test without hitting real API)
- [ ] Rate limit tracking across agents
- [ ] Webhook payload preview

---

## Phase 4: IDE Integration (v0.5.0)

**Goal**: Native integration with popular AI coding tools

### Cursor Integration
- [ ] Extension that intercepts agent mode actions
- [ ] In-editor diff preview
- [ ] One-click approve/reject

### VS Code / Claude Code
- [ ] Similar extension pattern
- [ ] Works with Claude Code's permission model

### CrewAI / LangGraph
- [ ] Native tool wrapper
- [ ] Callback integration
- [ ] Async approval support

---

## Phase 5: Production Ready (v1.0.0)

**Goal**: Enterprise-ready with all safety features

### Security
- [ ] SOC 2 compliance preparation
- [ ] Encryption at rest and in transit
- [ ] Audit log export (compliance)

### Scale
- [ ] Multi-tenant support
- [ ] Team/organization management
- [ ] Role-based access control

### Reliability
- [ ] 99.9% uptime SLA
- [ ] Disaster recovery
- [ ] Geographic redundancy

---

## Future Ideas (Backlog)

These may or may not be built depending on user feedback:

- **Undo/Rollback**: Not just preview, but automatic undo if things go wrong
- **Policy Engine**: Define rules like "never delete production tables"
- **Cost Tracking**: Track and limit AI API spend across all agents
- **Multi-Agent Coordination**: Original governance vision (if market matures)
- **Training Data**: Use preview/approval data to fine-tune safer agents

---

## How to Contribute

See issues labeled:
- `good first issue` - Great for new contributors
- `help wanted` - We need community input
- `milestone:v0.2.0` - Current sprint focus

---

## Feedback

We're pivoting based on real user needs. If you have feedback on this roadmap:
- Open an issue with the `feedback` label
- Join discussions in GitHub Discussions
- DM on Twitter/X (handle TBD)
