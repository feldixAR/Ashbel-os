"""Durable at-most-once claims for scheduled job occurrences."""
from sqlalchemy import Column, String, Text
from .base import Base, TimestampMixin


class SchedulerRunModel(Base, TimestampMixin):
    __tablename__ = 'scheduler_runs'

    job_id = Column(String(80), primary_key=True)
    slot = Column(String(40), primary_key=True)
    status = Column(String(20), nullable=False, default='claimed')
    finished_at = Column(String(40), nullable=True)
    error = Column(Text, nullable=True)
