"""Persistent import run report for safe lead intake."""
from sqlalchemy import Column, Integer, String, Text, JSON
from .base import Base, TimestampMixin, new_uuid


class ImportRunModel(Base, TimestampMixin):
    __tablename__ = "import_runs"

    id              = Column(String(36), primary_key=True, default=new_uuid)
    source_file     = Column(String(300), nullable=False)
    source_format   = Column(String(40), nullable=True)
    status          = Column(String(40), nullable=False, default="preview")
    operator        = Column(String(120), nullable=True)
    approval_id     = Column(String(36), nullable=True, index=True)
    raw_count       = Column(Integer, nullable=False, default=0)
    approved_count  = Column(Integer, nullable=False, default=0)
    created_count   = Column(Integer, nullable=False, default=0)
    skipped_count   = Column(Integer, nullable=False, default=0)
    duplicate_count = Column(Integer, nullable=False, default=0)
    error_count     = Column(Integer, nullable=False, default=0)
    lead_ids        = Column(JSON, nullable=True)
    errors          = Column(JSON, nullable=True)
    report          = Column(JSON, nullable=True)
    committed_at    = Column(String(40), nullable=True)
