"""
OpportunityModel — persists identified growth opportunities per goal.
Batch 6: Goal & Growth Engine.
"""
from sqlalchemy import Column, String, Text, ForeignKey
from .base import Base, TimestampMixin, new_uuid


class OpportunityModel(Base, TimestampMixin):
    __tablename__ = "opportunities"

    id          = Column(String(36), primary_key=True, default=new_uuid)
    goal_id     = Column(String(36), nullable=False, index=True)
    track_id    = Column(String(36), nullable=True)
    title       = Column(Text,       nullable=False)
    audience    = Column(String(60), nullable=False, default="general")
    channel     = Column(String(40), nullable=False, default="whatsapp")
    potential   = Column(String(20), nullable=False, default="medium")  # high/medium/low
    effort      = Column(String(20), nullable=False, default="medium")  # low/medium/high
    next_action = Column(Text,       nullable=True)
    status      = Column(String(20), nullable=False, default="open", index=True)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "goal_id":     self.goal_id,
            "track_id":    self.track_id,
            "title":       self.title,
            "audience":    self.audience,
            "channel":     self.channel,
            "potential":   self.potential,
            "effort":      self.effort,
            "next_action": self.next_action,
            "status":      self.status,
            "created_at":  str(self.created_at) if self.created_at else None,
        }
