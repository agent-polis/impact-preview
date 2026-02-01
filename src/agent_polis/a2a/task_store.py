"""
In-memory task store for A2A tasks.

For MVP, tasks are stored in memory. In production, this would be
backed by Redis or the database for persistence and scaling.
"""

from datetime import datetime, timezone
from typing import Dict

from agent_polis.a2a.models import Task


class TaskStore:
    """
    In-memory store for A2A tasks.
    
    Tasks represent ongoing conversations/work items with other agents.
    """
    
    def __init__(self):
        self._tasks: Dict[str, Task] = {}
    
    async def save(self, task: Task) -> None:
        """Save or update a task."""
        task.updated_at = datetime.now(timezone.utc)
        self._tasks[task.id] = task
    
    async def get(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)
    
    async def delete(self, task_id: str) -> bool:
        """Delete a task. Returns True if existed."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False
    
    async def list_active(self) -> list[Task]:
        """List all active (non-completed) tasks."""
        from agent_polis.a2a.models import TaskStatus
        return [
            t for t in self._tasks.values()
            if t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELED, TaskStatus.FAILED]
        ]
    
    async def cleanup_old(self, max_age_hours: int = 24) -> int:
        """Remove tasks older than max_age_hours. Returns count removed."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        old_ids = [
            tid for tid, task in self._tasks.items()
            if task.updated_at < cutoff
        ]
        for tid in old_ids:
            del self._tasks[tid]
        return len(old_ids)


# Global task store instance
_task_store = TaskStore()


def get_task_store() -> TaskStore:
    """Get the global task store instance."""
    return _task_store
