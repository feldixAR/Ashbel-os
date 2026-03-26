"""OutreachRepository — Batch 6 / Batch 9."""
import datetime
from typing import List, Optional
from services.storage.db import get_session
from services.storage.models.outreach import OutreachModel
from services.storage.models.base import new_uuid
from .base_repo import BaseRepository


class OutreachRepository(BaseRepository[OutreachModel]):
    model_class = OutreachModel

    def create(self, goal_id: str, opp_id: str, contact_name: str,
               contact_phone: str, channel: str, message_body: str) -> OutreachModel:
        next_followup = (datetime.datetime.utcnow() + datetime.timedelta(days=3)).isoformat()
        record = OutreachModel(
            id=new_uuid(),
            goal_id=goal_id, opp_id=opp_id,
            contact_name=contact_name, contact_phone=contact_phone,
            channel=channel, message_body=message_body,
            next_followup=next_followup,
        )
        with get_session() as s:
            s.add(record)
        return record

    def get_by_id(self, record_id: str) -> Optional[OutreachModel]:
        with get_session() as s:
            return s.query(OutreachModel).filter_by(id=record_id).first()

    def list_by_goal(self, goal_id: str) -> List[OutreachModel]:
        with get_session() as s:
            return (s.query(OutreachModel)
                    .filter_by(goal_id=goal_id)
                    .order_by(OutreachModel.created_at)
                    .all())

    def list_due_followup(self) -> List[OutreachModel]:
        """Legacy: records with next_followup <= now (status-based)."""
        now = datetime.datetime.utcnow().isoformat()
        with get_session() as s:
            return (s.query(OutreachModel)
                    .filter(OutreachModel.status.in_(["pending", "sent"]),
                            OutreachModel.next_followup <= now)
                    .order_by(OutreachModel.next_followup)
                    .limit(20).all())

    def list_lifecycle_due(self, limit: int = 50) -> List[OutreachModel]:
        """Batch 9: records where lifecycle_status='followup_due'."""
        with get_session() as s:
            return (s.query(OutreachModel)
                    .filter_by(lifecycle_status="followup_due")
                    .order_by(OutreachModel.next_action_at)
                    .limit(limit).all())

    def list_by_lifecycle(self, lifecycle_status: str,
                           limit: int = 50) -> List[OutreachModel]:
        """Return records filtered by lifecycle_status."""
        with get_session() as s:
            return (s.query(OutreachModel)
                    .filter_by(lifecycle_status=lifecycle_status)
                    .order_by(OutreachModel.created_at.desc())
                    .limit(limit).all())

    def set_lifecycle_status(self, record_id: str, lifecycle_status: str,
                              notes: str = "") -> bool:
        """Update lifecycle_status for a single record. Returns True on success."""
        with get_session() as s:
            record = s.query(OutreachModel).filter_by(id=record_id).first()
            if not record:
                return False
            record.lifecycle_status = lifecycle_status
            if notes:
                record.notes = (record.notes or "") + f"\n[{lifecycle_status}] {notes}"
        return True
