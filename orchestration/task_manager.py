"""
TaskManager — skeleton for Stage 1.

Manages the full task lifecycle:
  created → queued → routing → assigned → running → done | failed

Integrates with:
  - TaskRepository    (persistence)
  - EventBus          (publish lifecycle events)
  - ApprovalGate      (risk check — implemented in Stage 5)
  - RetryPolicy       (backoff + DLQ — implemented in Stage 5)
  - ModelRouter       (model selection — implemented in Stage 3)

In Stage 1: create, queue, transition, and publish events are fully wired.
            Execution dispatch is stubbed — filled in Stage 5 (Orchestration).
"""

import logging
import uuid
import datetime
from typing import Optional, Any

from services.storage.repositories.task_repo import TaskRepository
from services.storage.models.task import TaskModel
from events.event_bus import event_bus
import events.event_types as ET
from config.risk_policy import get_risk, requires_approval
from config.settings import AUTO_APPROVE_BELOW_RISK

log = logging.getLogger(__name__)

_task_repo = TaskRepository()


class TaskManager:

    # ── Task creation ─────────────────────────────────────────────────────────

    def create_task(
        self,
        type:           str,
        action:         str,
        input_data:     dict,
        priority:       int  = 5,
        agent_id:       str  = None,
        parent_task_id: str  = None,
        trace_id:       str  = None,
        max_retries:    int  = 3,
    ) -> TaskModel:
        """
        Create and persist a task, then publish TASK_CREATED.
        Risk level is derived from the action using the risk policy.
        """
        risk_level = int(get_risk(action))

        task = _task_repo.create(
            type=type,
            action=action,
            input_data=input_data,
            priority=priority,
            risk_level=risk_level,
            agent_id=agent_id,
            parent_task_id=parent_task_id,
            trace_id=trace_id,
            max_retries=max_retries,
        )

        event_bus.publish(
            ET.TASK_CREATED,
            payload={
                "task_id":  task.id,
                "type":     type,
                "action":   action,
                "priority": priority,
                "risk":     risk_level,
            },
            source_task_id=task.id,
            trace_id=trace_id,
        )

        log.info(
            f"[TaskManager] created task={task.id} "
            f"type={type} action={action} risk={risk_level}"
        )
        return task

    # ── Approval gate ─────────────────────────────────────────────────────────

    def check_approval(self, task: TaskModel) -> bool:
        """
        Returns True if the task can proceed without human approval.
        Returns False if it must be held for approval.
        Publishes TASK_APPROVAL_NEEDED when gated.
        """
        if not requires_approval(task.action, AUTO_APPROVE_BELOW_RISK):
            return True     # auto-approved

        # Gate the task
        self.transition(task.id, "approval_pending")

        event_bus.publish(
            ET.TASK_APPROVAL_NEEDED,
            payload={
                "task_id":    task.id,
                "action":     task.action,
                "details":    task.input_data or {},
                "risk_level": task.risk_level,
            },
            source_task_id=task.id,
            trace_id=task.trace_id,
        )

        log.info(
            f"[TaskManager] approval required: task={task.id} "
            f"action={task.action} risk={task.risk_level}"
        )
        return False

    # ── Lifecycle transitions ─────────────────────────────────────────────────

    def transition(self, task_id: str, new_status: str, **kwargs) -> None:
        """Moves a task to a new status and persists."""
        _task_repo.transition(task_id, new_status, **kwargs)
        log.debug(f"[TaskManager] transition task={task_id} → {new_status}")

    def mark_started(self, task_id: str, agent_id: str,
                      model_used: str = None) -> None:
        self.transition(
            task_id, "running",
            agent_id=agent_id,
            model_used=model_used,
            started_at=_now(),
        )
        event_bus.publish(
            ET.TASK_STARTED,
            payload={"task_id": task_id, "agent_id": agent_id},
            source_task_id=task_id,
        )

    def mark_completed(
        self,
        task_id:     str,
        output_data: dict,
        agent_id:    str   = None,
        model_used:  str   = None,
        tokens_in:   int   = 0,
        tokens_out:  int   = 0,
        cost_usd:    float = 0.0,
        duration_ms: int   = 0,
        trace_id:    str   = None,
    ) -> None:
        self.transition(
            task_id, "done",
            output_data=output_data,
            model_used=model_used,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            completed_at=_now(),
        )
        event_bus.publish(
            ET.TASK_COMPLETED,
            payload={
                "task_id":     task_id,
                "agent_id":    agent_id,
                "model_used":  model_used,
                "duration_ms": duration_ms,
                "cost_usd":    cost_usd,
            },
            source_task_id=task_id,
            trace_id=trace_id,
        )
        log.info(
            f"[TaskManager] completed task={task_id} "
            f"model={model_used} cost=${cost_usd:.4f}"
        )

    def mark_failed(
        self,
        task_id:  str,
        error:    str,
        trace_id: str = None,
    ) -> int:
        """
        Marks task as failed, increments retry counter.
        Returns new retry_count so caller can decide DLQ or retry.
        """
        new_count = _task_repo.mark_retry(task_id, error)

        task = _task_repo.get(task_id)
        max_retries = task.max_retries if task else 3

        event_bus.publish(
            ET.TASK_FAILED,
            payload={
                "task_id":     task_id,
                "error":       error,
                "retry_count": new_count,
                "type":        task.type if task else "unknown",
            },
            source_task_id=task_id,
            trace_id=trace_id,
        )

        if new_count >= max_retries:
            self._dead_letter(task, error, new_count, trace_id)

        return new_count

    def _dead_letter(
        self,
        task:     Optional[TaskModel],
        error:    str,
        attempts: int,
        trace_id: str = None,
    ) -> None:
        if not task:
            return
        self.transition(task.id, "dead_lettered")
        event_bus.publish(
            ET.TASK_DEAD_LETTERED,
            payload={
                "task_id":        task.id,
                "action":         task.action,
                "input_data":     task.input_data or {},
                "failure_reason": error,
                "attempts_made":  attempts,
            },
            source_task_id=task.id,
            trace_id=trace_id,
        )
        log.error(
            f"[TaskManager] DEAD LETTERED task={task.id} "
            f"action={task.action} attempts={attempts}"
        )

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_pending(self, limit: int = 50):
        return _task_repo.get_pending(limit=limit)

    def get_by_status(self, status: str):
        return _task_repo.get_by_status(status)

    def get(self, task_id: str) -> Optional[TaskModel]:
        return _task_repo.get(task_id)

    # ── Execution dispatch (stub — implemented in Stage 5) ───────────────────

    def dispatch(self, task: TaskModel) -> dict:
        """
        Executes task via executor and closes lifecycle (success / failure).
        """
        from services.execution.executor import execute
        self.mark_started(task.id, agent_id="executor")
        result = execute(task)
        if result.success:
            self.mark_completed(
                task_id=task.id,
                output_data=result.output,
                agent_id="executor",
                model_used=result.model_used,
                cost_usd=result.cost_usd,
                duration_ms=result.duration_ms,
                trace_id=task.trace_id,
            )
        else:
            error_msg = result.output.get("error") or result.message
            self.mark_failed(task_id=task.id, error=error_msg,
                              trace_id=task.trace_id)
        return result.to_dict()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ── Singleton ─────────────────────────────────────────────────────────────────
task_manager = TaskManager()
