import uuid
from dataclasses import dataclass, field
from typing import Optional

from orchestration.intent_parser import IntentResult, Intent, intent_parser
from orchestration.task_manager import task_manager, TaskManager


LAST_BUILD_ARTIFACT = {
    "files": [],
    "commit_message": "",
    "requested_agent": "",
    "status": "",
}


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


_INTENT_TASK_MAP = {
    Intent.CREATE_AGENT: ("agent_build", "create_agent"),
    Intent.BUILD_AGENT_CODE: ("agent_build", "build_agent_code"),
    Intent.APPLY_BUILD: ("development", "apply_files"),

    Intent.ASSISTANT_MESSAGE: ("assistant", "draft_message"),
    Intent.ASSISTANT_MEETING: ("assistant", "draft_meeting"),
    Intent.ASSISTANT_DASHBOARD: ("assistant", "update_dashboard"),
    Intent.ASSISTANT_PLAN: ("assistant", "plan_action"),

    Intent.DEVELOPMENT_ROADMAP: ("development", "roadmap"),
    Intent.DEVELOPMENT_GAP: ("development", "gap_analysis"),
    Intent.DEVELOPMENT_BATCH_STATUS: ("development", "batch_status"),

    Intent.STATUS: ("crm", "read_data"),

    # 🔥 SALES
    Intent.CREATE_LEAD: ("sales", "create_lead"),
    Intent.SALES: ("sales", "handle_sales"),
}


class Orchestrator:
    def __init__(self, tm: TaskManager = None):
        self._tm = tm or task_manager

    def handle_command(self, command: str) -> OrchestratorResult:
        global LAST_BUILD_ARTIFACT

        trace_id = str(uuid.uuid4())
        intent_result = intent_parser.parse(command)

        if not intent_result.is_confident(threshold=0.5):
            return self._unknown_intent(trace_id)

        direct = self._handle_direct(intent_result, trace_id)
        if direct is not None:
            return direct

        task_type, action = _INTENT_TASK_MAP.get(
            intent_result.intent,
            ("assistant", "plan_action"),
        )

        params = dict(intent_result.params or {})

        if intent_result.intent == Intent.APPLY_BUILD:
            if not LAST_BUILD_ARTIFACT.get("files"):
                return OrchestratorResult(
                    success=False,
                    intent=intent_result.intent,
                    message="אין כרגע build מוכן ליישום. קודם תבנה קוד לסוכן או לפיצ'ר.",
                    trace_id=trace_id,
                    error="missing_build_artifact",
                )

            params["files"] = LAST_BUILD_ARTIFACT.get("files", [])
            params["commit_message"] = LAST_BUILD_ARTIFACT.get("commit_message", "Apply generated files via AshbalOS")
            params["requested_agent"] = LAST_BUILD_ARTIFACT.get("requested_agent", "")

        task = self._tm.create_task(
            type=task_type,
            action=action,
            input_data={
                "command": command,
                "intent": intent_result.intent,
                "params": params,
            },
            priority=5,
            trace_id=trace_id,
        )

        approved = self._tm.check_approval(task)
        if not approved:
            return OrchestratorResult(
                success=False,
                intent=intent_result.intent,
                message=f"פעולה '{action}' דורשת אישור.",
                task_id=task.id,
                trace_id=trace_id,
                needs_approval=True,
            )

        self._tm.transition(task.id, "queued")
        dispatch_result = self._tm.dispatch(task)

        if dispatch_result.get("success"):
            output = dispatch_result.get("output", {}) or {}

            if intent_result.intent == Intent.BUILD_AGENT_CODE and output.get("files"):
                LAST_BUILD_ARTIFACT = {
                    "files": output.get("files", []),
                    "commit_message": output.get("commit_message", "Apply generated files via AshbalOS"),
                    "requested_agent": output.get("requested_agent", ""),
                    "status": output.get("status", ""),
                }

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
                data=output,
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

        return None

    def _system_status(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        from agents.base.agent_registry import agent_registry
        from services.storage.repositories.lead_repo import LeadRepository
        from services.storage.repositories.approval_repo import ApprovalRepository

        agents = agent_registry.list_agents()
        leads = LeadRepository().list_all()
        pending = ApprovalRepository().get_pending()

        data = {
            "agents": len(agents),
            "leads": len(leads),
            "pending_approvals": len(pending),
            "last_build_ready": bool(LAST_BUILD_ARTIFACT.get("files")),
            "last_build_agent": LAST_BUILD_ARTIFACT.get("requested_agent", ""),
        }

        return OrchestratorResult(
            success=True,
            intent=ir.intent,
            message=f"מערכת פעילה — {data['agents']} סוכנים, {data['leads']} לידים, {data['pending_approvals']} ממתינים לאישור.",
            data=data,
            trace_id=trace_id,
        )

    def _unknown_intent(self, trace_id: str) -> OrchestratorResult:
        return OrchestratorResult(
            success=False,
            intent=Intent.UNKNOWN,
            message="לא הצלחתי להבין את הבקשה.",
            trace_id=trace_id,
            error="intent_not_recognised",
        )


_HELP_TEXT = """
פקודות זמינות:
- צור סוכן חדש
- בנה קוד לסוכן חדש
- תיישמי את הקבצים
- תשלחי הודעה לשרי
- תקבעי פגישה עם יוסי ביום חמישי
- תוסיפי לידים חמים למסך הבית
- תני לי roadmap
- מה חסר במערכת
- מה מצב הפיתוח
- סטטוס
""".strip()


orchestrator = Orchestrator()
