"""
Tests for the actions module - the core of impact preview.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from agent_polis.actions.models import (
    ActionType,
    ApprovalStatus,
    ActionRequest,
    ActionPreview,
    ActionResponse,
    FileChange,
    RiskLevel,
)
from agent_polis.actions.diff import (
    generate_unified_diff,
    generate_file_change,
    format_diff_terminal,
    format_diff_plain,
    format_diff_summary,
)


class TestActionModels:
    """Tests for action Pydantic models."""
    
    def test_action_request_creation(self):
        """Test creating an action request."""
        request = ActionRequest(
            action_type=ActionType.FILE_WRITE,
            target="/app/config.yaml",
            description="Update config",
            payload={"content": "key: value"},
        )
        
        assert request.action_type == ActionType.FILE_WRITE
        assert request.target == "/app/config.yaml"
        assert request.timeout_seconds == 300  # default
        assert not request.auto_approve_if_low_risk
    
    def test_action_request_with_options(self):
        """Test action request with all options."""
        request = ActionRequest(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/old-file.txt",
            description="Clean up temp file",
            payload={},
            context="Part of cleanup task",
            timeout_seconds=60,
            auto_approve_if_low_risk=True,
            callback_url="https://webhook.example.com/notify",
        )
        
        assert request.timeout_seconds == 60
        assert request.auto_approve_if_low_risk
        assert request.callback_url == "https://webhook.example.com/notify"
    
    def test_action_preview(self):
        """Test action preview model."""
        preview = ActionPreview(
            file_changes=[
                FileChange(
                    path="/app/config.yaml",
                    operation="modify",
                    lines_added=5,
                    lines_removed=3,
                ),
            ],
            risk_level=RiskLevel.MEDIUM,
            risk_factors=["Contains credentials pattern"],
            summary="1 file modified (+5 -3)",
            affected_count=1,
            warnings=["Production config detected"],
            is_reversible=True,
        )
        
        assert preview.risk_level == RiskLevel.MEDIUM
        assert len(preview.file_changes) == 1
        assert len(preview.warnings) == 1
    
    def test_action_response(self):
        """Test action response model."""
        response = ActionResponse(
            id=uuid4(),
            action_type=ActionType.FILE_WRITE,
            description="Test action",
            target="/test/file.txt",
            status=ApprovalStatus.PENDING,
        )
        
        assert response.status == ApprovalStatus.PENDING
        assert response.approved_by is None
        assert response.executed_at is None


class TestDiffGeneration:
    """Tests for diff generation utilities."""
    
    def test_generate_unified_diff_modify(self):
        """Test generating unified diff for modifications."""
        original = "line1\nline2\nline3\n"
        modified = "line1\nmodified line\nline3\n"
        
        diff = generate_unified_diff(original, modified, "test.txt")
        
        assert "--- a/test.txt" in diff
        assert "+++ b/test.txt" in diff
        assert "-line2" in diff
        assert "+modified line" in diff
    
    def test_generate_unified_diff_new_file(self):
        """Test generating diff for new file."""
        diff = generate_unified_diff("", "new content\n", "new.txt")
        
        assert "+new content" in diff
    
    def test_generate_unified_diff_delete(self):
        """Test generating diff for deleted content."""
        diff = generate_unified_diff("old content\n", "", "deleted.txt")
        
        assert "-old content" in diff
    
    def test_generate_file_change_create(self):
        """Test generating FileChange for file creation."""
        change = generate_file_change(
            path="/new/file.txt",
            operation="create",
            new_content="hello world\nline 2\n",
        )
        
        assert change.operation == "create"
        assert change.lines_added == 2
        assert change.lines_removed == 0
        assert change.file_size_after == len("hello world\nline 2\n")
    
    def test_generate_file_change_modify(self):
        """Test generating FileChange for modification."""
        change = generate_file_change(
            path="/existing/file.txt",
            operation="modify",
            original_content="old line\n",
            new_content="new line\nextra line\n",
        )
        
        assert change.operation == "modify"
        assert change.lines_added == 2
        assert change.lines_removed == 1
        assert change.diff is not None
    
    def test_generate_file_change_delete(self):
        """Test generating FileChange for deletion."""
        change = generate_file_change(
            path="/delete/me.txt",
            operation="delete",
            original_content="line1\nline2\nline3\n",
        )
        
        assert change.operation == "delete"
        assert change.lines_added == 0
        assert change.lines_removed == 3
    
    def test_generate_file_change_move(self):
        """Test generating FileChange for move."""
        change = generate_file_change(
            path="/old/location.txt",
            operation="move",
            destination_path="/new/location.txt",
        )
        
        assert change.operation == "move"
        assert change.destination_path == "/new/location.txt"
        assert "rename from" in change.diff
        assert "rename to" in change.diff
    
    def test_format_diff_summary(self):
        """Test diff summary formatting."""
        changes = [
            FileChange(path="/a.txt", operation="create", lines_added=10, lines_removed=0),
            FileChange(path="/b.txt", operation="modify", lines_added=5, lines_removed=3),
            FileChange(path="/c.txt", operation="delete", lines_added=0, lines_removed=20),
        ]
        
        summary = format_diff_summary(changes)
        
        assert "1 file(s) created" in summary
        assert "1 file(s) modified" in summary
        assert "1 file(s) deleted" in summary
        assert "+15" in summary
        assert "-23" in summary
    
    def test_format_diff_summary_empty(self):
        """Test diff summary for no changes."""
        summary = format_diff_summary([])
        assert summary == "No changes"
    
    def test_format_diff_plain(self):
        """Test plain text diff formatting."""
        changes = [
            FileChange(
                path="/test.txt",
                operation="modify",
                lines_added=2,
                lines_removed=1,
                diff="--- a/test.txt\n+++ b/test.txt\n-old\n+new",
            ),
        ]
        
        output = format_diff_plain(changes)
        
        assert "/test.txt" in output
        assert "modify" in output
        assert "+2 -1" in output
    
    def test_format_diff_terminal(self):
        """Test terminal-colored diff formatting."""
        changes = [
            FileChange(
                path="/test.txt",
                operation="create",
                lines_added=1,
                lines_removed=0,
            ),
        ]
        
        output = format_diff_terminal(changes)
        
        # Should contain ANSI codes
        assert "\033[32m" in output  # green


class TestActionTypes:
    """Tests for action type handling."""
    
    def test_all_action_types_valid(self):
        """Ensure all action types can be created."""
        for action_type in ActionType:
            request = ActionRequest(
                action_type=action_type,
                target="/test",
                description=f"Test {action_type.value}",
            )
            assert request.action_type == action_type
    
    def test_approval_status_transitions(self):
        """Test valid status values."""
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
        assert ApprovalStatus.EXECUTED.value == "executed"
        assert ApprovalStatus.FAILED.value == "failed"
        assert ApprovalStatus.TIMED_OUT.value == "timed_out"


class TestRiskLevels:
    """Tests for risk level handling."""
    
    def test_risk_level_ordering(self):
        """Test that risk levels have expected values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


