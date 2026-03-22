"""
CEOAgent — Strategic decision maker (Batch 3+4)

Handles:
    (strategy,      complex_reasoning)
    (analysis,      analyze_market)
    (summarization, generate_report)
    (agent_build,   create_agent)      ← NEW Batch 3
    (revenue,       revenue_insights)  ← NEW Batch 4
    (revenue,       bottleneck_analysis)
    (revenue,       next_best_action)
"""

import logging
from services.storage.models.task  import TaskModel
from services.execution.executor   import ExecutionResult
from agents.base.base_agent        import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("strategy",      "complex_reasoning"),
    ("analysis",      "analyze_market"),
    ("summarization", "generate_report"),
    ("agent_build",   "create_agent"),
    ("revenue",       "revenue_insights"),
    ("revenue",       "bottleneck_analysis"),
    ("revenue",       "next_best_action"),
    ("development",   "gap_analysis"),
    ("development",   "batch_status"),
    ("development",   "roadmap"),
}


class CEOAgent(BaseAgent):
    agent_id   = "builtin_ceo_agent_v1"
    name       = "CEO Agent"
    department = "executive"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[CEOAgent] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(success=False, message=f"שגיאה: {e}",
                                   output={"error": str(e)})

    def _run(self, task: TaskModel) -> ExecutionResult:
        if task.type == "summarization":
            return self._generate_report(task)
        if task.type == "agent_build" and task.action == "create_agent":
            return self._create_agent(task)
        if task.type == "revenue":
            return self._revenue_action(task)
        if task.type == "development":
            return self._dev_action(task)
        return self._strategic_analysis(task)

    # ── Report ────────────────────────────────────────────────────────────────

    def _generate_report(self, task: TaskModel) -> ExecutionResult:
        from engines.reporting_engine import daily_summary, build_text_report
        summary = daily_summary()
        report  = build_text_report(summary)
        return ExecutionResult(success=True, message="דוח נוצר",
                               output={"report": report, **summary})

    # ── Agent creation (Batch 3) ──────────────────────────────────────────────

    def _create_agent(self, task: TaskModel) -> ExecutionResult:
        from agents.factory.agent_factory import agent_factory
        params  = self._input_params(task)
        command = (task.input_data or {}).get("command", "")

        # If full spec provided in params
        if params.get("name") and params.get("role"):
            from agents.factory.agent_factory import AgentSpec
            spec = AgentSpec(
                name=params["name"],
                role=params.get("role", ""),
                department=params.get("department", "sales"),
                capabilities=params.get("capabilities", []),
                task_types=params.get("task_types", ["sales"]),
                actions=params.get("actions", ["handle_sales"]),
                model_preference=params.get("model", "claude_haiku"),
                context=command,
            )
        else:
            # Parse from natural language command
            spec = agent_factory.parse_create_request(command)
            if not spec:
                return ExecutionResult(
                    success=False,
                    message="לא הצלחתי להבין את הגדרת הסוכן. נסה: 'צור סוכן follow-up לאדריכלים'",
                    output={"error": "parse_failed"},
                )

        result = agent_factory.create_agent(spec)
        if result.get("success"):
            return ExecutionResult(
                success=True,
                message=f"✅ סוכן '{result['name']}' נוצר ונרשם בהצלחה!",
                output=result,
            )
        return ExecutionResult(
            success=False,
            message=f"שגיאה ביצירת סוכן: {result.get('error')}",
            output=result,
        )

    # ── Revenue actions (Batch 4) ─────────────────────────────────────────────

    def _revenue_action(self, task: TaskModel) -> ExecutionResult:
        from engines.revenue_engine import revenue_snapshot, build_revenue_report

        snap = revenue_snapshot()

        if task.action == "revenue_insights":
            insights = []
            if snap.hot_leads:
                insights.append(f"⚡ {snap.hot_leads} לידים חמים — פנה אליהם היום!")
            if snap.stuck_leads:
                insights.append(f"⚠️ {snap.stuck_leads} לידים תקועים — שנה גישה")
            if snap.pipeline_value:
                insights.append(f"💰 שווי צנרת משוער: ₪{snap.pipeline_value:,}")
            if snap.opportunities:
                top = snap.opportunities[0]
                insights.append(f"🎯 הזדמנות מובילה: {top.lead_name} — {top.action}")
            if not snap.total_leads:
                insights.append("אין לידים במערכת — הוסף לידים כדי לקבל תובנות")

            return ExecutionResult(
                success=True,
                message="\n".join(insights) or "אין תובנות כרגע",
                output={
                    "insights":       insights,
                    "total_leads":    snap.total_leads,
                    "hot_leads":      snap.hot_leads,
                    "pipeline_value": snap.pipeline_value,
                    "conversion_est": snap.conversion_est,
                    "opportunities":  [
                        {"name": o.lead_name, "action": o.action, "urgency": o.urgency}
                        for o in snap.opportunities[:3]
                    ],
                },
            )

        if task.action == "bottleneck_analysis":
            if not snap.bottlenecks:
                msg = "✅ לא זוהו חסמים משמעותיים בצנרת"
            else:
                lines = [f"• {b.category} ({b.count}): {b.suggestion}"
                         for b in snap.bottlenecks]
                msg = "🚧 חסמים שזוהו:\n" + "\n".join(lines)

            return ExecutionResult(
                success=True,
                message=msg,
                output={
                    "bottlenecks":   [{"category": b.category, "count": b.count,
                                       "suggestion": b.suggestion}
                                      for b in snap.bottlenecks],
                    "status_dist":   snap.status_dist,
                },
            )

        if task.action == "next_best_action":
            if not snap.next_actions:
                msg = "אין פעולות דחופות כרגע"
            else:
                lines = [f"{a.priority}. {a.action} [{a.urgency}]"
                         for a in snap.next_actions]
                msg = "✅ פעולות מומלצות:\n" + "\n".join(lines)

            return ExecutionResult(
                success=True,
                message=msg,
                output={
                    "next_actions": [
                        {"priority": a.priority, "lead": a.lead_name,
                         "action": a.action, "channel": a.channel,
                         "urgency": a.urgency}
                        for a in snap.next_actions
                    ],
                },
            )

        # Full revenue report
        report = build_revenue_report(snap)
        return ExecutionResult(success=True, message="דוח הכנסות נוצר",
                               output={"report": report})

    # ── Development ───────────────────────────────────────────────────────────

    def _dev_action(self, task: TaskModel) -> ExecutionResult:
        action = task.action
        if action == "gap_analysis":
            msg = (
                "פערים עיקריים:\n"
                "• Batch 5 — Integrations (WhatsApp, Calendar, Contacts)\n"
                "• AI scoring אוטומטי ללידים\n"
                "• voice input interface"
            )
        elif action == "batch_status":
            msg = (
                "סטטוס פיתוח:\n"
                "✅ Batch 1 — Conversational Interface\n"
                "✅ Batch 2 — Action Interface\n"
                "✅ Batch 3 — Agent Factory\n"
                "✅ Batch 4 — Revenue Layer\n"
                "⏳ Batch 5 — Integrations (הבא)"
            )
        else:  # roadmap
            msg = (
                "תכנית פיתוח:\n"
                "1. ✅ Conversational Interface\n"
                "2. ✅ Action Interface\n"
                "3. ✅ Agent Factory\n"
                "4. ✅ Revenue Layer\n"
                "5. ⏳ Integrations (WhatsApp, Calendar)\n"
                "6. 🔮 Advanced Autonomy"
            )
        return ExecutionResult(success=True, message=msg, output={"status": msg})

    # ── Strategic analysis ────────────────────────────────────────────────────

    def _strategic_analysis(self, task: TaskModel) -> ExecutionResult:
        params  = self._input_params(task)
        command = (task.input_data or {}).get("command", "")
        topic   = params.get("topic") or command
        return ExecutionResult(
            success=True,
            message=f"ניתוח אסטרטגי: {topic}",
            output={"topic": topic,
                    "response": f"ניתוח: {topic}\n• בשלב 4 יתווסף ניתוח מלא מבוסס AI."},
        )
