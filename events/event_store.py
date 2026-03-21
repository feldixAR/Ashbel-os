"""
EventStore — persists every published event to the database.
Acts as a wildcard subscriber on the EventBus.
Provides replay and audit query interface.

The EventStore is registered automatically when the application starts
(see the bootstrap in event_dispatcher.py).
"""

import logging
from typing import List, Optional

from services.storage.repositories.event_repo import EventRepository

log = logging.getLogger(__name__)

_repo = EventRepository()


class EventStore:
    """
    Persists events and provides read access to the event log.
    Registered as a wildcard handler on the EventBus — never call directly.
    """

    # ── Write (called by EventBus) ────────────────────────────────────────────

    def handle(self, event_type: str, payload: dict, meta: dict) -> None:
        """
        Wildcard handler signature: (event_type, payload, meta).
        Persists every event to the database.
        """
        try:
            _repo.append(
                event_type=event_type,
                payload=payload,
                source_agent_id=meta.get("source_agent_id"),
                source_task_id=meta.get("source_task_id"),
                trace_id=meta.get("trace_id"),
            )
        except Exception as e:
            # EventStore failure must never crash the bus
            log.error(f"[EventStore] failed to persist {event_type}: {e}", exc_info=True)

    # ── Read ──────────────────────────────────────────────────────────────────

    @staticmethod
    def get_by_type(event_type: str, limit: int = 100):
        return _repo.get_by_type(event_type, limit=limit)

    @staticmethod
    def get_recent(limit: int = 50):
        return _repo.get_recent(limit=limit)

    @staticmethod
    def get_by_trace(trace_id: str):
        return _repo.get_by_trace(trace_id)


# ── Singleton ─────────────────────────────────────────────────────────────────
event_store = EventStore()
