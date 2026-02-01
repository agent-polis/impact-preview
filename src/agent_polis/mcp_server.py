"""
Agent Polis MCP Server - Impact Preview for AI Agents

This MCP server exposes Agent Polis tools to Claude Desktop, Cursor, and other
MCP-compatible clients. It provides "terraform plan" style impact previews
before AI agents execute dangerous operations.

Usage:
    # With uvicorn (recommended for production)
    uvicorn agent_polis.mcp_server:mcp.app --host 0.0.0.0 --port 8000
    
    # Or run directly
    python -m agent_polis.mcp_server
    
    # Then in Claude Desktop config (~/.config/claude/claude_desktop_config.json):
    {
        "mcpServers": {
            "impact-preview": {
                "url": "http://localhost:8000/mcp"
            }
        }
    }
"""

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from agent_polis.actions.analyzer import ImpactAnalyzer
from agent_polis.actions.diff import format_diff_plain, format_diff_terminal
from agent_polis.actions.models import ActionRequest, ActionType, RiskLevel

# Create MCP server
mcp = FastMCP(
    "Agent Polis",
    instructions="Impact preview for AI agents - see exactly what will change before any action executes. Use preview tools BEFORE making file changes, running shell commands, or executing database queries.",
)

# Initialize analyzer with current working directory
_analyzer = ImpactAnalyzer(working_directory=os.getcwd())


def _risk_emoji(risk: RiskLevel) -> str:
    """Get emoji for risk level."""
    return {
        RiskLevel.LOW: "🟢",
        RiskLevel.MEDIUM: "🟡", 
        RiskLevel.HIGH: "🟠",
        RiskLevel.CRITICAL: "🔴",
    }.get(risk, "⚪")


@mcp.tool()
async def preview_file_write(
    path: str,
    content: str,
    description: str = "Write to file",
) -> str:
    """
    Preview what a file write operation will change BEFORE executing it.
    
    Shows a diff of current vs proposed content, risk assessment, and warnings.
    Use this before writing to any file to see exactly what will change.
    
    Args:
        path: Path to the file to write
        content: The content to write
        description: Description of what this change does
        
    Returns:
        Impact preview showing diff, risk level, and any warnings
    """
    request = ActionRequest(
        action_type=ActionType.FILE_WRITE,
        target=path,
        description=description,
        payload={"content": content},
    )
    
    preview = await _analyzer.analyze(request)
    
    # Format output
    output_lines = [
        f"## Impact Preview: {description}",
        f"**Target:** `{path}`",
        f"**Risk:** {_risk_emoji(preview.risk_level)} {preview.risk_level.value.upper()}",
        "",
    ]
    
    if preview.risk_factors:
        output_lines.append("**Risk Factors:**")
        for factor in preview.risk_factors:
            output_lines.append(f"  - {factor}")
        output_lines.append("")
    
    if preview.warnings:
        output_lines.append("**⚠️ Warnings:**")
        for warning in preview.warnings:
            output_lines.append(f"  - {warning}")
        output_lines.append("")
    
    output_lines.append(f"**Summary:** {preview.summary}")
    output_lines.append("")
    
    if preview.file_changes:
        output_lines.append("**Diff:**")
        output_lines.append("```diff")
        output_lines.append(format_diff_plain(preview.file_changes))
        output_lines.append("```")
    
    return "\n".join(output_lines)


@mcp.tool()
async def preview_file_create(
    path: str,
    content: str,
    description: str = "Create new file",
) -> str:
    """
    Preview creating a new file BEFORE executing it.
    
    Shows what will be created, risk assessment, and any warnings.
    
    Args:
        path: Path where the file will be created
        content: The content for the new file
        description: Description of what this file is for
        
    Returns:
        Impact preview showing what will be created and risk assessment
    """
    request = ActionRequest(
        action_type=ActionType.FILE_CREATE,
        target=path,
        description=description,
        payload={"content": content},
    )
    
    preview = await _analyzer.analyze(request)
    
    output_lines = [
        f"## Impact Preview: {description}",
        f"**Target:** `{path}` (NEW FILE)",
        f"**Risk:** {_risk_emoji(preview.risk_level)} {preview.risk_level.value.upper()}",
        f"**Size:** {len(content)} bytes, {content.count(chr(10)) + 1} lines",
        "",
    ]
    
    if preview.risk_factors:
        output_lines.append("**Risk Factors:**")
        for factor in preview.risk_factors:
            output_lines.append(f"  - {factor}")
        output_lines.append("")
    
    if preview.warnings:
        output_lines.append("**⚠️ Warnings:**")
        for warning in preview.warnings:
            output_lines.append(f"  - {warning}")
        output_lines.append("")
    
    output_lines.append(f"**Summary:** {preview.summary}")
    
    return "\n".join(output_lines)


