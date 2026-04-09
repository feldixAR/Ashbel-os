"""
Base repository with common CRUD helpers.
All repositories inherit from this.
"""
import datetime
from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy.orm import Session
from services.storage.db import get_session

T = TypeVar("T")


def utcnow_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class BaseRepository(Generic[T]):
    model_class: Type[T]

    def get(self, record_id: str) -> Optional[T]:
        with get_session() as s:
            return s.get(self.model_class, record_id)

    def list_all(self) -> List[T]:
        with get_session() as s:
            return s.query(self.model_class).all()

    def save(self, record: T) -> T:
        with get_session() as s:
            s.merge(record)
        return record

    def delete(self, record_id: str) -> bool:
        with get_session() as s:
            obj = s.get(self.model_class, record_id)
            if obj:
                s.delete(obj)
                return True
        return False
