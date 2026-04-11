"""
EventDispatcher — wires the EventBus to all handlers and the EventStore.

Responsibilities:
  1. Import all handler modules
  2. Subscribe each handler function to its event types
  3. Subscribe EventStore as wildcard (persists everything)
  4. Provide bootstrap() called once at application startup

Rule: only this file knows about both the bus and the handlers.
      No other module imports handler functions directly.
"""

import logging

from events.event_bus   import event_bus, WILDCARD
from events.event_store import event_store
import events.event_types as ET

# ── Handler imports ───────────────────────────────────────────────────────────
from events.handlers.lead_handlers     import (
    on_lead_created,
    on_lead_scored,
    on_lead_responded,
    on_lead_status_changed,
)
from events.handlers.agent_handlers    import (
    on_agent_created,
    on_agent_failed,
    on_agent_version_promoted,
    on_agent_version_rolled_back,
)
from events.handlers.task_handlers     import (
    on_task_created,
    on_task_completed,
    on_task_failed,
    on_task_dead_lettered,
    on_task_approval_needed,
)
from events.handlers.learning_handlers import (
    on_pattern_detected,
    on_prompt_optimized,
    on_routing_map_updated,
)
from events.handlers.approval_handlers import (
    on_approval_requested,
    on_approval_granted,
    on_approval_denied,
)
from events.handlers.lead_acquisition_handlers import (
    on_lead_discovered,
    on_inbound_lead_received,
    on_lead_outreach_sent,
    on_lead_followup_proposed,
    on_website_analysis_requested,
)

log = logging.getLogger(__name__)

_bootstrapped = False


def bootstrap() -> None:
    """
    Register all handlers. Idempotent — safe to call multiple times.
    Must be called once before any events are published.
    """
    global _bootstrapped
    if _bootstrapped:
        return

    # ── EventStore: persist everything ────────────────────────────────────────
    event_bus.subscribe(WILDCARD, event_store.handle)

    # ── Lead events ───────────────────────────────────────────────────────────
    event_bus.subscribe(ET.LEAD_CREATED,        on_lead_created)
    event_bus.subscribe(ET.LEAD_SCORED,         on_lead_scored)
    event_bus.subscribe(ET.LEAD_RESPONDED,      on_lead_responded)
    event_bus.subscribe(ET.LEAD_STATUS_CHANGED, on_lead_status_changed)

    # ── Agent events ──────────────────────────────────────────────────────────
    event_bus.subscribe(ET.AGENT_CREATED,             on_agent_created)
    event_bus.subscribe(ET.AGENT_FAILED,              on_agent_failed)
    event_bus.subscribe(ET.AGENT_VERSION_PROMOTED,    on_agent_version_promoted)
    event_bus.subscribe(ET.AGENT_VERSION_ROLLED_BACK, on_agent_version_rolled_back)

    # ── Task events ───────────────────────────────────────────────────────────
    event_bus.subscribe(ET.TASK_CREATED,         on_task_created)
    event_bus.subscribe(ET.TASK_COMPLETED,       on_task_completed)
    event_bus.subscribe(ET.TASK_FAILED,          on_task_failed)
    event_bus.subscribe(ET.TASK_DEAD_LETTERED,   on_task_dead_lettered)
    event_bus.subscribe(ET.TASK_APPROVAL_NEEDED, on_task_approval_needed)

    # ── Learning events ───────────────────────────────────────────────────────
    event_bus.subscribe(ET.PATTERN_DETECTED,    on_pattern_detected)
    event_bus.subscribe(ET.PROMPT_OPTIMIZED,    on_prompt_optimized)
    event_bus.subscribe(ET.ROUTING_MAP_UPDATED, on_routing_map_updated)

    # ── Approval events ───────────────────────────────────────────────────────
    event_bus.subscribe(ET.APPROVAL_REQUESTED, on_approval_requested)
    event_bus.subscribe(ET.APPROVAL_GRANTED,   on_approval_granted)
    event_bus.subscribe(ET.APPROVAL_DENIED,    on_approval_denied)

    # ── Lead Acquisition events (Phase 12) ────────────────────────────────────
    event_bus.subscribe(ET.LEAD_DISCOVERED,            on_lead_discovered)
    event_bus.subscribe(ET.INBOUND_LEAD_RECEIVED,      on_inbound_lead_received)
    event_bus.subscribe(ET.LEAD_OUTREACH_SENT,         on_lead_outreach_sent)
    event_bus.subscribe(ET.LEAD_FOLLOWUP_PROPOSED,     on_lead_followup_proposed)
    event_bus.subscribe(ET.WEBSITE_ANALYSIS_REQUESTED, on_website_analysis_requested)

    # ── AgentRegistry bootstrap ───────────────────────────────────────────────
    try:
        from agents.base.agent_registry import agent_registry
        agent_registry.bootstrap()
    except Exception as e:
        log.error(f"[EventDispatcher] AgentRegistry bootstrap failed: {e}",
                  exc_info=True)

    _bootstrapped = True
    log.info(
        f"[EventDispatcher] bootstrapped — "
        f"{sum(len(v) for v in event_bus.registered_handlers().values())} subscriptions active"
    )
