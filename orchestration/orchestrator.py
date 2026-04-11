"""
orchestrator.py — Central control layer for AshbelOS.

Batch 1+2: Conversational Interface + Action Interface
- All intents mapped including new Batch 1/2 intents
- Entity params flow through automatically from intent_parser
- Action handlers return rich structured responses

FIX (Axis 1 / BUG-1):
  Removed duplicate self._tm.mark_completed() and self._tm.mark_failed()
  from handle_command(). task_manager.dispatch() owns the full task lifecycle:
    mark_started → execute → mark_completed / mark_failed
  The orchestrator must only call dispatch() and read the result dict.
"""

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
    success:        bool
    intent:         str
    message:        str
    data:           dict          = field(default_factory=dict)
    task_id:        Optional[str] = None
    trace_id:       Optional[str] = None
    needs_approval: bool          = False
    approval_id:    Optional[str] = None
    error:          Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success":        self.success,
            "intent":         self.intent,
            "message":        self.message,
            "data":           self.data,
            "task_id":        self.task_id,
            "trace_id":       self.trace_id,
            "needs_approval": self.needs_approval,
            "approval_id":    self.approval_id,
            "error":          self.error,
        }


_INTENT_TASK_MAP = {
    # Agent build
    Intent.CREATE_AGENT:             ("agent_build",  "create_agent"),
    Intent.BUILD_AGENT_CODE:         ("agent_build",  "build_agent_code"),
    Intent.APPLY_BUILD:              ("development",  "apply_files"),

    # Assistant
    Intent.ASSISTANT_MESSAGE:        ("assistant",    "draft_message"),
    Intent.ASSISTANT_MEETING:        ("assistant",    "draft_meeting"),
    Intent.ASSISTANT_DASHBOARD:      ("assistant",    "update_dashboard"),
    Intent.ASSISTANT_PLAN:           ("assistant",    "plan_action"),
    Intent.ASSISTANT_REMINDER:       ("assistant",    "set_reminder"),

    # Development
    Intent.DEVELOPMENT_ROADMAP:      ("development",  "roadmap"),
    Intent.DEVELOPMENT_GAP:          ("development",  "gap_analysis"),
    Intent.DEVELOPMENT_BATCH_STATUS: ("development",  "batch_status"),

    # CRM
    Intent.STATUS:                   ("crm",          "read_data"),
    Intent.CREATE_LEAD:              ("sales",        "create_lead"),
    Intent.UPDATE_LEAD:              ("sales",        "update_lead"),
    Intent.LIST_LEADS:               ("crm",          "read_data"),
    Intent.HOT_LEADS:                ("crm",          "hot_leads"),
    Intent.SALES:                    ("sales",        "handle_sales"),

    # Revenue
    Intent.REVENUE_INSIGHTS:         ("revenue",      "revenue_insights"),
    Intent.BOTTLENECK:               ("revenue",      "bottleneck_analysis"),
    Intent.NEXT_ACTION:              ("revenue",      "next_best_action"),

    # Reports
    Intent.DAILY_REPORT:             ("reporting",    "generate_report"),

    # Agent Factory (Batch 3)
    Intent.UPDATE_AGENT:             ("agent_build",  "update_agent"),
    Intent.RETIRE_AGENT:             ("agent_build",  "retire_agent"),
    Intent.LIST_AGENTS:              ("crm",          "read_data"),

    # Revenue (Batch 4)
    Intent.REVENUE_REPORT:           ("revenue",      "revenue_report"),

    # Goal & Growth Engine (Batch 6)
    Intent.SET_GOAL:                 ("growth",       "set_goal"),
    Intent.LIST_GOALS:               ("growth",       "list_goals"),
    Intent.GROWTH_PLAN:              ("growth",       "growth_plan"),

    # Research & Asset Engine (Batch 7)
    Intent.RESEARCH_AUDIENCE:        ("research",     "research_audience"),
    Intent.BUILD_PORTFOLIO:          ("research",     "build_portfolio"),
    Intent.BUILD_OUTREACH_COPY:      ("research",     "build_outreach_copy"),

    # Outreach & Execution Engine (Batch 8)
    Intent.SEND_OUTREACH:            ("outreach",     "send_outreach"),
    Intent.DAILY_PLAN:               ("outreach",     "daily_plan"),
    Intent.FOLLOWUP_QUEUE:           ("outreach",     "followup_queue"),

    # Revenue Learning (Batch 9)
    Intent.LEARNING_CYCLE:           ("learning",     "learning_cycle"),
    Intent.PERFORMANCE_REPORT:       ("learning",     "performance_report"),

    # Chief of Staff (Phase 3)
    Intent.CHIEF_OF_STAFF:           ("executive",    "plan_action"),

    # Lead Acquisition OS (Phase 12)
    Intent.DISCOVER_LEADS:           ("acquisition",  "discover_leads"),
    Intent.PROCESS_INBOUND:          ("acquisition",  "process_inbound"),
    Intent.WEBSITE_ANALYSIS:         ("acquisition",  "website_analysis"),
    Intent.LEAD_OPS_QUEUE:           ("acquisition",  "lead_ops_queue"),
}


