"""
SentNotification — deduplication table for scheduled Telegram deliveries.

Schema:
    id            — UUID primary key
    lead_id       — references leads.id (string FK, not enforced for resilience)
    delivery_date — ISO date string in Israel timezone (e.g. "2026-03-26")
    status        — "sent" | "failed"
    created_at    — UTC timestamp of the insert

UNIQUE constraint on (lead_id, delivery_date):
    Enforced at DB level. Workers race to INSERT; only one succeeds.
    The loser receives IntegrityError and skips the delivery.
"""

from sqlalchemy import Column, Date, String, UniqueConstraint
from .base import Base, TimestampMixin, new_uuid


class SentNotificationModel(Base, TimestampMixin):
    __tablename__ = "sent_notifications"

    id            = Column(String(36), primary_key=True, default=new_uuid)
    lead_id       = Column(String(36), nullable=False, index=True)
    delivery_date = Column(Date,       nullable=False)   # Israel TZ date (datetime.date)
    status        = Column(String(20), nullable=False, default="sent")

    __table_args__ = (
        UniqueConstraint("lead_id", "delivery_date", name="idx_lead_delivery_date_unique"),
    )

    def __repr__(self) -> str:
        return f"<SentNotification lead={self.lead_id} date={self.delivery_date} status={self.status}>"
