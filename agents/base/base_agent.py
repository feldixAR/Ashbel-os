"""
BaseAgent — abstract base class for all agents.

Every agent must implement:
    can_handle(task_type, action) -> bool   deterministic, no I/O
    execute(task)                 -> ExecutionResult   never raises

execute() must catch all exceptions internally and return
ExecutionResult(success=False, ...) on failure.
"""

import logging
from abc import ABC, abstractmethod

from services.storage.models.task import TaskModel
from services.execution.executor  import ExecutionResult

log = logging.getLogger(__name__)


class BaseAgent(ABC):

    agent_id:   str = ""
    name:       str = ""
    department: str = ""
    version:    int = 1

    @abstractmethod
    def can_handle(self, task_type: str, action: str) -> bool:
        """Return True if this agent handles this task_type + action pair."""

    @abstractmethod
    def execute(self, task: TaskModel) -> ExecutionResult:
        """Execute task. Must never raise."""

    # ── Helpers available to all subclasses ───────────────────────────────────

    def _input_params(self, task: TaskModel) -> dict:
        """Safely extract params from task.input_data."""
        return (task.input_data or {}).get("params", {})

    def _safe_str(self, value, default: str = "") -> str:
        if value is None:
            return default
        return str(value).strip() or default

    def __repr__(self) -> str:
        return (f"<{self.__class__.__name__} "
                f"id={self.agent_id!r} dept={self.department!r} v={self.version}>")
