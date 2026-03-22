"""
CodeBuilderAgent — builds agent code from build specs.

Handles:
    (agent_build, build_agent_code)

Stage 1:
- accepts build spec
- returns ready-to-create file payloads
- does NOT write files automatically yet
"""

import logging

from services.storage.models.task import TaskModel
from services.execution.executor import ExecutionResult
from agents.base.base_agent import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("agent_build", "build_agent_code"),
}


class CodeBuilderAgent(BaseAgent):
    agent_id = "builtin_code_builder_agent_v1"
    name = "Code Builder Agent"
    department = "executive"
    version = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[CodeBuilderAgent] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                message=f"שגיאה בבניית קוד: {e}",
                output={"error": str(e)},
            )

    def _run(self, task: TaskModel) -> ExecutionResult:
        params = self._input_params(task)
        command = (task.input_data or {}).get("command", "").strip()

        agent_name = (
            params.get("agent_name")
            or params.get("requested_agent")
            or "ExecutiveAssistantAgent"
        )

        class_name = self._class_name(agent_name)
        file_name = self._file_name(agent_name)

        file_path = f"agents/departments/executive/{file_name}.py"

        code = f'''import logging

from services.storage.models.task import TaskModel
from services.execution.executor import ExecutionResult
from agents.base.base_agent import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {{
    ("assistant", "plan_action"),
    ("assistant", "draft_message"),
    ("assistant", "draft_meeting"),
    ("assistant", "update_dashboard"),
}}


class {class_name}(BaseAgent):
    agent_id = "builtin_{self._slug(agent_name)}_v1"
    name = "{agent_name}"
    department = "executive"
    version = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[{class_name}] error task={{task.id}}: {{e}}", exc_info=True)
            return ExecutionResult(
                success=False,
                message=f"שגיאה בסוכן {agent_name}: {{e}}",
                output={{"error": str(e)}},
            )

    def _run(self, task: TaskModel) -> ExecutionResult:
        command = (task.input_data or {{}}).get("command", "").strip()
        return ExecutionResult(
            success=True,
            message="{agent_name} קיבל את הבקשה",
            output={{
                "agent": "{agent_name}",
                "task_type": task.type,
                "action": task.action,
                "command": command,
                "status": "received",
                "next_step": "connect_real_handlers"
            }},
        )
'''

        return ExecutionResult(
            success=True,
            message=f"קוד סוכן מוכן עבור {agent_name}",
            output={
                "requested_agent": agent_name,
                "goal": command or "בניית קוד לסוכן חדש",
                "status": "code_ready",
                "next_step": "create_file_and_register_agent",
                "files": [
                    {
                        "path": file_path,
                        "content": code,
                    }
                ],
                "register_in": "agents/base/agent_registry.py",
            },
        )

    def _slug(self, text: str) -> str:
        clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in text)
        while "__" in clean:
            clean = clean.replace("__", "_")
        return clean.strip("_") or "new_agent"

    def _file_name(self, text: str) -> str:
        return self._slug(text)

    def _class_name(self, text: str) -> str:
        raw = "".join(ch if ch.isalnum() else " " for ch in text)
        parts = [p for p in raw.split() if p]
        if not parts:
            return "NewAgent"
        return "".join(p[:1].upper() + p[1:] for p in parts)
