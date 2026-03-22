"""
Orchestrator — central command router.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from orchestration.intent_parser import IntentResult, Intent, intent_parser
from orchestration.task_manager import task_manager, TaskManager

log = logging.getLogger(__name__)


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


_INTENT_TASK_MAP: dict[str, tuple[str, str]] = {
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

    def _handle_direct(self, ir: IntentResult, trace_id: str) -> Optional[OrchestratorResult]:
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

    def _system_status(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        from services.storage.repositories.agent_repo import AgentRepository
        from services.storage.repositories.lead_repo import LeadRepository
        from services.storage.repositories.approval_repo import ApprovalRepository

        agents = AgentRepository().get_active()
        leads = LeadRepository().list_all()
        pending = ApprovalRepository().get_pending()

        by_dept: dict[str, list[str]] = {}
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

    def _handle_approve(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
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

        ok = repo.approve(approval_id)
        if ok:
            return OrchestratorResult(
                success=True,
                intent=ir.intent,
                message=f"אישור {approval_id} בוצע בהצלחה.",
                data={"approval_id": approval_id},
                trace_id=trace_id,
            )

        return OrchestratorResult(
            success=False,
            intent=ir.intent,
            message=f"לא נמצא אישור {approval_id}.",
            trace_id=trace_id,
        )

    def _unknown_intent(self, command: str, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        return OrchestratorResult(
            success=False,
            intent=ir.intent,
            message=f"לא הצלחתי להבין את הבקשה: {command}",
            data={"suggestion": "נסה לנסח אחרת או להשתמש בפקודה ברורה יותר"},
            trace_id=trace_id,
            error="unknown_intent",
        )

    def _priority_for(self, intent: str) -> int:
        high = {
            Intent.CREATE_AGENT,
            Intent.BUILD_AGENT_CODE,
            Intent.SEND_FOLLOWUP,
            Intent.APPROVE,
        }
        medium = {
            Intent.GENERATE_MESSAGE,
            Intent.UPDATE_LEAD,
            Intent.ADD_LEAD,
        }
        if intent in high:
            return 90
        if intent in medium:
            return 60
        return 30


_HELP_TEXT = """פקודות אפשריות:
- צור סוכן חדש
- בנה קוד לסוכן חדש
- הצג סוכנים
- סטטוס
- כתוב הודעה
- הוסף ליד
"""

orchestrator = Orchestrator()
