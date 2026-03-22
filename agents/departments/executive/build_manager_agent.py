"""
BuildManagerAgent — manages system build requests.

Handles:
    (agent_build, create_agent)

Stage 1:
- accepts build request
- returns structured build spec
- does NOT write code yet
"""

import logging

from services.storage.models.task import TaskModel
from services.execution.executor import ExecutionResult
from agents.base.base_agent import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("agent_build", "create_agent"),
}


class BuildManagerAgent(BaseAgent):
    agent_id = "builtin_build_manager_agent_v1"
    name = "Build Manager Agent"
    department = "executive"
    version = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[BuildManagerAgent] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                message=f"שגיאה בבניית מפרט פיתוח: {e}",
                output={"error": str(e)},
            )

    def _run(self, task: TaskModel) -> ExecutionResult:
        params = self._input_params(task)
        command = (task.input_data or {}).get("command", "").strip()

        requested_agent = (
            params.get("agent_name")
            or params.get("name")
            or "Executive Assistant Agent"
        )

        build_spec = {
            "requested_agent": requested_agent,
            "goal": command or "יצירת סוכן חדש במערכת",
            "stage": "build_spec_only",
            "status": "planned",
            "next_step": "create_agent_code_and_register",
            "files_to_create": [
                f"agents/departments/executive/{self._slugify(requested_agent)}.py"
            ],
            "files_to_update": [
                "agents/base/agent_registry.py",
                "orchestration/orchestrator.py",
            ],
            "required_capabilities": [
                "intent_understanding",
                "action_planning",
                "draft_generation",
                "approval_flow",
            ],
            "done_criteria": [
                "agent file exists",
                "agent registered in registry bootstrap",
                "orchestrator routes relevant requests",
                "agent returns structured response",
            ],
        }

        return ExecutionResult(
            success=True,
            message=f"נוצר מפרט בנייה עבור {requested_agent}",
            output=build_spec,
        )

    def _slugify(self, text: str) -> str:
        clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in text)
        while "__" in clean:
            clean = clean.replace("__", "_")
        return clean.strip("_") or "new_agent"
