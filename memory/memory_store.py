"""
MemoryStore — unified interface for all namespaced memory operations.
Wraps MemoryRepository. All layers use this, never the repo directly.

Namespaces:
  global          — system-wide settings and learnings
  agent:{id}      — per-agent performance and history
  routing         — model routing overrides from learning
  messaging       — best-performing message templates
  leads           — lead scoring patterns
  departments     — department-level KPIs
"""
import logging
from typing import Any, Optional

from services.storage.repositories.memory_repo import MemoryRepository

log = logging.getLogger(__name__)
_repo = MemoryRepository()


class MemoryStore:

    # ── Core ──────────────────────────────────────────────────────────────────
    @staticmethod
    def write(namespace: str, key: str, value: Any,
               updated_by: str = "system") -> None:
        try:
            _repo.write(namespace, key, value, updated_by)
        except Exception as e:
            log.error(f"MemoryStore.write failed [{namespace}:{key}]: {e}")

    @staticmethod
    def read(namespace: str, key: str,
              default: Any = None) -> Any:
        try:
            result = _repo.read(namespace, key)
            return result if result is not None else default
        except Exception as e:
            log.error(f"MemoryStore.read failed [{namespace}:{key}]: {e}")
            return default

    @staticmethod
    def list_namespace(namespace: str) -> dict:
        try:
            return _repo.list_namespace(namespace)
        except Exception as e:
            log.error(f"MemoryStore.list_namespace failed [{namespace}]: {e}")
            return {}

    @staticmethod
    def delete(namespace: str, key: str) -> bool:
        try:
            return _repo.delete(namespace, key)
        except Exception as e:
            log.error(f"MemoryStore.delete failed [{namespace}:{key}]: {e}")
            return False

    # ── Convenience: global namespace ────────────────────────────────────────
    @staticmethod
    def set_global(key: str, value: Any) -> None:
        MemoryStore.write("global", key, value)

    @staticmethod
    def get_global(key: str, default: Any = None) -> Any:
        return MemoryStore.read("global", key, default)

    # ── Convenience: agent namespace ─────────────────────────────────────────
    @staticmethod
    def set_agent(agent_id: str, key: str, value: Any) -> None:
        MemoryStore.write(f"agent:{agent_id}", key, value)

    @staticmethod
    def get_agent(agent_id: str, key: str, default: Any = None) -> Any:
        return MemoryStore.read(f"agent:{agent_id}", key, default)

    # ── Convenience: routing overrides ───────────────────────────────────────
    @staticmethod
    def get_routing_override(task_type: str) -> Optional[str]:
        """Returns model key if learning has overridden default routing."""
        overrides = MemoryStore.read("routing", "overrides", {})
        return overrides.get(task_type)

    @staticmethod
    def set_routing_override(task_type: str, model_key: str) -> None:
        overrides = MemoryStore.read("routing", "overrides", {})
        overrides[task_type] = model_key
        MemoryStore.write("routing", "overrides", overrides, updated_by="learning_engine")

    # ── Convenience: messaging templates ─────────────────────────────────────
    @staticmethod
    def get_best_template(template_type: str) -> Optional[str]:
        return MemoryStore.read("messaging", f"best_{template_type}")

    @staticmethod
    def set_best_template(template_type: str, template: str) -> None:
        MemoryStore.write("messaging", f"best_{template_type}", template,
                           updated_by="learning_engine")
