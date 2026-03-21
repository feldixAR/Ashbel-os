"""
EventBus — in-process pub/sub engine.

Design:
  - Handlers register per event_type (or wildcard "*")
  - publish() is synchronous by default; async workers build on top
  - Thread-safe: uses a lock for handler registration
  - Upgradeable: swap _dispatch() for Redis/RabbitMQ without changing callers

Usage:
    from events.event_bus import event_bus
    from events.event_types import LEAD_CREATED

    # Register
    event_bus.subscribe(LEAD_CREATED, my_handler_fn)

    # Publish
    event_bus.publish(LEAD_CREATED, payload={"lead_id": "..."}, trace_id="...")
"""

import logging
import threading
from typing import Callable, Dict, List, Any, Optional

log = logging.getLogger(__name__)

# Handler signature: fn(event_type: str, payload: dict, meta: dict) -> None
HandlerFn = Callable[[str, dict, dict], None]

WILDCARD = "*"


class EventBus:

    def __init__(self):
        self._handlers: Dict[str, List[HandlerFn]] = {}
        self._lock = threading.Lock()

    # ── Registration ──────────────────────────────────────────────────────────

    def subscribe(self, event_type: str, handler: HandlerFn) -> None:
        """
        Register a handler for an event type.
        Use WILDCARD "*" to receive all events.
        Safe to call from any thread.
        """
        with self._lock:
            self._handlers.setdefault(event_type, [])
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)
                log.debug(f"[EventBus] subscribed {handler.__name__} → {event_type}")

    def unsubscribe(self, event_type: str, handler: HandlerFn) -> None:
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)
                log.debug(f"[EventBus] unsubscribed {handler.__name__} ← {event_type}")

    def clear(self, event_type: Optional[str] = None) -> None:
        """Remove all handlers. Primarily for test teardown."""
        with self._lock:
            if event_type:
                self._handlers.pop(event_type, None)
            else:
                self._handlers.clear()

    # ── Publishing ────────────────────────────────────────────────────────────

    def publish(
        self,
        event_type: str,
        payload:        dict  = None,
        source_agent_id: str  = None,
        source_task_id:  str  = None,
        trace_id:        str  = None,
    ) -> None:
        """
        Publish an event synchronously.
        All registered handlers for the event_type (and wildcard) are called.
        A handler failure is logged but never propagates to the caller.
        """
        payload = payload or {}
        meta = {
            "source_agent_id": source_agent_id,
            "source_task_id":  source_task_id,
            "trace_id":        trace_id,
        }

        # Collect handlers under lock, then execute outside lock
        with self._lock:
            specific  = list(self._handlers.get(event_type, []))
            wildcards = list(self._handlers.get(WILDCARD, []))

        all_handlers = specific + [h for h in wildcards if h not in specific]

        if not all_handlers:
            log.debug(f"[EventBus] no handlers for {event_type}")
            return

        log.debug(f"[EventBus] publishing {event_type} → {len(all_handlers)} handler(s)")

        for handler in all_handlers:
            self._call_handler(handler, event_type, payload, meta)

    def _call_handler(
        self,
        handler:    HandlerFn,
        event_type: str,
        payload:    dict,
        meta:       dict,
    ) -> None:
        try:
            handler(event_type, payload, meta)
        except Exception as e:
            log.error(
                f"[EventBus] handler {handler.__name__} raised on {event_type}: {e}",
                exc_info=True,
            )

    # ── Introspection ─────────────────────────────────────────────────────────

    def registered_handlers(self) -> Dict[str, List[str]]:
        with self._lock:
            return {
                etype: [h.__name__ for h in handlers]
                for etype, handlers in self._handlers.items()
            }

    def handler_count(self, event_type: str) -> int:
        with self._lock:
            return len(self._handlers.get(event_type, []))


# ── Singleton ─────────────────────────────────────────────────────────────────
event_bus = EventBus()
