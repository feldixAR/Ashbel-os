"""
SQLAlchemy declarative base + shared mixins.
"""
import uuid
import datetime
from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Adds created_at and updated_at to any model."""
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=True,
    )


def new_uuid() -> str:
    return str(uuid.uuid4())
