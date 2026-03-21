"""
GenericTaskAgent — fallback for any unhandled task type/action.
Set as registry._fallback. Always returns a valid ExecutionResult.
"""

import logging
from services.storage.models.task  import TaskModel
from services.execution.executor   import ExecutionResult
from agents.base.base_agent        import BaseAgent

log = logging.getLogger(__name__)


class GenericTaskAgent(BaseAgent):
    agent_id   = "builtin_generic_agent_v1"
    name       = "Generic Task Agent"
    department = "operations"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return True  # used as fallback only — always matches

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[GenericAgent] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(success=False,
                                   message=f"שגיאה כללית: {e}",
                                   output={"error": str(e)})

    def _run(self, task: TaskModel) -> ExecutionResult:
        action    = task.action
        task_type = task.type
        params    = self._input_params(task)
        log.info(f"[GenericAgent] ({task_type},{action}) task={task.id}")

        if action == "read_data":
            return self._handle_read(task_type)

        return ExecutionResult(
            success=True,
            message=f"פעולה '{action}' התקבלה",
            output={"task_type": task_type, "action": action, "params": params,
                    "note": "handler ייעודי יתווסף בשלבים הבאים"},
        )

    def _handle_read(self, task_type: str) -> ExecutionResult:
        if task_type == "crm":
            from services.storage.repositories.lead_repo  import LeadRepository
            from services.storage.repositories.agent_repo import AgentRepository
            leads  = LeadRepository().list_all()
            agents = AgentRepository().get_active()
            return ExecutionResult(
                success=True,
                message=f"{len(leads)} לידים, {len(agents)} סוכנים",
                output={
                    "leads":  [{"id": l.id, "name": l.name,
                                "status": l.status, "score": l.score}
                               for l in leads],
                    "agents": [{"id": a.id, "name": a.name,
                                "department": a.department}
                               for a in agents],
                },
            )
        return ExecutionResult(success=True, message="נתונים נקראו",
                               output={"task_type": task_type})
