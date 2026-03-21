"""
Agent event handlers.

Triggered by: AGENT_CREATED, AGENT_FAILED, AGENT_VERSION_PROMOTED,
              AGENT_VERSION_ROLLED_BACK

Responsibilities:
  - Log agent lifecycle events
  - Track failure rates per agent for health monitoring
  - Update memory when version changes occur
  - Alert if agent failure rate exceeds threshold
"""

import logging
from memory.memory_store import MemoryStore

log = logging.getLogger(__name__)

FAILURE_ALERT_THRESHOLD = 3   # consecutive failures before alert


def on_agent_created(event_type: str, payload: dict, meta: dict) -> None:
    """
    A new agent was registered in the factory.
    Initialises per-agent memory namespace.
    """
    agent_id   = payload.get("agent_id")
    agent_name = payload.get("name", "unknown")
    department = payload.get("department", "unknown")
    version    = payload.get("version", 1)

    log.info(
        f"[AgentHandler] created: {agent_name} "
        f"(id={agent_id}, dept={department}, v={version})"
    )

    # Initialise agent memory namespace
    MemoryStore.set_agent(agent_id, "consecutive_failures", 0)
    MemoryStore.set_agent(agent_id, "total_tasks", 0)
    MemoryStore.set_agent(agent_id, "total_failures", 0)

    # Track total agents per department
    key = f"agent_count_{department}"
    current = MemoryStore.read("global", key, 0)
    MemoryStore.write("global", key, current + 1)


def on_agent_failed(event_type: str, payload: dict, meta: dict) -> None:
    """
    An agent task execution failed.
    Tracks consecutive failures and emits alert if threshold exceeded.
    """
    agent_id   = payload.get("agent_id")
    agent_name = payload.get("name", "unknown")
    error      = payload.get("error", "")
    task_id    = payload.get("task_id")

    log.warning(
        f"[AgentHandler] failure: {agent_name} "
        f"(id={agent_id}, task={task_id}) error={error[:120]}"
    )

    # Increment failure counters
    consecutive = MemoryStore.get_agent(agent_id, "consecutive_failures", 0)
    total       = MemoryStore.get_agent(agent_id, "total_failures", 0)
    consecutive += 1
    total       += 1
    MemoryStore.set_agent(agent_id, "consecutive_failures", consecutive)
    MemoryStore.set_agent(agent_id, "total_failures", total)

    if consecutive >= FAILURE_ALERT_THRESHOLD:
        log.error(
            f"[AgentHandler] ALERT: {agent_name} has failed {consecutive} "
            f"times consecutively — review required."
        )
        # Flag for dashboard alert
        alerts = MemoryStore.read("global", "unhealthy_agents", [])
        if agent_id not in alerts:
            alerts.append(agent_id)
            MemoryStore.write("global", "unhealthy_agents", alerts)


def on_agent_version_promoted(event_type: str, payload: dict, meta: dict) -> None:
    """
    A new agent version won the A/B test and was promoted to active.
    Resets failure counters for the agent.
    """
    agent_id   = payload.get("agent_id")
    agent_name = payload.get("name", "unknown")
    old_version = payload.get("old_version")
    new_version = payload.get("new_version")

    log.info(
        f"[AgentHandler] version promoted: {agent_name} "
        f"v{old_version} → v{new_version}"
    )

    # Reset health counters on promotion
    MemoryStore.set_agent(agent_id, "consecutive_failures", 0)

    # Record version history
    history = MemoryStore.get_agent(agent_id, "version_history", [])
    history.append({
        "from": old_version,
        "to":   new_version,
        "event": "promoted",
    })
    MemoryStore.set_agent(agent_id, "version_history", history)

    # Remove from unhealthy list if present
    alerts = MemoryStore.read("global", "unhealthy_agents", [])
    if agent_id in alerts:
        alerts.remove(agent_id)
        MemoryStore.write("global", "unhealthy_agents", alerts)


def on_agent_version_rolled_back(event_type: str, payload: dict, meta: dict) -> None:
    """
    An agent was manually rolled back to a previous version.
    """
    agent_id    = payload.get("agent_id")
    agent_name  = payload.get("name", "unknown")
    from_version = payload.get("from_version")
    to_version   = payload.get("to_version")
    reason       = payload.get("reason", "manual")

    log.warning(
        f"[AgentHandler] rollback: {agent_name} "
        f"v{from_version} → v{to_version} reason={reason}"
    )

    MemoryStore.set_agent(agent_id, "consecutive_failures", 0)

    history = MemoryStore.get_agent(agent_id, "version_history", [])
    history.append({
        "from":   from_version,
        "to":     to_version,
        "event":  "rolled_back",
        "reason": reason,
    })
    MemoryStore.set_agent(agent_id, "version_history", history)
