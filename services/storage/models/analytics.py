"""
PerformanceMetric — rolling conversion KPIs per dimension.
Batch 10: Learning & Revenue Feedback Loop.

dim_type  : 'channel' | 'audience' | 'opp_type'
dim_value : e.g. 'whatsapp', 'contractors', '[whatsapp] goal title'

Unique constraint on (dim_type, dim_value) — one row per slice.
Updated in-place by LearningEngine.compute_lifecycle_metrics().
"""
from sqlalchemy import Column, Float, Integer, String, Text, UniqueConstraint
from .base import Base, TimestampMixin, new_uuid


class PerformanceMetric(Base, TimestampMixin):
    __tablename__ = "performance_metrics"

    id              = Column(String(36), primary_key=True, default=new_uuid)
    dim_type        = Column(String(30),  nullable=False, index=True)   # channel/audience/opp_type
    dim_value       = Column(String(120), nullable=False, index=True)
    window_days     = Column(Integer,     nullable=False, default=30)

    # Counts
    total_sent      = Column(Integer, nullable=False, default=0)
    total_replied   = Column(Integer, nullable=False, default=0)  # awaiting + followup_sent
    total_won       = Column(Integer, nullable=False, default=0)  # closed_won
    total_lost      = Column(Integer, nullable=False, default=0)  # closed_lost

    # Revenue
    total_revenue_ils = Column(Integer, nullable=False, default=0)
    avg_deal_ils      = Column(Integer, nullable=False, default=15_000)

    # Derived
    conversion_rate   = Column(Float, nullable=False, default=0.0)  # total_won / total_sent
    reply_rate        = Column(Float, nullable=False, default=0.0)   # total_replied / total_sent

    # Audit
    computed_at     = Column(String(40), nullable=True)   # ISO-8601, Asia/Jerusalem
    sample_size     = Column(Integer,    nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("dim_type", "dim_value", name="uq_metric_dim"),
    )

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "dim_type":         self.dim_type,
            "dim_value":        self.dim_value,
            "window_days":      self.window_days,
            "total_sent":       self.total_sent,
            "total_replied":    self.total_replied,
            "total_won":        self.total_won,
            "total_lost":       self.total_lost,
            "total_revenue_ils": self.total_revenue_ils,
            "avg_deal_ils":     self.avg_deal_ils,
            "conversion_rate":  round(self.conversion_rate, 4),
            "reply_rate":       round(self.reply_rate, 4),
            "computed_at":      self.computed_at,
            "sample_size":      self.sample_size,
        }
