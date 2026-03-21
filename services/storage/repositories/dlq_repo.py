"""Dead Letter Queue repository."""
from typing import List
from services.storage.db import get_session
from services.storage.models.dlq import DLQModel
from .base_repo import BaseRepository, utcnow_iso


class DLQRepository(BaseRepository[DLQModel]):
    model_class = DLQModel

    def push(self, original_task_id: str, action: str,
              payload: dict, failure_reason: str,
              attempts_made: int) -> DLQModel:
        from services.storage.models.base import new_uuid
        entry = DLQModel(
            id=new_uuid(),
            original_task_id=original_task_id,
            action=action, payload=payload,
            failure_reason=failure_reason,
            attempts_made=attempts_made,
            status="pending_review",
        )
        with get_session() as s:
            s.add(entry)
        return entry

    def get_pending(self) -> List[DLQModel]:
        with get_session() as s:
            return (s.query(DLQModel)
                    .filter_by(status="pending_review")
                    .order_by(DLQModel.created_at)
                    .all())

    def resolve(self, dlq_id: str, status: str, note: str = "") -> None:
        with get_session() as s:
            entry = s.get(DLQModel, dlq_id)
            if entry:
                entry.status       = status
                entry.resolved_at  = utcnow_iso()
                entry.resolved_note = note
