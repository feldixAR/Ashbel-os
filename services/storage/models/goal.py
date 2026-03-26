"""
GoalModel — persists a business goal and its decomposed tracks.
Batch 6: Goal & Growth Engine.
"""
import json as _json
from sqlalchemy import Column, String, Text, JSON
from .base import Base, TimestampMixin, new_uuid


class GoalModel(Base, TimestampMixin):
    __tablename__ = "goals"

    id                       = Column(String(36), primary_key=True, default=new_uuid)
    raw_goal                 = Column(Text,        nullable=False)
    domain                   = Column(String(60),  nullable=False, default="default", index=True)
    primary_metric           = Column(String(60),  nullable=False, default="revenue")
    status                   = Column(String(30),  nullable=False, default="active", index=True)
    tracks                   = Column(JSON,         nullable=True)   # list of track dicts

    # Committee output — full blob
    committee_decision       = Column(Text,        nullable=True)   # JSON string — CommitteeDecision

    # Committee output — scalar / structured for fast queries
    committee_winner_title   = Column(String(200), nullable=True)
    committee_reasoning      = Column(Text,        nullable=True)
    prioritized_actions_json = Column(Text,        nullable=True)   # JSON array string

    # Pipeline lifecycle
    goal_status              = Column(String(30),  nullable=False, default="analyzed", index=True)
    # Values: 'analyzed' | 'approved' | 'executing'

    def to_dict(self) -> dict:
        committee = None
        if self.committee_decision:
            try:
                committee = _json.loads(self.committee_decision)
            except Exception:
                committee = self.committee_decision

        prioritized = None
        if self.prioritized_actions_json:
            try:
                prioritized = _json.loads(self.prioritized_actions_json)
            except Exception:
                prioritized = self.prioritized_actions_json

        return {
            "id":                       self.id,
            "raw_goal":                 self.raw_goal,
            "domain":                   self.domain,
            "primary_metric":           self.primary_metric,
            "status":                   self.status,
            "goal_status":              self.goal_status,
            "tracks":                   self.tracks or [],
            "committee_decision":       committee,
            "committee_winner_title":   self.committee_winner_title,
            "committee_reasoning":      self.committee_reasoning,
            "prioritized_actions":      prioritized or [],
            "created_at":               str(self.created_at) if self.created_at else None,
        }
