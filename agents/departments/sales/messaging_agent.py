"""
MessagingAgent — generates outreach messages for leads.

Handles: task_type="sales", action="generate_content"
Stage 3: deterministic template. Stage 4: AI-generated via model_router.
"""

import logging
from services.storage.models.task  import TaskModel
from services.execution.executor   import ExecutionResult
from agents.base.base_agent        import BaseAgent
from events.event_bus              import event_bus
import events.event_types          as ET

log = logging.getLogger(__name__)


class MessagingAgent(BaseAgent):
    agent_id   = "builtin_messaging_agent_v1"
    name       = "Messaging Agent"
    department = "sales"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return task_type == "sales" and action == "generate_content"

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[MessagingAgent] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(success=False,
                                   message=f"שגיאה ביצירת הודעה: {e}",
                                   output={"error": str(e)})

    def _run(self, task: TaskModel) -> ExecutionResult:
        params   = self._input_params(task)
        name     = self._safe_str(params.get("name"),  "לקוח")
        city     = self._safe_str(params.get("city"),  "")
        notes    = self._safe_str(params.get("notes"), "")
        attempts = int(params.get("attempts", 0))
        lead_id  = params.get("lead_id", "")

        from engines.messaging_engine import build_message
        msg_type = "cold" if attempts == 0 else "followup"
        message  = build_message(name, city, notes, attempts)

        event_bus.publish(
            ET.MESSAGE_GENERATED,
            payload={"lead_id": lead_id, "name": name,
                     "message": message, "message_type": msg_type},
            source_task_id=task.id, trace_id=task.trace_id,
        )
        return ExecutionResult(
            success=True,
            message=f"הודעה נוצרה עבור {name}",
            output={"lead_name": name, "message": message, "message_type": msg_type},
        )
