"""
Actions module - the core of impact preview.

This module handles:
- Receiving proposed actions from AI agents
- Generating impact previews (what will change)
- Managing the approval workflow
- Executing approved actions
"""

from agent_polis.actions.analyzer import ImpactAnalyzer, get_analyzer
from agent_polis.actions.diff import (
    format_diff_plain,
    format_diff_summary,
    format_diff_terminal,
    generate_file_change,
    generate_unified_diff,
)
from agent_polis.actions.models import (
    ActionPreview,
    ActionRequest,
    ActionResponse,
    ActionType,
    ApprovalStatus,
    FileChange,
    RiskLevel,
)
from agent_polis.actions.router import router
from agent_polis.actions.service import ActionService

__all__ = [
    # Models
    "ActionType",
    "ApprovalStatus",
    "ActionRequest",
    "ActionPreview",
    "FileChange",
    "ActionResponse",
    "RiskLevel",
    # Service
    "ActionService",
    # Analyzer
    "ImpactAnalyzer",
    "get_analyzer",
    # Diff
    "generate_unified_diff",
    "generate_file_change",
    "format_diff_terminal",
    "format_diff_plain",
    "format_diff_summary",
    # Router
    "router",
]
