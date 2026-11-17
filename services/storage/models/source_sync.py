"""Append-operation journal and workbook lease, never a second CRM."""
from sqlalchemy import Column, String, Text, JSON, UniqueConstraint
from .base import Base, TimestampMixin, new_uuid


class SourceSyncOperation(Base, TimestampMixin):
    __tablename__ = "source_sync_operations"
    __table_args__ = (UniqueConstraint("business_id", "preview_hash", name="uq_source_sync_preview"),)
    id = Column(String(36), primary_key=True, default=new_uuid)
    business_id = Column(String(80), nullable=False, index=True)
    spreadsheet_id = Column(String(150), nullable=False)
    preview_hash = Column(String(64), nullable=False)
    snapshot_hash = Column(String(64), nullable=False)
    candidate = Column(JSON, nullable=False)
    expected_row = Column(JSON, nullable=False)
    status = Column(String(40), nullable=False, default="prepared", index=True)
    expires_at = Column(String(40), nullable=False)
    claim_token = Column(String(36), nullable=True)
    result = Column(JSON, nullable=True)
    error_code = Column(String(100), nullable=True)


class SourceSyncLease(Base):
    __tablename__ = "source_sync_leases"
    business_id = Column(String(80), primary_key=True)
    spreadsheet_id = Column(String(150), primary_key=True)
    operation_id = Column(String(36), nullable=True)
    token = Column(String(36), nullable=True)
    expires_at = Column(String(40), nullable=True)
