"""
LeadQualifierAgent — scores leads using LEAD_SCORE_WEIGHTS.

Handles: task_type="scoring", action="score_lead"
"""

import logging
from services.storage.models.task            import TaskModel
from services.execution.executor             import ExecutionResult
from agents.base.base_agent                  import BaseAgent
from services.storage.repositories.lead_repo import LeadRepository
from events.event_bus                        import event_bus
import events.event_types                    as ET

log        = logging.getLogger(__name__)
_lead_repo = LeadRepository()


class LeadQualifierAgent(BaseAgent):
    agent_id   = "builtin_lead_qualifier_v1"
    name       = "Lead Qualifier"
    department = "sales"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return task_type == "scoring" and action == "score_lead"

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[LeadQualifier] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(success=False,
                                   message=f"שגיאה בדירוג: {e}",
                                   output={"error": str(e)})

    def _run(self, task: TaskModel) -> ExecutionResult:
        params  = self._input_params(task)
        lead_id = params.get("lead_id")
        if lead_id:
            return self._score_one(task, lead_id)
        return self._score_all(task)

    def _score_one(self, task: TaskModel, lead_id: str) -> ExecutionResult:
        lead = _lead_repo.get(lead_id)
        if not lead:
            return ExecutionResult(success=False,
                                   message=f"ליד {lead_id} לא נמצא",
                                   output={"error": "lead_not_found"})
        score = self._compute_score(lead)
        _lead_repo.update_score(lead_id, score)
        event_bus.publish(ET.LEAD_SCORED,
                          payload={"lead_id": lead_id, "name": lead.name,
                                   "score": score},
                          source_task_id=task.id, trace_id=task.trace_id)
        return ExecutionResult(success=True,
                               message=f"ליד {lead.name} קיבל ציון {score}",
                               output={"lead_id": lead_id, "name": lead.name,
                                       "score": score})

    def _score_all(self, task: TaskModel) -> ExecutionResult:
        leads = _lead_repo.list_all()
        if not leads:
            return ExecutionResult(success=True, message="אין לידים לדירוג",
                                   output={"scored": 0})
        scored = []
        for lead in leads:
            score = self._compute_score(lead)
            _lead_repo.update_score(lead.id, score)
            event_bus.publish(ET.LEAD_SCORED,
                              payload={"lead_id": lead.id, "name": lead.name,
                                       "score": score},
                              source_task_id=task.id, trace_id=task.trace_id)
            scored.append({"lead_id": lead.id, "name": lead.name, "score": score})
        top = sorted(scored, key=lambda x: x["score"], reverse=True)[:5]
        return ExecutionResult(success=True,
                               message=f"דורגו {len(scored)} לידים",
                               output={"scored": len(scored), "top_5": top})

    def _compute_score(self, lead) -> int:
        from engines.lead_engine import compute_score
        return compute_score(lead)
