"""
ClaudeTaskRepository — CRUD for ClaudeTaskModel.
"""
import logging
from typing import Optional

from services.storage.db import get_session
from services.storage.models.claude_task import ClaudeTaskModel

log = logging.getLogger(__name__)


class ClaudeTaskRepository:

    def create(self, **kwargs) -> ClaudeTaskModel:
        task = ClaudeTaskModel(**kwargs)
        with get_session() as s:
            s.add(task)
        log.info(f"[ClaudeTaskRepo] created {task.id}")
        return task

    def get(self, task_id: str) -> Optional[ClaudeTaskModel]:
        with get_session() as s:
            return s.get(ClaudeTaskModel, task_id)

    def update(self, task_id: str, **fields) -> Optional[ClaudeTaskModel]:
        with get_session() as s:
            task = s.get(ClaudeTaskModel, task_id)
            if task is None:
                return None
            for k, v in fields.items():
                setattr(task, k, v)
        return task
