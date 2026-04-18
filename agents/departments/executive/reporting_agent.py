"""
ReportingAgent — Reporting and analytics summaries.

Handles:
    (reporting, generate_report)
    (reporting, daily_summary)
    (reporting, weekly_report)
    (reporting, performance_report)
    (reporting, kpi_snapshot)
"""

import logging
from services.storage.models.task import TaskModel
from services.execution.executor  import ExecutionResult
from agents.base.base_agent       import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("reporting", "generate_report"),
    ("reporting", "daily_summary"),
    ("reporting", "weekly_report"),
    ("reporting", "performance_report"),
    ("reporting", "kpi_snapshot"),
}


class ReportingAgent(BaseAgent):
    agent_id   = "builtin_reporting_agent_v1"
    name       = "Reporting Agent"
    department = "executive"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[ReportingAgent] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(success=False, message=f"שגיאה בדוח: {e}",
                                   output={"error": str(e)})

    def _run(self, task: TaskModel) -> ExecutionResult:
        if task.action == "kpi_snapshot":
            return self._kpi_snapshot()
        if task.action in ("weekly_report",):
            return self._weekly_report()
        if task.action == "performance_report":
            return self._performance_report()
        return self._daily_report()

    def _daily_report(self) -> ExecutionResult:
        from engines.reporting_engine import daily_summary, build_text_report
        summary = daily_summary()
        report  = build_text_report(summary)
        return ExecutionResult(success=True, message="דוח יומי נוצר",
                               output={"report": report, **summary})

    def _kpi_snapshot(self) -> ExecutionResult:
        from engines.revenue_engine import revenue_snapshot
        snap = revenue_snapshot()
        kpis = {
            "total_leads":    snap.total_leads,
            "hot_leads":      snap.hot_leads,
            "pipeline_value": snap.pipeline_value,
            "conversion_est": snap.conversion_est,
            "stuck_leads":    snap.stuck_leads,
        }
        lines = [
            f"לידים סה\"כ: {snap.total_leads}",
            f"לידים חמים: {snap.hot_leads}",
            f"שווי צנרת: ₪{snap.pipeline_value:,}",
            f"לידים תקועים: {snap.stuck_leads}",
            f"המרה משוערת: {snap.conversion_est:.0%}" if snap.conversion_est else "",
        ]
        return ExecutionResult(success=True,
                               message="\n".join(l for l in lines if l),
                               output=kpis)

    def _weekly_report(self) -> ExecutionResult:
        from engines.reporting_engine import daily_summary, build_text_report
        from services.storage.repositories.lead_repo import LeadRepository
        summary = daily_summary()
        report  = build_text_report(summary)

        repo  = LeadRepository()
        total = len(repo.list(limit=500, filters={}))
        hot   = len(repo.list(limit=500, filters={"status": "hot"}))

        weekly_lines = [
            "=== דוח שבועי ===",
            report,
            f"\nסיכום שבועי: {total} לידים, {hot} חמים",
        ]
        return ExecutionResult(success=True, message="דוח שבועי נוצר",
                               output={"report": "\n".join(weekly_lines)})

    def _performance_report(self) -> ExecutionResult:
        try:
            from engines.learning_engine import measure_outreach_performance
            p = measure_outreach_performance(30)
            lines = [
                f"ביצועי פנייה — 30 יום:",
                f"• פניות: {p.total_outreach}",
                f"• תגובות: {p.total_replies} ({p.overall_reply_rate:.0%})",
                f"• עסקאות: {p.total_deals}",
                f"• הכנסות: ₪{p.total_revenue:,}",
            ]
            return ExecutionResult(success=True, message="\n".join(lines),
                                   output={"outreach": p.total_outreach,
                                           "replies": p.total_replies,
                                           "reply_rate": p.overall_reply_rate,
                                           "deals": p.total_deals,
                                           "revenue": p.total_revenue})
        except Exception as e:
            return self._daily_report()
