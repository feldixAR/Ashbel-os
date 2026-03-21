"""
Executor — entry point for all task execution.

Stage 2: handles update_crm_status via direct handler.
Stage 3: AgentRegistry will be added here without breaking this.

Contract with TaskManager.dispatch():
    execute(task) -> ExecutionResult
    ExecutionResult has: success, message, output, model_used, cost_usd, duration_ms, to_dict()
"""

import logging
import datetime
from dataclasses import dataclass, field
from typing import Optional

from services.storage.models.task import TaskModel

log = logging.getLogger(__name__)


# ── ExecutionResult — DO NOT MODIFY ──────────────────────────────────────────

@dataclass
class ExecutionResult:
    success:     bool
    message:     str
    output:      dict          = field(default_factory=dict)
    model_used:  Optional[str] = None
    cost_usd:    float         = 0.0
    duration_ms: int           = 0

    def to_dict(self) -> dict:
        return {
            "success":     self.success,
            "message":     self.message,
            "output":      self.output,
            "model_used":  self.model_used,
            "cost_usd":    self.cost_usd,
            "duration_ms": self.duration_ms,
        }


# ── Handler: update_crm_status ────────────────────────────────────────────────

def _handle_update_crm_status(task: TaskModel) -> ExecutionResult:
    from services.storage.repositories.lead_repo import LeadRepository
    from events.event_bus                         import event_bus
    import events.event_types                     as ET

    started = _now_ms()
    params  = (task.input_data or {}).get("params", {})
    name    = (params.get("name")   or "").strip()
    city    = (params.get("city")   or "").strip()
    phone   = (params.get("phone")  or "").strip()
    source  = (params.get("source") or "manual").strip()
    notes   = (params.get("notes")  or "").strip()

    if not name:
        log.warning(f"[Executor] missing name task={task.id}")
        return ExecutionResult(
            success=False,
            message="שגיאה: שם הליד חסר.",
            output={"error": "missing_name", "received_params": params},
        )

    try:
        lead = LeadRepository().create(
            name=name, city=city, phone=phone, source=source, notes=notes)
    except Exception as e:
        log.error(f"[Executor] lead create failed task={task.id}: {e}", exc_info=True)
        return ExecutionResult(
            success=False,
            message=f"שגיאה ביצירת ליד: {e}",
            output={"error": str(e)},
        )

    event_bus.publish(
        ET.LEAD_CREATED,
        payload={"lead_id": lead.id, "name": lead.name,
                 "city": lead.city, "phone": lead.phone, "source": lead.source},
        source_task_id=task.id,
        trace_id=task.trace_id,
    )
    log.info(f"[Executor] lead created id={lead.id} name={lead.name}")
    return ExecutionResult(
        success=True,
        message=f"ליד נוצר בהצלחה: {lead.name}",
        output={"lead_id": lead.id, "name": lead.name, "city": lead.city,
                "phone": lead.phone, "source": lead.source, "status": lead.status},
        duration_ms=_elapsed_ms(started),
    )


# ── Handler registry ──────────────────────────────────────────────────────────

_HANDLERS: dict[str, callable] = {
    "update_crm_status": _handle_update_crm_status,
}


# ── Main entry point ──────────────────────────────────────────────────────────

def execute(task: TaskModel) -> ExecutionResult:
    """
    Routing priority:
        1. AgentRegistry  — agent-based (Stage 3+)
        2. _HANDLERS dict — direct handlers (Stage 2 fallback)
        3. Unhandled      — return ExecutionResult(success=False)
    """
    action    = task.action
    task_type = task.type

    # 1. AgentRegistry
    try:
        from agents.base.agent_registry import agent_registry
        agent = agent_registry.find(task_type, action)
        if agent is not None:
            log.debug(f"[Executor] ({task_type},{action}) → {agent.name!r}")
            return agent.execute(task)
    except Exception as e:
        log.error(f"[Executor] registry error: {e}", exc_info=True)

    # 2. Direct handlers
    handler = _HANDLERS.get(action)
    if handler:
        try:
            return handler(task)
        except Exception as e:
            log.error(f"[Executor] handler crashed action={action}: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                message=f"שגיאה בביצוע '{action}': {e}",
                output={"error": str(e)},
            )

    # 3. Unhandled
    log.warning(f"[Executor] no handler for ({task_type},{action}) task={task.id}")
    return ExecutionResult(
        success=False,
        message=f"אין handler לפעולה '{action}'",
        output={"error": "unhandled_action", "action": action, "task_type": task_type},
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(datetime.datetime.utcnow().timestamp() * 1000)

def _elapsed_ms(started: int) -> int:
    return _now_ms() - started
