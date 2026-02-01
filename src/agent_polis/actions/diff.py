"""
Diff generation for file changes.

Creates human-readable diffs showing exactly what will change.
"""

import difflib
from pathlib import Path
from typing import Literal

from agent_polis.actions.models import FileChange


def generate_unified_diff(
    original: str,
    modified: str,
    filename: str = "file",
    context_lines: int = 3,
) -> str:
    """
    Generate a unified diff between two strings.
    
    Args:
        original: Original content
        modified: Modified content
        filename: Name to show in diff header
        context_lines: Number of context lines around changes
        
    Returns:
        Unified diff string
    """
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    
    # Ensure trailing newlines for cleaner diffs
    if original_lines and not original_lines[-1].endswith('\n'):
        original_lines[-1] += '\n'
    if modified_lines and not modified_lines[-1].endswith('\n'):
        modified_lines[-1] += '\n'
    
    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=context_lines,
    )
    
    return ''.join(diff)


def generate_file_change(
    path: str,
    operation: Literal["create", "modify", "delete", "move"],
    original_content: str | None = None,
    new_content: str | None = None,
    destination_path: str | None = None,
) -> FileChange:
    """
    Generate a FileChange object with diff.
    
    Args:
        path: File path
        operation: Type of operation
        original_content: Original file content (for modify/delete)
        new_content: New content (for create/modify)
        destination_path: Destination (for move)
        
    Returns:
        FileChange with computed diff and stats
    """
    diff = None
    lines_added = 0
    lines_removed = 0
    
    if operation == "create":
        # New file - show all lines as added
        if new_content:
            lines = new_content.splitlines()
            lines_added = len(lines)
            diff = generate_unified_diff("", new_content, path)
            
    elif operation == "modify":
        # Modified file - show unified diff
        if original_content is not None and new_content is not None:
            diff = generate_unified_diff(original_content, new_content, path)
            
            # Count changes
            for line in diff.splitlines():
                if line.startswith('+') and not line.startswith('+++'):
                    lines_added += 1
                elif line.startswith('-') and not line.startswith('---'):
                    lines_removed += 1
                    
    elif operation == "delete":
        # Deleted file - show all lines as removed
        if original_content:
            lines = original_content.splitlines()
            lines_removed = len(lines)
            diff = generate_unified_diff(original_content, "", path)
            
    elif operation == "move":
        # Move shows as rename in diff header
        diff = f"rename from {path}\nrename to {destination_path}\n"
    
    return FileChange(
        path=path,
        operation=operation,
        original_content=original_content,
        new_content=new_content,
        destination_path=destination_path,
        diff=diff,
        lines_added=lines_added,
        lines_removed=lines_removed,
        file_size_before=len(original_content) if original_content else None,
        file_size_after=len(new_content) if new_content else None,
    )


def format_diff_terminal(changes: list[FileChange]) -> str:
    """
    Format file changes for terminal output with colors.
    
    Returns ANSI-colored string for terminal display.
    """
    output = []
    
    for change in changes:
        # Header
        if change.operation == "create":
            output.append(f"\033[32m+ {change.path}\033[0m (new file)")
        elif change.operation == "delete":
            output.append(f"\033[31m- {change.path}\033[0m (deleted)")
        elif change.operation == "modify":
            output.append(f"\033[33m~ {change.path}\033[0m (modified)")
        elif change.operation == "move":
            output.append(f"\033[34m→ {change.path}\033[0m → {change.destination_path}")
        
        # Stats
        if change.lines_added or change.lines_removed:
            output.append(
                f"  \033[32m+{change.lines_added}\033[0m "
                f"\033[31m-{change.lines_removed}\033[0m"
            )
        
        # Diff (if present)
        if change.diff:
            for line in change.diff.splitlines():
                if line.startswith('+') and not line.startswith('+++'):
                    output.append(f"  \033[32m{line}\033[0m")
                elif line.startswith('-') and not line.startswith('---'):
                    output.append(f"  \033[31m{line}\033[0m")
                elif line.startswith('@@'):
                    output.append(f"  \033[36m{line}\033[0m")
                else:
                    output.append(f"  {line}")
        
        output.append("")
    
    return '\n'.join(output)


def format_diff_plain(changes: list[FileChange]) -> str:
    """
    Format file changes as plain text (no colors).
    """
    output = []
    
    for change in changes:
        output.append(f"{'='*60}")
        output.append(f"File: {change.path}")
        output.append(f"Operation: {change.operation}")
        
        if change.destination_path:
            output.append(f"Destination: {change.destination_path}")
        
        if change.lines_added or change.lines_removed:
            output.append(f"Changes: +{change.lines_added} -{change.lines_removed}")
        
        if change.diff:
            output.append("")
            output.append(change.diff)
        
        output.append("")
    
    return '\n'.join(output)


def format_diff_summary(changes: list[FileChange]) -> str:
    """
    Generate a short summary of changes.
    """
    if not changes:
        return "No changes"
    
    creates = sum(1 for c in changes if c.operation == "create")
    modifies = sum(1 for c in changes if c.operation == "modify")
    deletes = sum(1 for c in changes if c.operation == "delete")
    moves = sum(1 for c in changes if c.operation == "move")
    
    total_added = sum(c.lines_added for c in changes)
    total_removed = sum(c.lines_removed for c in changes)
    
    parts = []
    if creates:
        parts.append(f"{creates} file(s) created")
    if modifies:
        parts.append(f"{modifies} file(s) modified")
    if deletes:
        parts.append(f"{deletes} file(s) deleted")
    if moves:
        parts.append(f"{moves} file(s) moved")
    
    summary = ", ".join(parts)
    summary += f" (+{total_added} -{total_removed} lines)"
    
    return summary