@mcp.tool()
async def preview_file_delete(
    path: str,
    description: str = "Delete file",
) -> str:
    """
    Preview deleting a file BEFORE executing it.
    
    Shows what will be deleted, current contents, and risk assessment.
    This is a destructive operation - always preview first!
    
    Args:
        path: Path to the file to delete
        description: Reason for deletion
        
    Returns:
        Impact preview showing what will be lost and risk assessment
    """
    request = ActionRequest(
        action_type=ActionType.FILE_DELETE,
        target=path,
        description=description,
        payload={},
    )
    
    preview = await _analyzer.analyze(request)
    
    output_lines = [
        f"## ⚠️ DELETION Preview: {description}",
        f"**Target:** `{path}`",
        f"**Risk:** {_risk_emoji(preview.risk_level)} {preview.risk_level.value.upper()}",
        "",
    ]
    
    if preview.risk_factors:
        output_lines.append("**Risk Factors:**")
        for factor in preview.risk_factors:
            output_lines.append(f"  - {factor}")
        output_lines.append("")
    
    output_lines.append("**⚠️ This action is IRREVERSIBLE without backup!**")
    output_lines.append("")
    output_lines.append(f"**Summary:** {preview.summary}")
    
    if preview.file_changes:
        output_lines.append("")
        output_lines.append("**Content that will be DELETED:**")
        output_lines.append("```diff")
        output_lines.append(format_diff_plain(preview.file_changes))
        output_lines.append("```")
    
    return "\n".join(output_lines)


@mcp.tool()
async def preview_shell_command(
    command: str,
    description: str = "Execute shell command",
) -> str:
    """
    Preview a shell command BEFORE executing it.
    
    Analyzes the command for dangerous patterns and shows risk assessment.
    Shell commands can have system-wide effects - always preview first!
    
    Args:
        command: The shell command to analyze
        description: What this command is supposed to do
        
    Returns:
        Risk assessment and warnings for the command
    """
    request = ActionRequest(
        action_type=ActionType.SHELL_COMMAND,
        target=command,
        description=description,
        payload={"command": command},
    )
    
    preview = await _analyzer.analyze(request)
    
    output_lines = [
        f"## Shell Command Preview: {description}",
        f"**Command:** `{command}`",
        f"**Risk:** {_risk_emoji(preview.risk_level)} {preview.risk_level.value.upper()}",
        "",
    ]
    
    if preview.risk_factors:
        output_lines.append("**Risk Factors:**")
        for factor in preview.risk_factors:
            output_lines.append(f"  - {factor}")
        output_lines.append("")
    
    if preview.warnings:
        output_lines.append("**⚠️ Warnings:**")
        for warning in preview.warnings:
            output_lines.append(f"  - {warning}")
        output_lines.append("")
    
    if not preview.is_reversible:
        output_lines.append("**⚠️ This command may have IRREVERSIBLE effects!**")
        output_lines.append("")
    
    output_lines.append(f"**Reversible:** {'Yes' if preview.is_reversible else 'NO'}")
    
    return "\n".join(output_lines)


@mcp.tool()
async def preview_database_query(
    query: str,
    description: str = "Execute database query",
) -> str:
    """
    Preview a database query BEFORE executing it.
    
    Analyzes the query for dangerous operations (DELETE, DROP, TRUNCATE).
    Database operations can cause data loss - always preview first!
    
    Args:
        query: The SQL query to analyze
        description: What this query is supposed to do
        
    Returns:
        Risk assessment and classification of the query
    """
    # Determine if it's a read or write query
    query_upper = query.strip().upper()
    if query_upper.startswith("SELECT"):
        action_type = ActionType.DB_QUERY
    else:
        action_type = ActionType.DB_EXECUTE
    
    request = ActionRequest(
        action_type=action_type,
        target=query,
        description=description,
        payload={"query": query},
    )
    
    preview = await _analyzer.analyze(request)
    
    output_lines = [
        f"## Database Query Preview: {description}",
        f"**Query:**",
        "```sql",
        query,
        "```",
        f"**Risk:** {_risk_emoji(preview.risk_level)} {preview.risk_level.value.upper()}",
        "",
    ]
    
    if preview.risk_factors:
        output_lines.append("**Risk Factors:**")
        for factor in preview.risk_factors:
            output_lines.append(f"  - {factor}")
        output_lines.append("")
    
    if preview.warnings:
        output_lines.append("**⚠️ Warnings:**")
        for warning in preview.warnings:
            output_lines.append(f"  - {warning}")
        output_lines.append("")
    
    output_lines.append(f"**Reversible:** {'Yes' if preview.is_reversible else 'NO - Potential data loss!'}")
    
    return "\n".join(output_lines)


