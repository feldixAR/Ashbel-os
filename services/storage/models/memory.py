"""
Memory model — namespaced key/value store with versioning.
"""
from sqlalchemy import Column, String, Text, Integer
from .base import Base, TimestampMixin, new_uuid


class MemoryModel(Base, TimestampMixin):
    __tablename__ = "memory"

    id         = Column(String(36),  primary_key=True, default=new_uuid)
    namespace  = Column(String(80),  nullable=False, index=True)
    key        = Column(String(200), nullable=False, index=True)
    value      = Column(Text,        nullable=True)
    version    = Column(Integer,     nullable=False, default=1)
    updated_by = Column(String(80),  nullable=True)

    def __repr__(self) -> str:
        return f"<Memory {self.namespace}:{self.key} v{self.version}>"
