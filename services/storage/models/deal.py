"""
DealModel — Revenue CRM deal with stage lifecycle.
Stages: new → qualified → proposal → negotiation → won | lost
"""
from sqlalchemy import Column, Float, Integer, String, Text
from .base import Base, TimestampMixin, new_uuid

DEAL_STAGES = ("new", "qualified", "proposal", "negotiation", "won", "lost")


class DealModel(Base, TimestampMixin):
    __tablename__ = "deals"

    id                 = Column(String(36),  primary_key=True, default=new_uuid)
    lead_id            = Column(String(36),  nullable=False, index=True)
    title              = Column(String(200), nullable=False)
    stage              = Column(String(30),  nullable=False, default="new", index=True)
    value_ils          = Column(Integer,     nullable=False, default=0)
    probability        = Column(Float,       nullable=False, default=0.20)  # 0–1
    expected_close_date = Column(String(20), nullable=True)   # ISO date, IL tz
    owner_agent_id     = Column(String(36),  nullable=True)
    source             = Column(String(60),  nullable=True)   # whatsapp/email/referral/...
    next_action        = Column(Text,        nullable=True)
    next_action_at     = Column(String(40),  nullable=True)   # ISO-8601 IL tz
    closed_at          = Column(String(40),  nullable=True)
    close_reason       = Column(Text,        nullable=True)

    def weighted_value(self) -> int:
        return int(self.value_ils * self.probability)

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "lead_id":             self.lead_id,
            "title":               self.title,
            "stage":               self.stage,
            "value_ils":           self.value_ils,
            "probability":         self.probability,
            "weighted_value":      self.weighted_value(),
            "expected_close_date": self.expected_close_date,
            "owner_agent_id":      self.owner_agent_id,
            "source":              self.source,
            "next_action":         self.next_action,
            "next_action_at":      self.next_action_at,
            "closed_at":           self.closed_at,
            "close_reason":        self.close_reason,
            "created_at":          str(self.created_at) if self.created_at else None,
            "updated_at":          str(self.updated_at) if self.updated_at else None,
        }