@mcp.tool()
def check_path_risk(path: str) -> str:
    """
    Quick check if a file path is sensitive/risky.
    
    Checks for patterns like .env, credentials, production configs, etc.
    Use this for a fast risk assessment before any file operation.
    
    Args:
        path: The file path to check
        
    Returns:
        Risk assessment for the path
    """
    path_lower = path.lower()
    
    risks = []
    
    # Check high-risk patterns
    high_risk_patterns = [
        (".env", "Environment file - may contain secrets"),
        (".git/", "Git directory - may corrupt repository"),
        ("credentials", "Credentials file"),
        ("secrets", "Secrets file"),
        ("password", "Password file"),
        (".pem", "Certificate/key file"),
        (".ssh/", "SSH directory"),
        ("id_rsa", "SSH private key"),
        ("/etc/", "System configuration"),
        ("/var/", "System variable data"),
        ("/usr/", "System programs"),
    ]
    
    for pattern, desc in high_risk_patterns:
        if pattern in path_lower:
            risks.append(f"🔴 HIGH: {desc} ({pattern})")
    
    # Check critical patterns
    critical_patterns = [
        ("production", "Production environment"),
        ("prod.", "Production config"),
        (".prod", "Production file"),
        ("database", "Database-related"),
        ("api_key", "API key"),
        ("secret_key", "Secret key"),
    ]
    
    for pattern, desc in critical_patterns:
        if pattern in path_lower:
            risks.append(f"🔴 CRITICAL: {desc} ({pattern})")
    
    if not risks:
        return f"✅ `{path}` - No obvious risk patterns detected"
    
    output = [f"⚠️ Risk assessment for `{path}`:", ""]
    output.extend(risks)
    return "\n".join(output)


@mcp.resource("config://working-directory")
def get_working_directory() -> str:
    """Get the current working directory used for file operations."""
    return os.getcwd()


@mcp.resource("config://risk-patterns")
def get_risk_patterns() -> str:
    """Get the list of patterns that trigger risk warnings."""
    return """
High Risk Patterns:
- .env - Environment files with secrets
- .git/ - Git repository internals
- credentials, secrets, password - Credential files
- .pem, id_rsa, .ssh/ - Keys and certificates
- /etc/, /var/, /usr/ - System directories

Critical Patterns:
- production, prod., .prod - Production configs
- database - Database configs
- api_key, secret_key - API credentials
"""


# Prompt for safe file operations
@mcp.prompt()
def safe_file_edit_workflow(file_path: str, change_description: str) -> str:
    """
    A workflow prompt for safely editing files with impact preview.
    
    This prompt guides the AI through a safe edit process:
    1. Preview the change
    2. Review the diff
    3. Only proceed if approved
    """
    return f"""You are about to edit a file. Follow this safety workflow:

1. First, use `preview_file_write` to see exactly what will change:
   - Path: {file_path}
   - Description: {change_description}

2. Review the diff output carefully:
   - Check the risk level
   - Review any warnings
   - Verify the changes match your intent

3. Only proceed with the actual edit if:
   - Risk is LOW or MEDIUM
   - No unexpected changes in the diff
   - The user explicitly approves

4. If risk is HIGH or CRITICAL:
   - Show the preview to the user
   - Explain the risks
   - Ask for explicit confirmation

Remember: ALWAYS preview before writing!
"""


def main():
    """CLI entry point for the MCP server."""
    print("🛡️  Agent Polis MCP Server - Impact Preview for AI Agents")
    print("=" * 60)
    print("\n📡 Starting server at: http://localhost:8000/mcp")
    print("\n📋 Add to Claude Desktop config (~/.config/claude/claude_desktop_config.json):")
    print("""
{
    "mcpServers": {
        "impact-preview": {
            "url": "http://localhost:8000/mcp"
        }
    }
}
""")
    print("🔧 Available tools:")
    print("   • preview_file_write  - Preview file edits before writing")
    print("   • preview_file_create - Preview new file creation")
    print("   • preview_file_delete - Preview file deletion (dangerous!)")
    print("   • preview_shell_command - Analyze shell commands for risk")
    print("   • preview_database_query - Analyze SQL queries")
    print("   • check_path_risk - Quick risk check for any path")
    print("\n" + "=" * 60)
    
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