class Orchestrator:
    def __init__(self, tm: TaskManager = None):
        self._tm = tm or task_manager

    def handle_command(self, command: str) -> OrchestratorResult:
        global LAST_BUILD_ARTIFACT

        trace_id      = str(uuid.uuid4())
        intent_result = intent_parser.parse(command)

        if not intent_result.is_confident(threshold=0.5):
            return self._unknown_intent(trace_id)

        # Direct handlers (no task needed)
        direct = self._handle_direct(intent_result, trace_id)
        if direct is not None:
            return direct

        task_type, action = _INTENT_TASK_MAP.get(
            intent_result.intent,
            ("assistant", "plan_action"),
        )

        params = dict(intent_result.params or {})

        # APPLY_BUILD: attach last build artifact
        if intent_result.intent == Intent.APPLY_BUILD:
            if not LAST_BUILD_ARTIFACT.get("files"):
                return OrchestratorResult(
                    success=False,
                    intent=intent_result.intent,
                    message="אין כרגע build מוכן ליישום. קודם תבנה קוד לסוכן או לפיצ'ר.",
                    trace_id=trace_id,
                    error="missing_build_artifact",
                )
            params["files"]           = LAST_BUILD_ARTIFACT.get("files", [])
            params["commit_message"]  = LAST_BUILD_ARTIFACT.get("commit_message",
                                        "Apply generated files via AshbelOS")
            params["requested_agent"] = LAST_BUILD_ARTIFACT.get("requested_agent", "")

        task = self._tm.create_task(
            type=task_type,
            action=action,
            input_data={
                "command": command,
                "intent":  intent_result.intent,
                "context": intent_result.context,
                "params":  params,
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

        # ── BUG-1 FIX ────────────────────────────────────────────────────────
        # dispatch() owns the full lifecycle:
        #   mark_started → execute → mark_completed OR mark_failed
        # Do NOT call mark_completed / mark_failed here — that was a duplicate.
        # ─────────────────────────────────────────────────────────────────────
        dispatch_result = self._tm.dispatch(task)

        if dispatch_result.get("success"):
            output = dispatch_result.get("output", {}) or {}

            if intent_result.intent == Intent.BUILD_AGENT_CODE and output.get("files"):
                LAST_BUILD_ARTIFACT = {
                    "files":           output.get("files", []),
                    "commit_message":  output.get("commit_message",
                                       "Apply generated files via AshbelOS"),
                    "requested_agent": output.get("requested_agent", ""),
                    "status":          output.get("status", ""),
                }

            return OrchestratorResult(
                success=True,
                intent=intent_result.intent,
                message=dispatch_result.get("message", "בוצע בהצלחה"),
                data=output,
                task_id=task.id,
                trace_id=trace_id,
            )

        # dispatch() already called mark_failed — do NOT call again
        error = dispatch_result.get("output", "שגיאה לא ידועה")
        return OrchestratorResult(
            success=False,
            intent=intent_result.intent,
            message=f"הפעולה נכשלה: {error}",
            task_id=task.id,
            trace_id=trace_id,
            error=str(error),
        )

    # ── Direct handlers ───────────────────────────────────────────────────────

    def _handle_direct(self, ir: IntentResult, trace_id: str) -> Optional[OrchestratorResult]:
        if ir.intent == Intent.HELP:
            return OrchestratorResult(
                success=True, intent=ir.intent,
                message=_HELP_TEXT, trace_id=trace_id,
            )
        if ir.intent in (Intent.STATUS, Intent.LIST_LEADS):
            return self._system_status(ir, trace_id)
        if ir.intent == Intent.HOT_LEADS:
            return self._hot_leads(ir, trace_id)
        if ir.intent == Intent.DAILY_REPORT:
            return self._daily_report(ir, trace_id)
        if ir.intent == Intent.REVENUE_INSIGHTS:
            return self._revenue_insights(ir, trace_id)
        if ir.intent == Intent.BOTTLENECK:
            return self._bottleneck(ir, trace_id)
        if ir.intent == Intent.NEXT_ACTION:
            return self._next_action(ir, trace_id)
        if ir.intent == Intent.REVENUE_REPORT:
            return self._full_revenue_report(ir, trace_id)
        if ir.intent == Intent.LIST_AGENTS:
            return self._list_agents(ir, trace_id)
        return None

    def _unknown_intent(self, trace_id: str) -> OrchestratorResult:
        return OrchestratorResult(
            success=False, intent="unknown",
            message="לא הבנתי את הפקודה. נסה שוב או הקלד 'עזרה'.",
            trace_id=trace_id, error="low_confidence",
        )

    def _system_status(self, ir, trace_id):
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            leads = LeadRepository().list_all()
            return OrchestratorResult(
                success=True, intent=ir.intent,
                message=f"מערכת פעילה. {len(leads)} לידים במסד.",
                data={"total_leads": len(leads)}, trace_id=trace_id,
            )
        except Exception as e:
            return OrchestratorResult(
                success=False, intent=ir.intent,
                message=f"שגיאת סטטוס: {e}", trace_id=trace_id, error=str(e),
            )

    def _hot_leads(self, ir, trace_id):
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            leads = [l for l in LeadRepository().list_all() if (l.score or 0) >= 70]
            lines = [f"• {l.name} — {l.score}" for l in leads[:5]]
            return OrchestratorResult(
                success=True, intent=ir.intent,
                message="לידים חמים:\n" + "\n".join(lines) if lines else "אין לידים חמים.",
                data={"hot_leads": len(leads)}, trace_id=trace_id,
            )
        except Exception as e:
            return OrchestratorResult(
                success=False, intent=ir.intent,
                message=str(e), trace_id=trace_id, error=str(e),
            )

    def _daily_report(self, ir, trace_id):
        try:
            from engines.reporting_engine import daily_summary, build_text_report
            summary = daily_summary()
            return OrchestratorResult(
                success=True, intent=ir.intent,
                message=build_text_report(summary),
                data=summary, trace_id=trace_id,
            )
        except Exception as e:
            return OrchestratorResult(
                success=False, intent=ir.intent,
                message=str(e), trace_id=trace_id, error=str(e),
            )

    def _revenue_insights(self, ir, trace_id):
        try:
            from engines.revenue_engine import revenue_insights
            insights = revenue_insights()
            return OrchestratorResult(
                success=True, intent=ir.intent,
                message=insights.get("summary", "ללא נתונים"),
                data=insights, trace_id=trace_id,
            )
        except Exception as e:
            return OrchestratorResult(
                success=False, intent=ir.intent,
                message=str(e), trace_id=trace_id, error=str(e),
            )

    def _bottleneck(self, ir, trace_id):
        try:
            from engines.revenue_engine import identify_bottlenecks
            bottlenecks = identify_bottlenecks()
            lines = [f"• {b}" for b in bottlenecks[:5]]
            return OrchestratorResult(
                success=True, intent=ir.intent,
                message="צווארי בקבוק:\n" + "\n".join(lines) if lines else "אין צווארי בקבוק.",
                data={"bottlenecks": bottlenecks}, trace_id=trace_id,
            )
        except Exception as e:
            return OrchestratorResult(
                success=False, intent=ir.intent,
                message=str(e), trace_id=trace_id, error=str(e),
            )

    def _next_action(self, ir, trace_id):
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            from engines.revenue_engine import next_best_actions
            actions = next_best_actions(LeadRepository().list_all(), n=3)
            lines   = [f"• {a.lead_name} — {a.action}" for a in actions]
            return OrchestratorResult(
                success=True, intent=ir.intent,
                message="פעולות מומלצות:\n" + "\n".join(lines) if lines else "אין פעולות דחופות.",
                trace_id=trace_id,
            )
        except Exception as e:
            return OrchestratorResult(
                success=False, intent=ir.intent,
                message=str(e), trace_id=trace_id, error=str(e),
            )

    def _full_revenue_report(self, ir, trace_id):
        return self._daily_report(ir, trace_id)

    def _list_agents(self, ir, trace_id):
        try:
            from services.storage.repositories.agent_repo import AgentRepository
            agents = AgentRepository().get_active()
            lines  = [f"• {a.name} ({a.role})" for a in agents]
            return OrchestratorResult(
                success=True, intent=ir.intent,
                message="סוכנים פעילים:\n" + "\n".join(lines) if lines else "אין סוכנים פעילים.",
                data={"agents": len(agents)}, trace_id=trace_id,
            )
        except Exception as e:
            return OrchestratorResult(
                success=False, intent=ir.intent,
                message=str(e), trace_id=trace_id, error=str(e),
            )


_HELP_TEXT = """פקודות זמינות:
• הוסף ליד [שם] [עיר] [טלפון]
• הצג לידים / לידים חמים
• הגדל מכירות ל[תחום]
• תוכנית צמיחה ל[תחום]
• מה יביא כסף / מה תקוע
• דוח יומי / דוח הכנסות
• תכנן לי את היום
• פרופיל לקוח [תחום]
• שלח פנייה ל[שם/תחום]
• מחזור למידה / דוח ביצועים
• צור סוכן [שם]
• עזרה"""


# ── Singleton ─────────────────────────────────────────────────────────────────
orchestrator = Orchestrator()
