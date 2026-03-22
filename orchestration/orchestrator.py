"""
orchestrator.py — Central control layer for AshbelOS.

Batch 1+2: Conversational Interface + Action Interface
- All intents mapped including new Batch 1/2 intents
- Entity params flow through automatically from intent_parser
- Action handlers return rich structured responses
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
            params["files"] = LAST_BUILD_ARTIFACT.get("files", [])
            params["commit_message"] = LAST_BUILD_ARTIFACT.get("commit_message", "Apply generated files via AshbelOS")
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
        dispatch_result = self._tm.dispatch(task)

        if dispatch_result.get("success"):
            output = dispatch_result.get("output", {}) or {}

            if intent_result.intent == Intent.BUILD_AGENT_CODE and output.get("files"):
                LAST_BUILD_ARTIFACT = {
                    "files":            output.get("files", []),
                    "commit_message":   output.get("commit_message", "Apply generated files via AshbelOS"),
                    "requested_agent":  output.get("requested_agent", ""),
                    "status":           output.get("status", ""),
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
        if ir.intent == Intent.LIST_GOALS:
            return self._list_goals(ir, trace_id)
        return None

    def _system_status(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        from agents.base.agent_registry import agent_registry
        from services.storage.repositories.lead_repo import LeadRepository
        from services.storage.repositories.approval_repo import ApprovalRepository

        agents  = agent_registry.list_agents()
        leads   = LeadRepository().list_all()
        pending = ApprovalRepository().get_pending()

        data = {
            "agents":            len(agents),
            "leads":             len(leads),
            "pending_approvals": len(pending),
            "last_build_ready":  bool(LAST_BUILD_ARTIFACT.get("files")),
            "last_build_agent":  LAST_BUILD_ARTIFACT.get("requested_agent", ""),
            "leads_list": [
                {
                    "id":     l.id,
                    "name":   l.name,
                    "city":   l.city,
                    "phone":  l.phone,
                    "source": l.source,
                    "status": l.status,
                    "score":  l.score,
                }
                for l in leads
            ],
        }

        msg = (f"מערכת פעילה — {data['agents']} סוכנים, "
               f"{data['leads']} לידים, "
               f"{data['pending_approvals']} ממתינים לאישור.")
        return OrchestratorResult(
            success=True, intent=ir.intent,
            message=msg, data=data, trace_id=trace_id,
        )

    def _hot_leads(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        from services.storage.repositories.lead_repo import LeadRepository
        leads = LeadRepository().get_hot_leads(min_score=50)
        data  = {
            "hot_leads": [
                {"name": l.name, "city": l.city, "phone": l.phone,
                 "status": l.status, "score": l.score}
                for l in leads
            ],
            "count": len(leads),
        }
        msg = f"נמצאו {len(leads)} לידים חמים." if leads else "אין לידים חמים כרגע."
        return OrchestratorResult(
            success=True, intent=ir.intent,
            message=msg, data=data, trace_id=trace_id,
        )

    def _daily_report(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        try:
            from engines.reporting_engine import daily_summary, build_text_report
            summary = daily_summary()
            report  = build_text_report(summary)
            return OrchestratorResult(
                success=True, intent=ir.intent,
                message="דוח יומי נוצר",
                data={"report": report, **summary},
                trace_id=trace_id,
            )
        except Exception as e:
            return OrchestratorResult(
                success=False, intent=ir.intent,
                message=f"שגיאה ביצירת דוח: {e}",
                trace_id=trace_id, error=str(e),
            )

    def _revenue_insights(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        from services.storage.repositories.lead_repo import LeadRepository
        repo  = LeadRepository()
        leads = repo.list_all()
        hot   = [l for l in leads if (l.score or 0) >= 70]
        stuck = [l for l in leads if l.status == "ניסיון קשר" and (l.attempts or 0) >= 3]

        insights = []
        if hot:
            insights.append(f"יש {len(hot)} לידים חמים — צור קשר היום!")
        if stuck:
            insights.append(f"{len(stuck)} לידים תקועים ב-'ניסיון קשר' — שקול גישה אחרת.")
        if not leads:
            insights.append("אין לידים במערכת — התחל להזין לידים חדשים.")
        if len(leads) > 0 and not hot:
            insights.append("אין לידים חמים — הכנס לידים ושפר ציונים.")

        return OrchestratorResult(
            success=True, intent=ir.intent,
            message="\n".join(insights) or "אין תובנות כרגע.",
            data={"insights": insights, "total_leads": len(leads), "hot": len(hot), "stuck": len(stuck)},
            trace_id=trace_id,
        )

    def _bottleneck(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        from services.storage.repositories.lead_repo import LeadRepository
        leads = LeadRepository().list_all()
        status_counts: dict = {}
        for l in leads:
            status_counts[l.status] = status_counts.get(l.status, 0) + 1

        bottlenecks = []
        if status_counts.get("ניסיון קשר", 0) > 3:
            bottlenecks.append(f"{status_counts['ניסיון קשר']} לידים תקועים בניסיון קשר — צריך שינוי אסטרטגיה.")
        if status_counts.get("חדש", 0) > 5:
            bottlenecks.append(f"{status_counts['חדש']} לידים חדשים לא טופלו — פנה אליהם היום.")

        msg = "\n".join(bottlenecks) if bottlenecks else "לא זוהו חסמים משמעותיים."
        return OrchestratorResult(
            success=True, intent=ir.intent,
            message=msg,
            data={"status_distribution": status_counts, "bottlenecks": bottlenecks},
            trace_id=trace_id,
        )

    def _next_action(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        from services.storage.repositories.lead_repo import LeadRepository
        leads   = LeadRepository().get_pending_followup()
        actions = []
        for l in leads[:5]:
            actions.append(f"• {l.name} ({l.city or '—'}) — {l.status}, ציון {l.score}")

        msg = "הצעדים הבאים המומלצים:\n" + "\n".join(actions) if actions else "אין פעולות דחופות כרגע."
        return OrchestratorResult(
            success=True, intent=ir.intent,
            message=msg,
            data={"next_actions": [{"name": l.name, "status": l.status, "score": l.score} for l in leads[:5]]},
            trace_id=trace_id,
        )

    def _full_revenue_report(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        from engines.revenue_engine import revenue_snapshot, build_revenue_report
        snap   = revenue_snapshot()
        report = build_revenue_report(snap)
        return OrchestratorResult(
            success=True, intent=ir.intent,
            message="דוח הכנסות נוצר",
            data={
                "report":         report,
                "total_leads":    snap.total_leads,
                "hot_leads":      snap.hot_leads,
                "pipeline_value": snap.pipeline_value,
                "conversion_est": snap.conversion_est,
                "opportunities":  [{"name": o.lead_name, "action": o.action}
                                   for o in snap.opportunities[:3]],
                "bottlenecks":    [{"category": b.category, "suggestion": b.suggestion}
                                   for b in snap.bottlenecks],
                "next_actions":   [{"action": a.action, "urgency": a.urgency}
                                   for a in snap.next_actions[:3]],
            },
            trace_id=trace_id,
        )

    def _list_agents(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        from agents.base.agent_registry import agent_registry
        agents = agent_registry.list_agents()
        data = {
            "agents": [
                {"name": a.name, "department": a.department,
                 "agent_id": a.agent_id, "version": getattr(a, "version", 1)}
                for a in agents
            ],
            "count": len(agents),
        }
        msg = f"פעילים {len(agents)} סוכנים במערכת."
        return OrchestratorResult(
            success=True, intent=ir.intent,
            message=msg, data=data, trace_id=trace_id,
        )

    def _list_goals(self, ir: IntentResult, trace_id: str) -> OrchestratorResult:
        try:
            from services.storage.repositories.goal_repo import GoalRepository
            goals = GoalRepository().list_active()
            return OrchestratorResult(
                success=True, intent=ir.intent,
                message=f"יש {len(goals)} יעדים פעילים." if goals else "אין יעדים פעילים עדיין.",
                data={"goals": [g.to_dict() for g in goals], "total": len(goals)},
                trace_id=trace_id,
            )
        except Exception as e:
            return OrchestratorResult(
                success=False, intent=ir.intent,
                message=f"שגיאה בטעינת יעדים: {e}",
                trace_id=trace_id, error=str(e),
            )

    def _unknown_intent(self, trace_id: str) -> OrchestratorResult:
        return OrchestratorResult(
            success=False,
            intent=Intent.UNKNOWN,
            message="לא הצלחתי להבין את הבקשה. נסה לנסח אחרת או הקלד 'עזרה'.",
            trace_id=trace_id,
            error="intent_not_recognised",
        )


_HELP_TEXT = """
פקודות זמינות:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 לידים
  • הוסף ליד יוסי כהן תל אביב 0501234567
  • הצג לידים / לידים חמים
  • עדכן ליד [שם] לסטטוס מתעניין

💬 תקשורת
  • שלחי הודעה לשרי
  • תקבעי פגישה עם דוד ביום חמישי
  • תזכירי לי לחזור ליוסי מחר

💰 הכנסות (Batch 4)
  • מה הכי יקדם הכנסות היום
  • למה לא סוגרים
  • מה הצעד הבא
  • דוח הכנסות

🤖 סוכנים (Batch 3)
  • צור סוכן follow-up לאדריכלים
  • הצג סוכנים

📊 דוחות
  • דוח יומי / סטטוס

⚙️ מערכת
  • עזרה
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""".strip()


orchestrator = Orchestrator()
