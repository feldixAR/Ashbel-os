"""OutreachRepository — Batch 6."""
import datetime
from typing import List
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

    def list_by_goal(self, goal_id: str) -> List[OutreachModel]:
        with get_session() as s:
            return (s.query(OutreachModel)
                    .filter_by(goal_id=goal_id)
                    .order_by(OutreachModel.created_at)
                    .all())

    def list_due_followup(self) -> List[OutreachModel]:
        now = datetime.datetime.utcnow().isoformat()
        with get_session() as s:
            return (s.query(OutreachModel)
                    .filter(OutreachModel.status.in_(["pending", "sent"]),
                            OutreachModel.next_followup <= now)
                    .order_by(OutreachModel.next_followup)
                    .limit(20).all())
