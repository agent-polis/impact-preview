# Agent Polis Pivot: Impact Preview for AI Agents

**Date**: 2026-01-30
**Status**: v0.2.0 Implemented
**Codename**: Leviathan (working name for pivot)

---

## The Pivot

**From**: Governance and coordination layer for AI agents (voting, proposals, multi-agent democracy)

**To**: Impact preview layer for AI agents ("Terraform plan" for any AI action)

**Why**: The original vision is 3-5 years ahead of market. The new focus solves an ACTIVE pain point with documented incidents (Replit, Cursor YOLO mode) and real developer fear.

---

## Problem Statement

Developers want to use autonomous AI agents but don't trust them. Current solutions show what agents WANT to do, not what WILL happen.

**Key incidents driving this:**
- Replit agent deleted production database, then lied about it (July 2025)
- Cursor YOLO mode deleted entire system including itself (Jan 2025)
- Claude learned to bypass safety restrictions via shell scripts

**The gap**: No "terraform plan" equivalent for AI agent actions.

---

## New Value Proposition

> "See exactly what will change before any AI agent action executes."

- Intercept proposed actions from any AI agent
- Simulate/analyze impact on YOUR real environment  
- Show diff preview (files, DB, API calls affected)
- Human approves, modifies, or rejects
- Only then execute

---

## Target Users

1. **Primary**: Developers using Cursor/Claude Code who want agent mode but fear YOLO
2. **Secondary**: Teams running CrewAI/LangGraph in production
3. **Tertiary**: Enterprises deploying autonomous agents who need audit trails

---

## Reuse Plan

### Keep As-Is
- [x] Event sourcing infrastructure (perfect for audit trail)
- [x] Agent registration and authentication
- [x] Rate limiting and metering
- [x] Database schema (events table)
- [x] Docker/CI/CD infrastructure
- [x] FastAPI app structure

### Modify
- [x] Rename: Simulations → Actions (Impact Preview)
- [x] Repurpose: E2B sandbox → Available for future dry-run
- [x] Adapt: A2A endpoints → Action submission protocol
- [x] Redesign: Streamlit UI → Action approval dashboard

### Build New
- [x] Action SDK (Python package with @require_approval)
- [x] Diff Generator (readable output of proposed changes)
- [x] Impact Analyzer (file operations)
- [ ] Impact Analyzer (DB operations) - v0.3
- [ ] Impact Analyzer (API calls) - v0.4
- [ ] Cursor/Claude Code extension - v0.5

---

## Architecture Evolution

```
BEFORE (Agent Polis v0.1):
┌─────────┐     ┌─────────────┐     ┌──────────┐
│ Agents  │────▶│ Agent Polis │────▶│ Sandbox  │
└─────────┘     │ (Governance)│     │ (E2B)    │
                └─────────────┘     └──────────┘

AFTER (Leviathan v0.2):
┌─────────┐     ┌─────────────┐     ┌──────────────┐     ┌──────────┐
│ Agent   │────▶│ Interceptor │────▶│ Impact       │────▶│ Human    │
│ (Cursor,│     │ SDK         │     │ Analyzer     │     │ Approval │
│ CrewAI) │     └─────────────┘     └──────────────┘     └────┬─────┘
└─────────┘                                                    │
                                                               ▼
                         ┌──────────────────────────────────────┐
                         │ Execute (if approved) + Audit Log   │
                         └──────────────────────────────────────┘
```

---

## Version Strategy

| Version | Codename | Focus |
|---------|----------|-------|
| v0.1.x | Agent Polis | Original governance MVP (archive) |
| v0.2.0 | Leviathan | Impact preview core (file operations) |
| v0.3.0 | - | Database operation preview |
| v0.4.0 | - | API call preview |
| v0.5.0 | - | Cursor/Claude Code integration |
| v1.0.0 | - | Production-ready, multi-framework support |

---

## Milestones

### M1: Core Pivot (v0.2.0) ✅ COMPLETE
- [x] Rename/rebrand
- [x] Action submission protocol
- [x] File operation impact preview
- [x] Basic diff output
- [x] API approval workflow
- [x] Streamlit approval dashboard

### M2: Database Support (v0.3.0)
- [ ] SQL query interception
- [ ] Transaction dry-run preview
- [ ] Row-level impact display

### M3: External APIs (v0.4.0)  
- [ ] HTTP request interception
- [ ] Mock/simulate API responses
- [ ] Side-effect warnings

### M4: IDE Integration (v0.5.0)
- [ ] Cursor extension
- [ ] VS Code extension
- [ ] Claude Code hooks

---

## Naming Considerations

Current thinking on names:
- **Leviathan** - Working codename (control over the beast)
- **Guardrail** - Taken by GuardrailsAI
- **Terraform** - Obviously taken
- **Dryrun** - Simple, descriptive
- **Prevu** - Preview + view
- **Blastwall** - Blast radius protection
- **Checkpoint** - Like a security checkpoint

Need to check availability before committing.

---

## Open Questions

1. **SDK vs Proxy**: Should we be an SDK agents import, or a proxy they route through?
2. **Real-time vs Batch**: Support immediate approval flow only, or also batch review?
3. **Pricing**: Per-preview, per-execution, or subscription?
4. **Framework priority**: Cursor first, CrewAI first, or framework-agnostic first?

---

## Next Steps

1. Create `CHANGELOG.md` to track versions
2. Create GitHub issues for M1 tasks
3. Branch strategy: `main` stays v0.1.x, `pivot` branch for v0.2.0
4. Update README with new positioning (after M1 complete)
