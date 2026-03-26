"""
GoalModel — persists a business goal and its decomposed tracks.
Batch 6: Goal & Growth Engine.
"""
import json as _json
from sqlalchemy import Column, String, Text, JSON
from .base import Base, TimestampMixin, new_uuid


class GoalModel(Base, TimestampMixin):
    __tablename__ = "goals"

    id                 = Column(String(36), primary_key=True, default=new_uuid)
    raw_goal           = Column(Text,       nullable=False)
    domain             = Column(String(60), nullable=False, default="default", index=True)
    primary_metric     = Column(String(60), nullable=False, default="revenue")
    status             = Column(String(30), nullable=False, default="active", index=True)
    tracks             = Column(JSON,       nullable=True)   # list of track dicts
    committee_decision = Column(Text,       nullable=True)   # JSON string — CommitteeDecision

    def to_dict(self) -> dict:
        committee = None
        if self.committee_decision:
            try:
                committee = _json.loads(self.committee_decision)
            except Exception:
                committee = self.committee_decision
        return {
            "id":                 self.id,
            "raw_goal":           self.raw_goal,
            "domain":             self.domain,
            "primary_metric":     self.primary_metric,
            "status":             self.status,
            "tracks":             self.tracks or [],
            "committee_decision": committee,
            "created_at":         str(self.created_at) if self.created_at else None,
        }
