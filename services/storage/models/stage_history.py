"""
StageHistoryModel — immutable audit log of deal stage transitions.
Append-only. Never updated after insert.
"""
from sqlalchemy import Column, String, Text
from .base import Base, TimestampMixin, new_uuid


class StageHistoryModel(Base, TimestampMixin):
    __tablename__ = "stage_history"

    id          = Column(String(36),  primary_key=True, default=new_uuid)
    deal_id     = Column(String(36),  nullable=False, index=True)
    lead_id     = Column(String(36),  nullable=False, index=True)
    from_stage  = Column(String(30),  nullable=False)
    to_stage    = Column(String(30),  nullable=False)
    reason      = Column(Text,        nullable=True)
    changed_by  = Column(String(120), nullable=True)   # agent id / "system" / "api"
    changed_at_il = Column(String(40), nullable=False)  # ISO-8601 Asia/Jerusalem

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "deal_id":       self.deal_id,
            "lead_id":       self.lead_id,
            "from_stage":    self.from_stage,
            "to_stage":      self.to_stage,
            "reason":        self.reason,
            "changed_by":    self.changed_by,
            "changed_at_il": self.changed_at_il,
            "created_at":    str(self.created_at) if self.created_at else None,
        }
