"""
ReportingEngine — pure report and KPI generation from DB data.

No side effects. No event emission.
Reads from repositories and returns structured report data.

Functions:
    daily_summary()                          -> dict
    lead_kpis(leads)                         -> dict
    agent_summary(agents)                    -> dict
    build_text_report(summary)               -> str
"""

import logging
import datetime
from typing import List

log = logging.getLogger(__name__)


def daily_summary() -> dict:
    """
    Pull current system state from DB and return a structured summary dict.
    No AI — numbers and facts only.
    """
    from services.storage.repositories.lead_repo  import LeadRepository
    from services.storage.repositories.agent_repo import AgentRepository
    from services.storage.repositories.task_repo  import TaskRepository

    leads  = LeadRepository().list_all()
    agents = AgentRepository().get_active()
    tasks_done   = TaskRepository().get_by_status("done")
    tasks_failed = TaskRepository().get_by_status("failed")

    lead_kpi  = compute_lead_kpis(leads)
    agent_kpi = compute_agent_summary(agents)

    return {
        "generated_at":   datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "leads":          lead_kpi,
        "agents":         agent_kpi,
        "tasks": {
            "done":   len(tasks_done),
            "failed": len(tasks_failed),
        },
    }


def compute_lead_kpis(leads: list) -> dict:
    """
    Compute lead KPIs from a list of LeadModel objects.
    Pure — no DB access.
    """
    if not leads:
        return {"total": 0, "hot": 0, "avg_score": 0,
                "by_status": {}, "by_source": {}}

    total     = len(leads)
    scores    = [l.score or 0 for l in leads]
    avg_score = round(sum(scores) / total, 1)
    hot       = sum(1 for s in scores if s >= 70)

    by_status: dict = {}
    by_source: dict = {}
    for lead in leads:
        status = lead.status or "unknown"
        source = lead.source or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        by_source[source] = by_source.get(source, 0) + 1

    return {
        "total":     total,
        "hot":       hot,
        "avg_score": avg_score,
        "by_status": by_status,
        "by_source": by_source,
    }


def compute_agent_summary(agents: list) -> dict:
    """
    Compute agent summary from a list of AgentModel objects.
    Pure — no DB access.
    """
    if not agents:
        return {"total": 0, "by_department": {}}

    by_dept: dict = {}
    for agent in agents:
        dept = agent.department or "unknown"
        by_dept.setdefault(dept, []).append(agent.name)

    return {
        "total":         len(agents),
        "by_department": by_dept,
    }


def build_text_report(summary: dict) -> str:
    """
    Format a summary dict (from daily_summary()) into a readable text report.
    Pure — no I/O.
    """
    from config.settings import COMPANY_NAME

    now       = summary.get("generated_at", "")[:19].replace("T", " ")
    leads     = summary.get("leads", {})
    agents    = summary.get("agents", {})
    tasks     = summary.get("tasks", {})

    lines = [
        f"דוח יומי — {COMPANY_NAME}",
        f"{'─' * 45}",
        f"תאריך          : {now}",
        f"{'─' * 45}",
        f"לידים",
        f"  סה\"כ         : {leads.get('total', 0)}",
        f"  לידים חמים   : {leads.get('hot', 0)}",
        f"  ציון ממוצע   : {leads.get('avg_score', 0)}",
    ]

    by_status = leads.get("by_status", {})
    if by_status:
        lines.append(f"  לפי סטטוס    :")
        for status, count in sorted(by_status.items()):
            lines.append(f"    {status:<18}: {count}")

    by_source = leads.get("by_source", {})
    if by_source:
        lines.append(f"  לפי מקור     :")
        for source, count in sorted(by_source.items()):
            lines.append(f"    {source:<18}: {count}")

    lines += [
        f"{'─' * 45}",
        f"סוכנים",
        f"  פעילים       : {agents.get('total', 0)}",
    ]

    by_dept = agents.get("by_department", {})
    if by_dept:
        lines.append(f"  לפי מחלקה    :")
        for dept, names in sorted(by_dept.items()):
            lines.append(f"    {dept:<18}: {', '.join(names)}")

    lines += [
        f"{'─' * 45}",
        f"משימות",
        f"  הושלמו       : {tasks.get('done', 0)}",
        f"  נכשלו        : {tasks.get('failed', 0)}",
        f"{'─' * 45}",
    ]

    return "\n".join(lines)


# ── AI variant ────────────────────────────────────────────────────────────────

def build_ai_analysis(summary: dict) -> str:
    """
    AI-generated narrative analysis on top of daily_summary() data.
    Falls back to build_text_report() on any error.
    """
    try:
        from routing.model_router import model_router
        leads  = summary.get("leads", {})
        agents = summary.get("agents", {})
        tasks  = summary.get("tasks", {})
        user_prompt = (
            f"נתח את נתוני המערכת הבאים של חברת אשבל אלומיניום:\n"
            f"לידים: סה\"כ={leads.get('total',0)}, חמים={leads.get('hot',0)}, "
            f"ציון ממוצע={leads.get('avg_score',0)}\n"
            f"סוכנים פעילים: {agents.get('total',0)}\n"
            f"משימות: הושלמו={tasks.get('done',0)}, נכשלו={tasks.get('failed',0)}\n\n"
            f"תן: סיכום מנהלים (3 משפטים), 3 תובנות, המלצה אחת לפעולה מיידית."
        )
        return model_router.call(
            task_type="summarization",
            system_prompt="אתה מנהל עסקי של חברת אלומיניום. ענה בעברית בצורה תמציתית.",
            user_prompt=user_prompt,
            max_tokens=400,
        )
    except Exception as e:
        log.warning(f"[ReportingEngine] AI analysis failed: {e}")
        return build_text_report(summary)
