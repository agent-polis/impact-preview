"""
Impact analyzer - generates previews of what actions will change.

For v0.2, this focuses on file operations. Future versions will add
database and API call analysis.
"""

import os
from pathlib import Path

import structlog

from agent_polis.actions.models import (
    ActionRequest,
    ActionType,
    ActionPreview,
    FileChange,
    RiskLevel,
)
from agent_polis.actions.diff import generate_file_change, format_diff_summary

logger = structlog.get_logger()


class ImpactAnalyzer:
    """
    Analyzes proposed actions and generates impact previews.
    
    The analyzer examines what an action will do WITHOUT executing it,
    then produces a preview showing exactly what will change.
    """
    
    # Patterns that indicate high risk
    HIGH_RISK_PATHS = [
        ".env",
        ".git/",
        "node_modules/",
        "__pycache__/",
        ".ssh/",
        "id_rsa",
        "credentials",
        "secrets",
        "password",
        ".pem",
        "/etc/",
        "/var/log/",
        "/var/www/",
        "/var/lib/",
        "/usr/",
    ]
    
    # Paths that are safe (temp directories, etc.)
    SAFE_PATH_PREFIXES = [
        "/tmp",
        "/var/tmp",
        "/private/var/folders/",  # macOS temp
        "/var/folders/",  # macOS temp (alternate)
    ]
    
    CRITICAL_PATTERNS = [
        "production",
        "prod.",
        ".prod",
        "database",
        "db_password",
        "api_key",
        "secret_key",
    ]
    
    def __init__(self, working_directory: str | None = None):
        """
        Initialize analyzer.
        
        Args:
            working_directory: Base directory for relative paths
        """
        self.working_dir = Path(working_directory) if working_directory else Path.cwd()
    
    async def analyze(self, request: ActionRequest) -> ActionPreview:
        """
        Generate impact preview for a proposed action.
        
        Args:
            request: The proposed action
            
        Returns:
            ActionPreview with changes, risks, and summary
        """
        logger.info(
            "Analyzing action",
            action_type=request.action_type,
            target=request.target,
        )
        
        if request.action_type in [
            ActionType.FILE_WRITE,
            ActionType.FILE_CREATE,
            ActionType.FILE_DELETE,
            ActionType.FILE_MOVE,
        ]:
            return await self._analyze_file_operation(request)
        
        elif request.action_type == ActionType.SHELL_COMMAND:
            return await self._analyze_shell_command(request)
        
        elif request.action_type in [ActionType.DB_QUERY, ActionType.DB_EXECUTE]:
            return await self._analyze_db_operation(request)
        
        elif request.action_type == ActionType.API_CALL:
            return await self._analyze_api_call(request)
        
        else:
            return await self._analyze_custom(request)
    
    async def _analyze_file_operation(self, request: ActionRequest) -> ActionPreview:
        """Analyze file operations (create, write, delete, move)."""
        changes: list[FileChange] = []
        warnings: list[str] = []
        risk_factors: list[str] = []
        
        target_path = Path(request.target)
        if not target_path.is_absolute():
            target_path = self.working_dir / target_path
        
        # Determine operation type
        if request.action_type == ActionType.FILE_CREATE:
            operation = "create"
            new_content = request.payload.get("content", "")
            
            if target_path.exists():
                warnings.append(f"File already exists: {request.target}")
                operation = "modify"
                original_content = target_path.read_text() if target_path.exists() else None
            else:
                original_content = None
            
            changes.append(generate_file_change(
                path=request.target,
                operation=operation,
                original_content=original_content,
                new_content=new_content,
            ))
            
        elif request.action_type == ActionType.FILE_WRITE:
            new_content = request.payload.get("content", "")
            
            if target_path.exists():
                original_content = target_path.read_text()
                operation = "modify"
            else:
                original_content = None
                operation = "create"
            
            changes.append(generate_file_change(
                path=request.target,
                operation=operation,
                original_content=original_content,
                new_content=new_content,
            ))
            
        elif request.action_type == ActionType.FILE_DELETE:
            if target_path.exists():
                original_content = target_path.read_text() if target_path.is_file() else None
                changes.append(generate_file_change(
                    path=request.target,
                    operation="delete",
                    original_content=original_content,
                ))
                risk_factors.append("Deleting file")
            else:
                warnings.append(f"File does not exist: {request.target}")
                
        elif request.action_type == ActionType.FILE_MOVE:
            destination = request.payload.get("destination", "")
            if target_path.exists():
                changes.append(generate_file_change(
                    path=request.target,
                    operation="move",
                    destination_path=destination,
                ))
            else:
                warnings.append(f"Source file does not exist: {request.target}")
        
        # Assess risks
        risk_level, additional_factors = self._assess_file_risks(
            request.target,
            request.action_type,
            request.payload.get("content", ""),
        )
        risk_factors.extend(additional_factors)
        
        # Check if reversible
        is_reversible = request.action_type != ActionType.FILE_DELETE
        reversal_instructions = None
        if not is_reversible:
            reversal_instructions = "Restore from backup or version control"
        
        return ActionPreview(
            file_changes=changes,
            risk_level=risk_level,
            risk_factors=risk_factors,
            summary=format_diff_summary(changes),
            affected_count=len(changes),
            warnings=warnings,
            is_reversible=is_reversible,
            reversal_instructions=reversal_instructions,
        )
    
    async def _analyze_shell_command(self, request: ActionRequest) -> ActionPreview:
        """Analyze shell commands (high risk by default)."""
        command = request.payload.get("command", request.target)
        
        risk_factors = ["Shell command execution"]
        risk_level = RiskLevel.HIGH
        warnings = []
        
        # Check for especially dangerous commands
        dangerous_commands = ["rm", "rmdir", "del", "format", "dd", "mkfs", ">", ">>"]
        for cmd in dangerous_commands:
            if cmd in command.lower():
                risk_level = RiskLevel.CRITICAL
                risk_factors.append(f"Contains dangerous command: {cmd}")
        
        # Check for sudo/admin
        if "sudo" in command.lower() or "admin" in command.lower():
            risk_level = RiskLevel.CRITICAL
            risk_factors.append("Elevated privileges requested")
        
        warnings.append("Shell commands cannot be previewed - only the command itself is shown")
        
        return ActionPreview(
            file_changes=[],
            risk_level=risk_level,
            risk_factors=risk_factors,
            summary=f"Execute: {command[:100]}{'...' if len(command) > 100 else ''}",
            affected_count=0,
            warnings=warnings,
            is_reversible=False,
            reversal_instructions="Depends on the command - may not be reversible",
        )
    
    async def _analyze_db_operation(self, request: ActionRequest) -> ActionPreview:
        """Analyze database operations (placeholder for v0.3)."""
        query = request.payload.get("query", request.target)
        
        # Basic classification
        query_upper = query.upper().strip()
        
        if query_upper.startswith("SELECT"):
            risk_level = RiskLevel.LOW
            risk_factors = ["Read-only query"]
        elif query_upper.startswith(("INSERT", "UPDATE")):
            risk_level = RiskLevel.MEDIUM
            risk_factors = ["Data modification"]
        elif query_upper.startswith(("DELETE", "DROP", "TRUNCATE", "ALTER")):
            risk_level = RiskLevel.CRITICAL
            risk_factors = ["Destructive operation"]
        else:
            risk_level = RiskLevel.MEDIUM
            risk_factors = ["Unknown query type"]
        
        return ActionPreview(
            file_changes=[],
            risk_level=risk_level,
            risk_factors=risk_factors,
            summary=f"Execute SQL: {query[:100]}{'...' if len(query) > 100 else ''}",
            affected_count=0,
            warnings=["Full database preview coming in v0.3"],
            is_reversible=not query_upper.startswith(("DROP", "TRUNCATE")),
        )
    
    async def _analyze_api_call(self, request: ActionRequest) -> ActionPreview:
        """Analyze API calls (placeholder for v0.4)."""
        method = request.payload.get("method", "GET").upper()
        url = request.target
        
        if method == "GET":
            risk_level = RiskLevel.LOW
            risk_factors = ["Read-only request"]
        elif method in ["POST", "PUT", "PATCH"]:
            risk_level = RiskLevel.MEDIUM
            risk_factors = ["Data modification request"]
        elif method == "DELETE":
            risk_level = RiskLevel.HIGH
            risk_factors = ["Deletion request"]
        else:
            risk_level = RiskLevel.MEDIUM
            risk_factors = []
        
        return ActionPreview(
            file_changes=[],
            risk_level=risk_level,
            risk_factors=risk_factors,
            summary=f"{method} {url[:80]}{'...' if len(url) > 80 else ''}",
            affected_count=0,
            warnings=["Full API preview coming in v0.4"],
            is_reversible=method == "GET",
        )
    
    async def _analyze_custom(self, request: ActionRequest) -> ActionPreview:
        """Analyze custom actions."""
        return ActionPreview(
            file_changes=[],
            risk_level=RiskLevel.MEDIUM,
            risk_factors=["Custom action - cannot analyze automatically"],
            summary=f"Custom action: {request.description[:100]}",
            affected_count=0,
            warnings=["Custom actions require manual review"],
            is_reversible=False,
        )
    
    def _assess_file_risks(
        self,
        path: str,
        action_type: ActionType,
        content: str = "",
    ) -> tuple[RiskLevel, list[str]]:
        """
        Assess risk level for a file operation.
        
        Returns (risk_level, risk_factors)
        """
        risk_factors = []
        risk_level = RiskLevel.LOW
        
        path_lower = path.lower()
        
        # Check for high-risk paths
        for pattern in self.HIGH_RISK_PATHS:
            if pattern in path_lower:
                risk_level = RiskLevel.HIGH
                risk_factors.append(f"Sensitive path pattern: {pattern}")
        
        # Check for critical patterns
        for pattern in self.CRITICAL_PATTERNS:
            if pattern in path_lower or pattern in content.lower():
                risk_level = RiskLevel.CRITICAL
                risk_factors.append(f"Critical pattern detected: {pattern}")
        
        # Delete operations are always at least medium risk
        if action_type == ActionType.FILE_DELETE:
            if risk_level == RiskLevel.LOW:
                risk_level = RiskLevel.MEDIUM
            risk_factors.append("File deletion")
        
        # Large files are riskier
        if len(content) > 100000:  # > 100KB
            if risk_level == RiskLevel.LOW:
                risk_level = RiskLevel.MEDIUM
            risk_factors.append(f"Large file: {len(content)} bytes")
        
        # System directories (but not safe temp directories)
        is_safe_path = any(path.startswith(prefix) for prefix in self.SAFE_PATH_PREFIXES)
        if path.startswith("/") and not path.startswith("/home") and not is_safe_path:
            risk_level = RiskLevel.HIGH
            risk_factors.append("System directory")
        
        return risk_level, risk_factors


# Singleton instance
_analyzer: ImpactAnalyzer | None = None


def get_analyzer(working_directory: str | None = None) -> ImpactAnalyzer:
    """Get the impact analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = ImpactAnalyzer(working_directory)
    return _analyzer
