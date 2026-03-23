
"""
dashboard_engine.py — Dashboard, KPIs & Alerts (Batch 10)
Aggregates all system data into a unified dashboard view.
"""
import datetime, logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

log = logging.getLogger(__name__)

@dataclass
class KPI:
    key:       str
    label:     str
    value:     float
    unit:      str
    trend:     str   # up | down | stable
    target:    float
    status:    str   # green | yellow | red

@dataclass
class Alert:
    alert_id:  str
    severity:  str   # critical | warning | info
    category:  str
    message:   str
    action:    str
    created_at: str

@dataclass
class DashboardData:
    generated_at:   str
    business_name:  str
    kpis:           List[KPI]
    alerts:         List[Alert]
    revenue_summary: dict
    pipeline_summary: dict
    outreach_summary: dict
    learning_summary: dict
    system_health:   dict

def build_kpis(leads: list, outreach_records: list, goals: list) -> List[KPI]:
    now = datetime.datetime.utcnow().isoformat()
    total = len(leads)
    hot   = len([l for l in leads if (l.score or 0) >= 70])
    closed = len([l for l in leads if l.status == "סגור_זכה"])
    avg_score = round(sum(l.score or 0 for l in leads) / total, 1) if total else 0
    total_sent = len(outreach_records)
    replied = len([r for r in outreach_records if r.status == "replied"])
    reply_rate = round(replied / total_sent * 100, 1) if total_sent else 0
    pipeline_value = hot * 15000

    kpis = [
        KPI(key="total_leads",    label="סה\"כ לידים",      value=total,         unit="לידים",  trend="up",     target=50,   status="green" if total >= 10 else "yellow"),
        KPI(key="hot_leads",      label="לידים חמים",       value=hot,           unit="לידים",  trend="up",     target=10,   status="green" if hot >= 5 else "yellow" if hot >= 2 else "red"),
        KPI(key="avg_score",      label="ציון ממוצע",       value=avg_score,     unit="נקודות", trend="stable", target=60,   status="green" if avg_score >= 60 else "yellow" if avg_score >= 40 else "red"),
        KPI(key="reply_rate",     label="שיעור מענה",       value=reply_rate,    unit="%",      trend="up",     target=15,   status="green" if reply_rate >= 15 else "yellow" if reply_rate >= 8 else "red"),
        KPI(key="closed_deals",   label="עסקאות סגורות",   value=closed,        unit="עסקאות", trend="up",     target=5,    status="green" if closed >= 3 else "yellow" if closed >= 1 else "red"),
        KPI(key="pipeline_value", label="שווי צנרת",       value=pipeline_value,unit="₪",      trend="up",     target=150000,status="green" if pipeline_value >= 150000 else "yellow" if pipeline_value >= 75000 else "red"),
        KPI(key="active_goals",   label="יעדים פעילים",    value=len(goals),    unit="יעדים",  trend="stable", target=3,    status="green" if len(goals) >= 1 else "red"),
        KPI(key="total_outreach", label="סה\"כ פניות",      value=total_sent,    unit="פניות",  trend="up",     target=30,   status="green" if total_sent >= 20 else "yellow" if total_sent >= 10 else "red"),
    ]
    return kpis

def build_alerts(kpis: List[KPI], leads: list, outreach_records: list) -> List[Alert]:
    import uuid
    now = datetime.datetime.utcnow().isoformat()
    alerts = []

    for kpi in kpis:
        if kpi.status == "red":
            alerts.append(Alert(
                alert_id=str(uuid.uuid4())[:8],
                severity="critical",
                category=kpi.label,
                message=f"{kpi.label} נמוך מהיעד: {kpi.value}{kpi.unit} (יעד: {kpi.target}{kpi.unit})",
                action=f"בדוק את {kpi.label} ונקוט פעולה",
                created_at=now,
            ))
        elif kpi.status == "yellow":
            alerts.append(Alert(
                alert_id=str(uuid.uuid4())[:8],
                severity="warning",
                category=kpi.label,
                message=f"{kpi.label} מתחת ליעד: {kpi.value}{kpi.unit}",
                action=f"שפר את {kpi.label}",
                created_at=now,
            ))

    # Check overdue follow-ups
    now_str = datetime.datetime.utcnow().isoformat()
    overdue = [r for r in outreach_records if (r.next_followup or "") < now_str and r.status == "pending"]
    if overdue:
        alerts.append(Alert(
            alert_id=str(uuid.uuid4())[:8],
            severity="warning",
            category="follow-up",
            message=f"{len(overdue)} פניות ממתינות לטיפול",
            action="הפעל מחזור outreach יומי",
            created_at=now,
        ))

    alerts.sort(key=lambda a: {"critical":0,"warning":1,"info":2}[a.severity])
    return alerts

