"""
OpportunityModel — persists identified growth opportunities per goal.
Batch 6: Goal & Growth Engine.
"""
from sqlalchemy import Boolean, Column, Float, Integer, String, Text
from .base import Base, TimestampMixin, new_uuid


class OpportunityModel(Base, TimestampMixin):
    __tablename__ = "opportunities"

    id                   = Column(String(36), primary_key=True, default=new_uuid)
    goal_id              = Column(String(36), nullable=False, index=True)
    track_id             = Column(String(36), nullable=True)
    title                = Column(Text,       nullable=False)
    audience             = Column(String(60), nullable=False, default="general")
    channel              = Column(String(40), nullable=False, default="whatsapp")

    # Legacy string categories (backward-compat)
    potential            = Column(String(20), nullable=False, default="medium")  # high/medium/low
    effort               = Column(String(20), nullable=False, default="medium")  # low/medium/high

    # Numeric scoring fields
    normalized_score     = Column(Float,   nullable=True)   # 1-100
    raw_score            = Column(Float,   nullable=True)   # (revenue * prob) / effort
    success_probability  = Column(Float,   nullable=True)   # 0.0–1.0
    revenue_potential    = Column(Integer, nullable=True)   # ILS
    effort_hours         = Column(Integer, nullable=True)   # hours to close

    # Committee fields
    committee_rank       = Column(Integer, nullable=True)   # 1 = best
    is_committee_winner  = Column(Boolean, nullable=False, default=False)

    next_action          = Column(Text,       nullable=True)
    status               = Column(String(20), nullable=False, default="open", index=True)

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "goal_id":             self.goal_id,
            "track_id":            self.track_id,
            "title":               self.title,
            "audience":            self.audience,
            "channel":             self.channel,
            "potential":           self.potential,
            "effort":              self.effort,
            "normalized_score":    self.normalized_score,
            "raw_score":           self.raw_score,
            "success_probability": self.success_probability,
            "revenue_potential":   self.revenue_potential,
            "effort_hours":        self.effort_hours,
            "committee_rank":      self.committee_rank,
            "is_committee_winner": self.is_committee_winner,
            "next_action":         self.next_action,
            "status":              self.status,
            "created_at":          str(self.created_at) if self.created_at else None,
        }