@pytest.mark.asyncio
class TestActionAnalyzer:
    """Tests for impact analyzer."""
    
    async def test_analyzer_file_write(self, tmp_path):
        """Test analyzing file write operation."""
        from agent_polis.actions.analyzer import ImpactAnalyzer
        
        # Create a temp file
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content\n")
        
        analyzer = ImpactAnalyzer(working_directory=str(tmp_path))
        
        request = ActionRequest(
            action_type=ActionType.FILE_WRITE,
            target=str(test_file),
            description="Update test file",
            payload={"content": "new content\n"},
        )
        
        preview = await analyzer.analyze(request)
        
        assert preview.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
        assert len(preview.file_changes) == 1
        assert preview.file_changes[0].operation == "modify"
    
    async def test_analyzer_file_create(self, tmp_path):
        """Test analyzing file creation."""
        from agent_polis.actions.analyzer import ImpactAnalyzer
        
        analyzer = ImpactAnalyzer(working_directory=str(tmp_path))
        
        request = ActionRequest(
            action_type=ActionType.FILE_CREATE,
            target="new_file.txt",
            description="Create new file",
            payload={"content": "hello world\n"},
        )
        
        preview = await analyzer.analyze(request)
        
        assert preview.risk_level == RiskLevel.LOW
        assert len(preview.file_changes) == 1
        assert preview.file_changes[0].operation == "create"
    
    async def test_analyzer_detects_high_risk_path(self, tmp_path):
        """Test that analyzer detects high-risk paths."""
        from agent_polis.actions.analyzer import ImpactAnalyzer
        
        analyzer = ImpactAnalyzer(working_directory=str(tmp_path))
        
        request = ActionRequest(
            action_type=ActionType.FILE_WRITE,
            target=".env",
            description="Update environment",
            payload={"content": "SECRET_KEY=abc123"},
        )
        
        preview = await analyzer.analyze(request)
        
        assert preview.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert any(".env" in factor for factor in preview.risk_factors)
    
    async def test_analyzer_shell_command_high_risk(self, tmp_path):
        """Test that shell commands are high risk."""
        from agent_polis.actions.analyzer import ImpactAnalyzer
        
        analyzer = ImpactAnalyzer(working_directory=str(tmp_path))
        
        request = ActionRequest(
            action_type=ActionType.SHELL_COMMAND,
            target="rm -rf /",
            description="Cleanup",
            payload={"command": "rm -rf /"},
        )
        
        preview = await analyzer.analyze(request)
        
        assert preview.risk_level == RiskLevel.CRITICAL
        assert not preview.is_reversible
    
    async def test_analyzer_production_pattern_detection(self, tmp_path):
        """Test detection of production patterns."""
        from agent_polis.actions.analyzer import ImpactAnalyzer
        
        analyzer = ImpactAnalyzer(working_directory=str(tmp_path))
        
        request = ActionRequest(
            action_type=ActionType.FILE_WRITE,
            target="config.production.yaml",
            description="Update production config",
            payload={"content": "db_url: production_server"},
        )
        
        preview = await analyzer.analyze(request)
        
        assert preview.risk_level == RiskLevel.CRITICAL
        assert any("production" in factor.lower() for factor in preview.risk_factors)
