"""
Orchestrator — the central command router.

Receives a parsed IntentResult, decides what to do with it,
creates a Task via TaskManager, and returns a structured OrchestratorResult.

In this initial version (Batch 1):
  - All task types are recognised and routed
  - dispatch() is called on TaskManager but returns a stub result
    until Batch 2 wires real agents
  - Approval gate is checked before dispatch
  - Events are emitted at every step

The orchestrator never calls agents directly.
It only speaks to TaskManager and EventBus.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from orchestration.intent_parser import IntentResult, Intent, intent_parser
from orchestration.task_manager import task_manager, TaskManager
from events.event_bus import event_bus
import events.event_types as ET

log = logging.getLogger(__name__)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class OrchestratorResult:
    success: bool
    intent: str
    message: str
    data: dict = field(default_factory=dict)
    task_id: Optional[str] = None
    trace_id: Optional[str] = None
    needs_approval: bool = False
    approval_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "intent": self.intent,
            "message": self.message,
            "data": self.data,
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "needs_approval": self.needs_approval,
            "approval_id": self.approval_id,
            "error": self.error,
        }


# ── Intent → Task type + action mapping ──────────────────────────────────────

_INTENT_TASK_MAP = {
    Intent.ADD_LEAD: ("crm", "update_crm_status"),
    Intent.LIST_LEADS: ("crm", "read_data"),
    Intent.SCORE_LEADS: ("scoring", "score_lead"),
    Intent.UPDATE_LEAD: ("crm", "update_crm_status"),
    Intent.GENERATE_MESSAGE: ("sales", "generate_content"),
    Intent.SEND_FOLLOWUP: ("followup", "generate_content"),
    Intent.CREATE_AGENT: ("agent_build", "create_agent"),
    Intent.BUILD_AGENT_CODE: ("agent_build", "build_agent_code"),
    Intent.CREATE_DEPARTMENT: ("agent_build", "create_agent"),
    Intent.LIST_AGENTS: ("crm", "read_data"),
    Intent.GENERATE_CONTENT: ("content", "generate_content"),
    Intent.SEO: ("seo", "generate_content"),
    Intent.MARKET_ANALYSIS: ("analysis", "analyze_market"),
    Intent.COMPETITOR: ("analysis", "analyze_market"),
    Intent.BRAINSTORM: ("strategy", "complex_reasoning"),
    Intent.REPORT: ("summarization", "generate_report"),
    Intent.STATUS: ("crm", "read_data"),
    Intent.APPROVE: ("crm", "read_data"),
}


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:

    def __init__(self, tm: TaskManager = None):
        self._tm = tm or task_manager

    def handle_command(self, command: str) -> OrchestratorResult:
        trace_id = str(uuid.uuid4())
        log.info(f"[Orchestrator] command received trace={trace_id}: {command!r}")

        intent_result = intent_parser.parse(command)
        log.info(f"[Orchestrator] parsed: {intent_result}")

        if not intent_result.is_confident(threshold=0.5):
            return self._unknown_intent(command, intent_result, trace_id)

        direct = self._handle_direct(intent_result, trace_id)
        if direct is not None:
            return direct

        task_type, action = _INTENT_TASK_MAP.get(
            intent_result.intent,
            ("strategy", "complex_reasoning"),
        )

        task = self._tm.create_task(
            type=task_type,
            action=action,
            input_data={
                "command": command,
                "intent": intent_result.intent,
                "params": intent_result.params,
            },
            priority=self._priority_for(intent_result.intent),
            trace_id=trace_id,
        )

        approved = self._tm.check_approval(task)
        if not approved:
            return OrchestratorResult(
                success=False,
                intent=intent_result.intent,
                message=f"פעולה '{action}' דורשת אישור. בדוק את תור האישורים.",
                task_id=task.id,
                trace_id=trace_id,
                needs_approval=True,
            )

        self._tm.transition(task.id, "queued")
        dispatch_result = self._tm.dispatch(task)

        if dispatch_result.get("success"):
            self._tm.mark_completed(
                task_id=task.id,
                output_data=dispatch_result,
                model_used=dispatch_result.get("model_used"),
                duration_ms=dispatch_result.get("duration_ms", 0),
                cost_usd=dispatch_result.get("cost_usd", 0.0),
                trace_id=trace_id,
            )
            return OrchestratorResult(
                success=True,
                intent=intent_result.intent,
                message=dispatch_result.get("message", "בוצע בהצלחה"),
                data=dispatch_result.get("output", {}),
                task_id=task.id,
                trace_id=trace_id,
            )

        error = dispatch_result.get("output", "שגיאה לא ידועה")
        self._tm.mark_failed(task.id, str(error), trace_id=trace_id)
        return OrchestratorResult(
            success=False,
            intent=intent_result.intent,
            message=f"הפעולה נכשלה: {error}",
            task_id=task.id,
            trace_id=trace_id,
            error=str(error),
        )

    def _handle_direct(
        self, ir: IntentResult, trace_id: str
    ) -> Optional[OrchestratorResult]:
        if ir.intent == Intent.HELP:
            return OrchestratorResult(
                success=True,
                intent=ir.intent,
                message=_HELP_TEXT,
                trace_id=trace_id,
            )

        if ir.intent == Intent.STATUS:
            return self._system_status(ir, trace_id)

        if ir.intent == Intent.APPROVE:
            return self._handle_approve(ir, trace_id)

        return None

    def _system_status(
        self, ir: IntentResult, trace_id: str
    ) -> OrchestratorResult:
        from services.storage.repositories.agent_repo import AgentRepository
        from services.storage.repositories.lead_repo import LeadRepository
        from services.storage.repositories.approval_repo import ApprovalRepository

        agents = AgentRepository().get_active()
        leads = LeadRepository().list_all()
        pending = ApprovalRepository().get_pending()

        by_dept = {}
        for a in agents:
            by_dept.setdefault(a.department, []).append(a.name)

        data = {
            "agents": len(agents),
            "leads": len(leads),
            "pending_approvals": len(pending),
            "departments": by_dept,
        }
        msg = (
            f"מערכת פעילה — "
            f"{data['agents']} סוכנים, "
            f"{data['leads']} לידים, "
            f"{data['pending_approvals']} ממתינים לאישור."
        )
        return OrchestratorResult(
            success=True,
            intent=ir.intent,
            message=msg,
            data=data,
            trace_id=trace_id,
        )

    def _handle_approve(
        self, ir: IntentResult, trace_id: str
    ) -> OrchestratorResult:
        from services.storage.repositories.approval_repo import ApprovalRepository
        repo = ApprovalRepository()

        approval_id = ir.params.get("approval_id")
        if not approval_id:
            pending = repo.get_pending()
            if not pending:
                return OrchestratorResult(
                    success=True,
                    intent=ir.intent,
                    message="אין אישורים ממתינים.",
                    trace_id=trace_id,
                )
            approval_id = pending[0].id

        result = repo.resolve(approval_id, status="approved", resolved_by="owner")
        if not result:
            return OrchestratorResult(
                success=False,
                intent=ir.intent,
                message=f"לא נמצא אישור עם מזהה {approval_id}.",
                trace_id=trace_id,
                error="approval_not_found",
            )

        event_bus.publish(
            ET.APPROVAL_GRANTED,
            payload={
                "approval_id": approval_id,
                "action": result.action,
                "resolved_by": "owner",
                "task_id": result.task_id,
            },
            trace_id=trace_id,
        )

        return OrchestratorResult(
            success=True,
            intent=ir.intent,
            message=f"פעולה '{result.action}' אושרה.",
            data={"approval_id": approval_id, "action": result.action},
            trace_id=trace_id,
        )

    def _unknown_intent(
        self, command: str, ir: IntentResult, trace_id: str
    ) -> OrchestratorResult:
        log.warning(f"[Orchestrator] unknown intent for: {command!r}")
        return OrchestratorResult(
            success=False,
            intent=Intent.UNKNOWN,
            message=(
                "לא הצלחתי להבין את הפקודה. "
                "נסה להיות יותר ספציפי, או כתוב 'עזרה' לרשימת פקודות."
            ),
            trace_id=trace_id,
            error="intent_not_recognised",
        )

    @staticmethod
    def _priority_for(intent: str) -> int:
        high_priority = {
            Intent.SEND_FOLLOWUP,
            Intent.GENERATE_MESSAGE,
            Intent.APPROVE,
            Intent.BUILD_AGENT_CODE,
        }
        low_priority = {
            Intent.REPORT,
            Intent.MARKET_ANALYSIS,
            Intent.BRAINSTORM,
            Intent.SEO,
        }
        if intent in high_priority:
            return 2
        if intent in low_priority:
            return 7
        return 5


_HELP_TEXT = """
פקודות זמינות:
─────────────────────────────────────────
לידים:
  הוסף ליד: שם=X עיר=Y טלפון=Z
  הצג לידים
  דרג לידים

הודעות:
  כתוב הודעה ל...
  פולואפ ל...

סוכנים:
  צור סוכן [שם/תפקיד]
  בנה קוד לסוכן [שם/תפקיד]
  צור מחלקת [שם]
  הצג סוכנים

תוכן:
  כתוב פוסט על...
  SEO לנושא...

אנליזה:
  ניתוח שוק [נושא]
  מתחרה [שם]
  סיעור מוחות: [נושא]

מערכת:
  סטטוס
  דוח יומי
  אשר [id]
  עזרה
─────────────────────────────────────────
""".strip()


orchestrator = Orchestrator()
