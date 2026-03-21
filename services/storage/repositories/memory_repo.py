"""Memory repository — namespaced key/value with versioning."""
import json
from typing import Optional, Any, List
from services.storage.db import get_session
from services.storage.models.memory import MemoryModel
from .base_repo import utcnow_iso


class MemoryRepository:

    def write(self, namespace: str, key: str,
               value: Any, updated_by: str = "system") -> MemoryModel:
        from services.storage.models.base import new_uuid
        serialized = json.dumps(value, ensure_ascii=False)
        with get_session() as s:
            existing = (s.query(MemoryModel)
                        .filter_by(namespace=namespace, key=key)
                        .first())
            if existing:
                existing.value      = serialized
                existing.version    = (existing.version or 1) + 1
                existing.updated_by = updated_by
                return existing
            record = MemoryModel(
                id=new_uuid(), namespace=namespace, key=key,
                value=serialized, version=1, updated_by=updated_by,
            )
            s.add(record)
            return record

    def read(self, namespace: str, key: str) -> Optional[Any]:
        with get_session() as s:
            record = (s.query(MemoryModel)
                      .filter_by(namespace=namespace, key=key)
                      .first())
            if not record or record.value is None:
                return None
            return json.loads(record.value)

    def list_namespace(self, namespace: str) -> dict:
        with get_session() as s:
            records = (s.query(MemoryModel)
                       .filter_by(namespace=namespace)
                       .all())
            return {r.key: json.loads(r.value) for r in records if r.value}

    def delete(self, namespace: str, key: str) -> bool:
        with get_session() as s:
            record = (s.query(MemoryModel)
                      .filter_by(namespace=namespace, key=key)
                      .first())
            if record:
                s.delete(record)
                return True
        return False
