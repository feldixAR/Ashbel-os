"""Lead / CRM repository."""
import datetime
from typing import List, Optional
from services.storage.db import get_session
from services.storage.models.lead import LeadModel, LeadHistoryModel
from .base_repo import BaseRepository, utcnow_iso


class LeadRepository(BaseRepository[LeadModel]):
    model_class = LeadModel

    def create(self, name: str, city: str, phone: str,
                source: str, notes: str = "") -> LeadModel:
        from services.storage.models.base import new_uuid
        lead = LeadModel(
            id=new_uuid(), name=name, city=city,
            phone=phone, source=source, notes=notes,
            status="חדש", score=0, attempts=0,
        )
        with get_session() as s:
            s.add(lead)
        return lead

    def all_sorted_by_score(self, status: Optional[str] = None) -> List[LeadModel]:
        with get_session() as s:
            q = s.query(LeadModel)
            if status:
                q = q.filter(LeadModel.status == status)
            return q.order_by(LeadModel.score.desc()).all()

    def update_status(self, lead_id: str, status: str) -> None:
        with get_session() as s:
            lead = s.get(LeadModel, lead_id)
            if lead:
                lead.status       = status
                lead.last_contact = utcnow_iso()

    def update_score(self, lead_id: str, score: int) -> None:
        with get_session() as s:
            lead = s.get(LeadModel, lead_id)
            if lead:
                lead.score = score

    def increment_attempts(self, lead_id: str, response: str = "") -> None:
        with get_session() as s:
            lead = s.get(LeadModel, lead_id)
            if lead:
                lead.attempts     = (lead.attempts or 0) + 1
                lead.last_contact = utcnow_iso()
                if response:
                    lead.response = response

    def append_history(self, lead_id: str, action: str,
                        note: str = "", agent_id: str = "",
                        model_used: str = "") -> None:
        from services.storage.models.base import new_uuid
        entry = LeadHistoryModel(
            id=new_uuid(), lead_id=lead_id,
            action=action, note=note,
            agent_id=agent_id or None,
            model_used=model_used or None,
            created_at=utcnow_iso(),
        )
        with get_session() as s:
            s.add(entry)

    def get_hot_leads(self, min_score: int = 70) -> List[LeadModel]:
        with get_session() as s:
            return (s.query(LeadModel)
                    .filter(LeadModel.score >= min_score,
                            LeadModel.status.notin_(["סגור_זכה", "סגור_הפסיד"]))
                    .order_by(LeadModel.score.desc())
                    .all())

    def get_pending_followup(self, max_attempts: int = 5) -> List[LeadModel]:
        with get_session() as s:
            return (s.query(LeadModel)
                    .filter(LeadModel.attempts < max_attempts,
                            LeadModel.status.in_(["ניסיון קשר", "חדש", "מתעניין"]))
                    .order_by(LeadModel.score.desc())
                    .all())
