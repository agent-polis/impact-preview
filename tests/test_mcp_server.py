"""
Tests for the MCP server tools.

These test the impact preview tools directly without going through HTTP.
"""

import pytest

from agent_polis.mcp_server import (
    _risk_emoji,
    check_path_risk,
    preview_file_write,
    preview_file_delete,
    preview_shell_command,
    preview_database_query,
    preview_file_create,
)
from agent_polis.actions.models import RiskLevel


class TestRiskEmoji:
    """Test risk level emoji mapping."""
    
    def test_low_risk_emoji(self):
        assert _risk_emoji(RiskLevel.LOW) == "🟢"
    
    def test_medium_risk_emoji(self):
        assert _risk_emoji(RiskLevel.MEDIUM) == "🟡"
    
    def test_high_risk_emoji(self):
        assert _risk_emoji(RiskLevel.HIGH) == "🟠"
    
    def test_critical_risk_emoji(self):
        assert _risk_emoji(RiskLevel.CRITICAL) == "🔴"


class TestCheckPathRisk:
    """Test the quick path risk checker."""
    
    def test_safe_path(self):
        result = check_path_risk("/tmp/test.txt")
        assert "No obvious risk patterns detected" in result
    
    def test_env_file(self):
        result = check_path_risk(".env")
        assert "HIGH" in result
        assert "secrets" in result.lower() or "environment" in result.lower()
    
    def test_production_path(self):
        result = check_path_risk("/app/config.production.yaml")
        assert "CRITICAL" in result
        assert "production" in result.lower()
    
    def test_credentials_path(self):
        result = check_path_risk("credentials.json")
        assert "HIGH" in result
    
    def test_ssh_key(self):
        result = check_path_risk("/home/user/.ssh/id_rsa")
        assert "HIGH" in result


class TestPreviewFileWrite:
    """Test file write preview tool."""
    
    @pytest.mark.asyncio
    async def test_preview_simple_write(self, tmp_path):
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")
        
        result = await preview_file_write(
            path=str(test_file),
            content="new content",
            description="Update test file",
        )
        
        assert "Impact Preview" in result
        assert "Risk:" in result
        assert "LOW" in result or "MEDIUM" in result
        assert "Diff:" in result
    
    @pytest.mark.asyncio
    async def test_preview_new_file_write(self, tmp_path):
        new_file = tmp_path / "new_file.txt"
        
        result = await preview_file_write(
            path=str(new_file),
            content="brand new content",
            description="Create new file",
        )
        
        assert "Impact Preview" in result
        assert "Risk:" in result


class TestPreviewFileCreate:
    """Test file create preview tool."""
    
    @pytest.mark.asyncio
    async def test_preview_file_create(self, tmp_path):
        new_file = tmp_path / "new_file.py"
        
        result = await preview_file_create(
            path=str(new_file),
            content="print('hello')",
            description="Create Python script",
        )
        
        assert "Impact Preview" in result
        assert "NEW FILE" in result
        assert "bytes" in result


class TestPreviewFileDelete:
    """Test file delete preview tool."""
    
    @pytest.mark.asyncio
    async def test_preview_delete(self, tmp_path):
        # Create a file to delete
        test_file = tmp_path / "to_delete.txt"
        test_file.write_text("content to be deleted")
        
        result = await preview_file_delete(
            path=str(test_file),
            description="Remove test file",
        )
        
        assert "DELETION Preview" in result
        assert "IRREVERSIBLE" in result


class TestPreviewShellCommand:
    """Test shell command preview tool."""
    
    @pytest.mark.asyncio
    async def test_safe_command(self):
        result = await preview_shell_command(
            command="ls -la",
            description="List files",
        )
        
        assert "Shell Command Preview" in result
        assert "Risk:" in result
    
    @pytest.mark.asyncio
    async def test_dangerous_command(self):
        result = await preview_shell_command(
            command="rm -rf /",
            description="Delete everything",
        )
        
        assert "Shell Command Preview" in result
        assert "HIGH" in result or "CRITICAL" in result
        assert "Risk Factors:" in result


class TestPreviewDatabaseQuery:
    """Test database query preview tool."""
    
    @pytest.mark.asyncio
    async def test_select_query(self):
        result = await preview_database_query(
            query="SELECT * FROM users WHERE id = 1",
            description="Get user by ID",
        )
        
        assert "Database Query Preview" in result
        assert "Risk:" in result
    
    @pytest.mark.asyncio
    async def test_delete_query(self):
        result = await preview_database_query(
            query="DELETE FROM users WHERE active = false",
            description="Remove inactive users",
        )
        
        assert "Database Query Preview" in result
        # DELETE should be higher risk
        assert "Risk:" in result
    
    @pytest.mark.asyncio
    async def test_drop_table(self):
        result = await preview_database_query(
            query="DROP TABLE users",
            description="Remove users table",
        )
        
        assert "Database Query Preview" in result
        # DROP should be critical
        assert "CRITICAL" in result or "HIGH" in result
