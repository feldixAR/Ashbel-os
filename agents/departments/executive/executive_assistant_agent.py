"""
ExecutiveAssistantAgent — personal operating assistant for the system.

Handles:
    (assistant, plan_action)
    (assistant, draft_message)
    (assistant, draft_meeting)
    (assistant, update_dashboard)

Stage 1:
- understands high-level assistant tasks
- returns structured draft/action payloads
- does NOT call external systems yet
"""

import logging

from services.storage.models.task import TaskModel
from services.execution.executor import ExecutionResult
from agents.base.base_agent import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("assistant", "plan_action"),
    ("assistant", "draft_message"),
    ("assistant", "draft_meeting"),
    ("assistant", "update_dashboard"),
}


class ExecutiveAssistantAgent(BaseAgent):
    agent_id = "builtin_executive_assistant_agent_v1"
    name = "Executive Assistant Agent"
    department = "executive"
    version = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[ExecutiveAssistantAgent] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                message=f"שגיאה בסוכן העוזר האישי: {e}",
                output={"error": str(e)},
            )

    def _run(self, task: TaskModel) -> ExecutionResult:
        command = self._safe_str((task.input_data or {}).get("command"))
        params = self._input_params(task)

        if task.action == "draft_message":
            return self._draft_message(command, params)

        if task.action == "draft_meeting":
            return self._draft_meeting(command, params)

        if task.action == "update_dashboard":
            return self._update_dashboard(command, params)

        return self._plan_action(command, params)

    def _plan_action(self, command: str, params: dict) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            message="העוזר האישי ניתח את הבקשה",
            output={
                "agent": self.name,
                "status": "planned",
                "task_type": "assistant",
                "action": "plan_action",
                "command": command,
                "suggested_next_steps": [
                    "classify_request",
                    "prepare_draft",
                    "ask_for_approval_if_needed",
                ],
                "needs_approval": True,
            },
        )

    def _draft_message(self, command: str, params: dict) -> ExecutionResult:
        contact_name = (
            params.get("contact_name")
            or params.get("name")
            or "איש קשר"
        )
        message_text = params.get("message") or f"היי {contact_name}, רציתי לעדכן אותך לגבי הנושא שדיברנו עליו."

        return ExecutionResult(
            success=True,
            message="טיוטת הודעה הוכנה",
            output={
                "agent": self.name,
                "status": "draft_ready",
                "channel": "whatsapp",
                "contact_name": contact_name,
                "draft_message": message_text,
                "needs_approval": True,
                "next_step": "open_whatsapp_draft",
                "command": command,
            },
        )

    def _draft_meeting(self, command: str, params: dict) -> ExecutionResult:
        contact_name = (
            params.get("contact_name")
            or params.get("name")
            or "איש קשר"
        )
        date = params.get("date") or "לקביעה"
        time = params.get("time") or "לקביעה"

        return ExecutionResult(
            success=True,
            message="טיוטת פגישה הוכנה",
            output={
                "agent": self.name,
                "status": "draft_ready",
                "channel": "calendar",
                "contact_name": contact_name,
                "meeting_title": f"פגישה עם {contact_name}",
                "meeting_date": date,
                "meeting_time": time,
                "needs_approval": True,
                "next_step": "create_calendar_draft",
                "command": command,
            },
        )

    def _update_dashboard(self, command: str, params: dict) -> ExecutionResult:
        widget = params.get("widget") or "לידים חמים"

        return ExecutionResult(
            success=True,
            message="בקשת עדכון למסך הבית הוכנה",
            output={
                "agent": self.name,
                "status": "dashboard_update_planned",
                "widget": widget,
                "needs_approval": True,
                "next_step": "apply_dashboard_update",
                "command": command,
            },
        )
