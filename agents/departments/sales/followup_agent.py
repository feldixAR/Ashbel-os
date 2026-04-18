"""
FollowUpAgent — Autonomous follow-up scheduling and queue management.

Handles:
    (followup, schedule_followup)
    (followup, followup_queue)
    (outreach, followup_queue)
    (followup, batch_followup)
"""

import logging
from services.storage.models.task import TaskModel
from services.execution.executor  import ExecutionResult
from agents.base.base_agent       import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("followup", "schedule_followup"),
    ("followup", "followup_queue"),
    ("outreach", "followup_queue"),
    ("followup", "batch_followup"),
}


class FollowUpAgent(BaseAgent):
    agent_id   = "builtin_followup_agent_v1"
    name       = "Follow-Up Agent"
    department = "sales"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[FollowUpAgent] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(success=False, message=f"שגיאה: {e}",
                                   output={"error": str(e)})

    def _run(self, task: TaskModel) -> ExecutionResult:
        if task.action == "followup_queue":
            return self._followup_queue(task)
        if task.action == "schedule_followup":
            return self._schedule_followup(task)
        if task.action == "batch_followup":
            return self._batch_followup(task)
        return self._followup_queue(task)

    def _followup_queue(self, task: TaskModel) -> ExecutionResult:
        from services.storage.repositories.lead_repo import LeadRepository
        from skills.outreach_intelligence import should_followup, draft_followup

        repo  = LeadRepository()
        leads = repo.list(limit=100, filters={})

        queue = []
        for lead in leads:
            if lead.status in ("new", "contacted", "hot"):
                try:
                    if should_followup(lead.__dict__ if hasattr(lead, '__dict__') else {}):
                        d = draft_followup({"name": lead.name, "phone": getattr(lead, "phone", ""),
                                            "segment": getattr(lead, "segment", "general")})
                        queue.append({
                            "lead_id":    lead.id,
                            "lead_name":  lead.name,
                            "phone":      getattr(lead, "phone", ""),
                            "status":     lead.status,
                            "draft_body": d.body,
                            "channel":    d.channel,
                        })
                except Exception:
                    pass

        msg = f"תור מעקב: {len(queue)} לידים ממתינים לפנייה"
        return ExecutionResult(success=True, message=msg,
                               output={"queue": queue, "count": len(queue)})

    def _schedule_followup(self, task: TaskModel) -> ExecutionResult:
        params  = self._input_params(task)
        lead_id = params.get("lead_id") or (task.input_data or {}).get("lead_id", "")
        days    = int(params.get("days", 2))

        if not lead_id:
            return ExecutionResult(success=False, message="נדרש lead_id",
                                   output={"error": "missing lead_id"})

        from services.storage.repositories.lead_repo import LeadRepository
        lead = LeadRepository().get(lead_id)
        if not lead:
            return ExecutionResult(success=False, message=f"ליד {lead_id} לא נמצא",
                                   output={"error": "not_found"})

        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel
        import datetime
        scheduled_at = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        with get_session() as s:
            s.add(ActivityModel(
                lead_id=lead_id,
                activity_type="followup_scheduled",
                subject=f"מעקב מתוכנן — {scheduled_at}",
                notes=f"מעקב אוטומטי בעוד {days} ימים",
                outcome="pending",
                performed_by="followup_agent",
            ))

        return ExecutionResult(success=True,
                               message=f"מעקב נקבע ל-{lead.name} בתאריך {scheduled_at}",
                               output={"lead_id": lead_id, "scheduled_at": scheduled_at})

    def _batch_followup(self, task: TaskModel) -> ExecutionResult:
        """Propose follow-up drafts for all hot/contacted leads — used by scheduler."""
        from services.storage.repositories.lead_repo import LeadRepository
        from skills.outreach_intelligence import draft_followup
        from skills.learning_skills import get_best_template

        repo   = LeadRepository()
        leads  = repo.list(limit=50, filters={})
        drafts = []

        for lead in leads:
            if lead.status not in ("hot", "contacted"):
                continue
            try:
                seg = getattr(lead, "segment", "general")
                learned = get_best_template("follow_up", seg, "whatsapp")
                body = learned or None
                if not body:
                    d = draft_followup({"name": lead.name,
                                        "segment": seg,
                                        "phone": getattr(lead, "phone", "")})
                    body = d.body
                drafts.append({"lead_id": lead.id, "lead_name": lead.name, "body": body})
            except Exception:
                pass

        return ExecutionResult(success=True,
                               message=f"הוכנו {len(drafts)} טיוטות מעקב",
                               output={"drafts": drafts, "count": len(drafts)})
