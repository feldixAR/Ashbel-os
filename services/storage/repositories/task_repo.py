"""Task repository."""
from typing import List, Optional
from services.storage.db import get_session
from services.storage.models.task import TaskModel
from .base_repo import BaseRepository, utcnow_iso


class TaskRepository(BaseRepository[TaskModel]):
    model_class = TaskModel

    def create(self, type: str, action: str, input_data: dict,
                priority: int = 5, risk_level: int = 1,
                agent_id: str = None, parent_task_id: str = None,
                trace_id: str = None, max_retries: int = 3) -> TaskModel:
        from services.storage.models.base import new_uuid
        task = TaskModel(
            id=new_uuid(), type=type, action=action,
            input_data=input_data, priority=priority,
            risk_level=risk_level, agent_id=agent_id,
            parent_task_id=parent_task_id, trace_id=trace_id,
            max_retries=max_retries, status="created",
        )
        with get_session() as s:
            s.add(task)
        return task

    def transition(self, task_id: str, new_status: str, **kwargs) -> None:
        with get_session() as s:
            task = s.get(TaskModel, task_id)
            if not task:
                return
            task.status = new_status
            for k, v in kwargs.items():
                setattr(task, k, v)
            if new_status == "running" and not task.started_at:
                task.started_at = utcnow_iso()
            if new_status in ("done", "failed", "dead_lettered"):
                task.completed_at = utcnow_iso()

    def mark_retry(self, task_id: str, error: str) -> int:
        """Increments retry_count, returns new count."""
        with get_session() as s:
            task = s.get(TaskModel, task_id)
            if not task:
                return 0
            task.retry_count += 1
            task.last_error   = error
            task.status       = "queued"
            return task.retry_count

    def get_pending(self, limit: int = 50) -> List[TaskModel]:
        with get_session() as s:
            return (s.query(TaskModel)
                    .filter(TaskModel.status.in_(["queued", "created"]))
                    .order_by(TaskModel.priority, TaskModel.created_at)
                    .limit(limit)
                    .all())

    def get_by_status(self, status: str) -> List[TaskModel]:
        with get_session() as s:
            return (s.query(TaskModel)
                    .filter_by(status=status)
                    .order_by(TaskModel.created_at.desc())
                    .all())

    def get_by_trace(self, trace_id: str) -> List[TaskModel]:
        with get_session() as s:
            return (s.query(TaskModel)
                    .filter_by(trace_id=trace_id)
                    .order_by(TaskModel.created_at)
                    .all())
