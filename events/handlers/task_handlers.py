"""
Task event handlers.

Triggered by: TASK_CREATED, TASK_COMPLETED, TASK_FAILED,
              TASK_DEAD_LETTERED, TASK_APPROVAL_NEEDED

Responsibilities:
  - Track task throughput and failure rates in memory
  - Push dead-lettered tasks to DLQ repository
  - Record model cost per completed task
  - Log approval requests for dashboard visibility
"""

import logging
from memory.memory_store import MemoryStore
from services.storage.repositories.dlq_repo import DLQRepository
from services.storage.repositories.approval_repo import ApprovalRepository

log = logging.getLogger(__name__)

_dlq_repo      = DLQRepository()
_approval_repo = ApprovalRepository()


def on_task_created(event_type: str, payload: dict, meta: dict) -> None:
    """
    A new task entered the system.
    Increments throughput counters.
    """
    task_type = payload.get("type", "unknown")
    task_id   = payload.get("task_id")

    log.debug(f"[TaskHandler] created: task={task_id} type={task_type}")

    key = f"tasks_created_{task_type}"
    current = MemoryStore.read("global", key, 0)
    MemoryStore.write("global", key, current + 1)


def on_task_completed(event_type: str, payload: dict, meta: dict) -> None:
    """
    A task completed successfully.
    Records duration, cost, and model usage to memory.
    """
    task_id     = payload.get("task_id")
    task_type   = payload.get("type", "unknown")
    agent_id    = payload.get("agent_id")
    model_used  = payload.get("model_used")
    duration_ms = payload.get("duration_ms", 0)
    cost_usd    = payload.get("cost_usd", 0.0)

    log.info(
        f"[TaskHandler] completed: task={task_id} type={task_type} "
        f"agent={agent_id} model={model_used} "
        f"duration={duration_ms}ms cost=${cost_usd:.4f}"
    )

    # Aggregate completed task count per type
    key = f"tasks_done_{task_type}"
    current = MemoryStore.read("global", key, 0)
    MemoryStore.write("global", key, current + 1)

    # Accumulate total cost
    total_cost = MemoryStore.read("global", "total_cost_usd", 0.0)
    MemoryStore.write("global", "total_cost_usd", total_cost + (cost_usd or 0.0))

    # Track cost per model
    if model_used:
        model_cost_key = f"cost_{model_used}"
        m_cost = MemoryStore.read("global", model_cost_key, 0.0)
        MemoryStore.write("global", model_cost_key, m_cost + (cost_usd or 0.0))

    # Reset agent consecutive failures on success
    if agent_id:
        MemoryStore.set_agent(agent_id, "consecutive_failures", 0)
        agent_total = MemoryStore.get_agent(agent_id, "total_tasks", 0)
        MemoryStore.set_agent(agent_id, "total_tasks", agent_total + 1)


def on_task_failed(event_type: str, payload: dict, meta: dict) -> None:
    """
    A task failed (but may still be retried).
    Increments failure counters. Does NOT push to DLQ — that is
    on_task_dead_lettered's responsibility.
    """
    task_id   = payload.get("task_id")
    task_type = payload.get("type", "unknown")
    error     = payload.get("error", "")
    retry     = payload.get("retry_count", 0)

    log.warning(
        f"[TaskHandler] failed: task={task_id} type={task_type} "
        f"retry={retry} error={error[:100]}"
    )

    key = f"tasks_failed_{task_type}"
    current = MemoryStore.read("global", key, 0)
    MemoryStore.write("global", key, current + 1)


def on_task_dead_lettered(event_type: str, payload: dict, meta: dict) -> None:
    """
    A task exhausted all retries and was dead-lettered.
    Persists to DLQ and flags for operator attention.
    """
    task_id      = payload.get("task_id")
    action       = payload.get("action", "unknown")
    task_payload = payload.get("input_data", {})
    reason       = payload.get("failure_reason", "max retries exceeded")
    attempts     = payload.get("attempts_made", 0)

    log.error(
        f"[TaskHandler] DEAD LETTERED: task={task_id} action={action} "
        f"attempts={attempts} reason={reason}"
    )

    # Persist to DLQ
    try:
        _dlq_repo.push(
            original_task_id=task_id,
            action=action,
            payload=task_payload,
            failure_reason=reason,
            attempts_made=attempts,
        )
    except Exception as e:
        log.error(f"[TaskHandler] failed to push to DLQ: {e}")

    # Increment DLQ counter
    dlq_count = MemoryStore.read("global", "dlq_total", 0)
    MemoryStore.write("global", "dlq_total", dlq_count + 1)


def on_task_approval_needed(event_type: str, payload: dict, meta: dict) -> None:
    """
    A task requires human approval before execution.
    Creates an approval record and logs for dashboard visibility.
    """
    task_id    = payload.get("task_id")
    action     = payload.get("action", "unknown")
    details    = payload.get("details", {})
    risk_level = payload.get("risk_level", 3)

    log.info(
        f"[TaskHandler] approval needed: task={task_id} "
        f"action={action} risk={risk_level}"
    )

    try:
        approval = _approval_repo.create(
            action=action,
            details=details,
            risk_level=risk_level,
            task_id=task_id,
            requested_by="system",
        )
        log.info(f"[TaskHandler] approval record created: {approval.id}")
    except Exception as e:
        log.error(f"[TaskHandler] failed to create approval record: {e}")

    # Increment pending approvals count in memory (for quick dashboard reads)
    pending = MemoryStore.read("global", "pending_approvals_count", 0)
    MemoryStore.write("global", "pending_approvals_count", pending + 1)