def build_dashboard() -> DashboardData:
    now = datetime.datetime.utcnow().isoformat()
    try:
        from config.business_registry import get_active_business
        biz = get_active_business()
        biz_name = biz.name
    except Exception:
        biz_name = "AshbelOS"

    try:
        from services.storage.repositories.lead_repo import LeadRepository
        from services.storage.repositories.outreach_repo import OutreachRepository
        from services.storage.repositories.goal_repo import GoalRepository

        leads    = LeadRepository().list_all()
        outreach = OutreachRepository().list_due_followup()
        goals    = GoalRepository().list_active()

        kpis   = build_kpis(leads, outreach, goals)
        alerts = build_alerts(kpis, leads, outreach)

        # Revenue summary
        closed = [l for l in leads if l.status == "סגור_זכה"]
        hot    = [l for l in leads if (l.score or 0) >= 70]
        revenue_summary = {
            "closed_deals":   len(closed),
            "estimated_revenue": len(closed) * 15000,
            "pipeline_value": len(hot) * 15000 * 0.15,
            "hot_leads":      len(hot),
        }

        # Pipeline summary
        status_dist = {}
        for l in leads:
            st = l.status or "unknown"
            status_dist[st] = status_dist.get(st, 0) + 1
        pipeline_summary = {"total": len(leads), "distribution": status_dist}

        # Outreach summary
        total_sent = len(outreach)
        replied    = len([r for r in outreach if r.status == "replied"])
        outreach_summary = {
            "total_sent":  total_sent,
            "replied":     replied,
            "reply_rate":  round(replied/total_sent*100,1) if total_sent else 0,
            "pending":     len([r for r in outreach if r.status == "pending"]),
        }

        # Learning summary
        try:
            from memory.memory_store import MemoryStore
            learning_summary = {
                "last_cycle":  MemoryStore.get_global("last_learning_cycle", "לא הורץ"),
                "reply_rate":  MemoryStore.get_global("last_reply_rate", 0),
                "top_channel": MemoryStore.get_global("top_channel", "whatsapp"),
                "top_audience":MemoryStore.get_global("top_audience", "architects"),
            }
        except Exception:
            learning_summary = {"last_cycle": "לא הורץ", "reply_rate": 0}

        # System health
        system_health = {
            "api_status":   "online",
            "db_status":    "online",
            "whatsapp_configured": bool(
                __import__("os").environ.get("WHATSAPP_ACCESS_TOKEN")
            ),
            "ai_configured": bool(
                __import__("os").environ.get("ANTHROPIC_API_KEY")
            ),
        }

        return DashboardData(
            generated_at=now,
            business_name=biz_name,
            kpis=kpis,
            alerts=alerts,
            revenue_summary=revenue_summary,
            pipeline_summary=pipeline_summary,
            outreach_summary=outreach_summary,
            learning_summary=learning_summary,
            system_health=system_health,
        )

    except Exception as e:
        log.error(f"[Dashboard] build failed: {e}", exc_info=True)
        return DashboardData(
            generated_at=now, business_name=biz_name,
            kpis=[], alerts=[], revenue_summary={},
            pipeline_summary={}, outreach_summary={},
            learning_summary={}, system_health={"api_status":"online"},
        )

def format_dashboard_text(data: DashboardData) -> str:
    lines = [
        f"📊 Dashboard — {data.business_name}",
        f"{'='*45}",
        f"עדכון: {data.generated_at[:19].replace('T',' ')}",
        f"{'='*45}",
        "KPIs:",
    ]
    for kpi in data.kpis:
        icon = "🟢" if kpi.status=="green" else "🟡" if kpi.status=="yellow" else "🔴"
        lines.append(f"  {icon} {kpi.label}: {kpi.value}{kpi.unit}")
    if data.alerts:
        lines.append(f"{'='*45}")
        lines.append(f"🚨 התראות ({len(data.alerts)}):")
        for a in data.alerts[:5]:
            icon = "🔴" if a.severity=="critical" else "🟡"
            lines.append(f"  {icon} {a.message}")
            lines.append(f"     → {a.action}")
    return "\n".join(lines)
