"""Approval repository."""
from typing import List, Optional
from services.storage.db import get_session
from services.storage.models.approval import ApprovalModel
from .base_repo import BaseRepository, utcnow_iso


class ApprovalRepository(BaseRepository[ApprovalModel]):
    model_class = ApprovalModel

    def create(self, action: str, details: dict, risk_level: int,
                task_id: str = None, requested_by: str = "system") -> ApprovalModel:
        from services.storage.models.base import new_uuid
        approval = ApprovalModel(
            id=new_uuid(), action=action, details=details,
            risk_level=risk_level, task_id=task_id,
            requested_by=requested_by, status="pending",
        )
        with get_session() as s:
            s.add(approval)
        return approval

    def resolve(self, approval_id: str, status: str,
                 resolved_by: str = "owner", note: str = "") -> Optional[ApprovalModel]:
        with get_session() as s:
            approval = s.get(ApprovalModel, approval_id)
            if not approval or approval.status != "pending":
                return None
            approval.status      = status
            approval.resolved_by = resolved_by
            approval.resolved_at = utcnow_iso()
            approval.note        = note
        return approval

    def get_pending(self) -> List[ApprovalModel]:
        with get_session() as s:
            return (s.query(ApprovalModel)
                    .filter_by(status="pending")
                    .order_by(ApprovalModel.created_at)
                    .all())

    def get_resolved(self, limit: int = 50) -> List[ApprovalModel]:
        with get_session() as s:
            return (s.query(ApprovalModel)
                    .filter(ApprovalModel.status.in_(["approved", "denied"]))
                    .order_by(ApprovalModel.resolved_at.desc())
                    .limit(limit)
                    .all())
