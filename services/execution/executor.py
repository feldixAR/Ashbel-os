"""
executor.py — Execution entry point for all task actions.

Batch 1+2: Full handler registry for CRM, assistant, revenue, and reporting.
Contract: execute(task) -> ExecutionResult (never raises)
"""

import logging
import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Callable

from services.storage.models.task import TaskModel

log = logging.getLogger(__name__)


# ── ExecutionResult ───────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    success:     bool
    message:     str
    output:      dict          = field(default_factory=dict)
    model_used:  Optional[str] = None
    cost_usd:    float         = 0.0
    duration_ms: int           = 0

    def to_dict(self) -> dict:
        return {
            "success":     self.success,
            "message":     self.message,
            "output":      self.output,
            "model_used":  self.model_used,
            "cost_usd":    self.cost_usd,
            "duration_ms": self.duration_ms,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(datetime.datetime.utcnow().timestamp() * 1000)

def _elapsed_ms(started: int) -> int:
    return _now_ms() - started

def _params(task: TaskModel) -> dict:
    return (task.input_data or {}).get("params", {})

def _command(task: TaskModel) -> str:
    return (task.input_data or {}).get("command", "")


# ── CRM Handlers ──────────────────────────────────────────────────────────────

def _handle_create_lead(task: TaskModel) -> ExecutionResult:
    from services.storage.repositories.lead_repo import LeadRepository
    from events.event_bus import event_bus
    import events.event_types as ET

    started = _now_ms()
    p = _params(task)

    name   = (p.get("name")   or "").strip()
    city   = (p.get("city")   or "").strip()
    phone  = (p.get("phone")  or "").strip()
    source = (p.get("source") or "manual").strip()
    notes  = (p.get("notes")  or "").strip()

    if not name:
        # Try to extract name from command text as fallback
        cmd = _command(task)
        import re
        m = re.search(r"ליד\s+([א-תa-zA-Z]+(?:\s+[א-תa-zA-Z]+)?)", cmd)
        if m:
            name = m.group(1).strip()

    if not name:
        return ExecutionResult(
            success=False,
            message="שגיאה: שם הליד חסר. נסה: 'הוסף ליד יוסי כהן תל אביב 0501234567'",
            output={"error": "missing_name", "tip": "פרמט: הוסף ליד [שם] [עיר] [טלפון]"},
        )

    try:
        lead = LeadRepository().create(
            name=name, city=city, phone=phone, source=source, notes=notes)
    except Exception as e:
        log.error(f"[Executor] create_lead failed task={task.id}: {e}", exc_info=True)
        return ExecutionResult(
            success=False,
            message=f"שגיאה ביצירת ליד: {e}",
            output={"error": str(e)},
        )

    event_bus.publish(
        ET.LEAD_CREATED,
        payload={"lead_id": lead.id, "name": lead.name,
                 "city": lead.city, "phone": lead.phone, "source": lead.source},
        source_task_id=task.id,
        trace_id=task.trace_id,
    )

    return ExecutionResult(
        success=True,
        message=f"✅ ליד נוצר בהצלחה: {lead.name}" + (f" ({lead.city})" if lead.city else ""),
        output={
            "lead_id": lead.id, "name": lead.name, "city": lead.city,
            "phone": lead.phone, "source": lead.source, "status": lead.status,
        },
        duration_ms=_elapsed_ms(started),
    )


def _handle_update_crm_status(task: TaskModel) -> ExecutionResult:
    """Alias for create_lead (legacy handler name)."""
    return _handle_create_lead(task)


def _handle_update_lead(task: TaskModel) -> ExecutionResult:
    from services.storage.repositories.lead_repo import LeadRepository
    started = _now_ms()
    p = _params(task)

    lead_id = p.get("lead_id", "")
    status  = p.get("status", "")
    score   = p.get("score")
    notes   = p.get("notes", "")

    if not lead_id and not p.get("name"):
        return ExecutionResult(
            success=False,
            message="שגיאה: חסר מזהה ליד לעדכון.",
            output={"error": "missing_lead_id"},
        )

    repo = LeadRepository()
    if lead_id and status:
        repo.update_status(lead_id, status)
    if lead_id and score is not None:
        repo.update_score(lead_id, int(score))

    return ExecutionResult(
        success=True,
        message=f"ליד עודכן בהצלחה.",
        output={"lead_id": lead_id, "status": status, "score": score},
        duration_ms=_elapsed_ms(started),
    )


def _handle_hot_leads(task: TaskModel) -> ExecutionResult:
    from services.storage.repositories.lead_repo import LeadRepository
    started = _now_ms()
    leads   = LeadRepository().get_hot_leads(min_score=50)
    data = [
        {"name": l.name, "city": l.city or "—", "phone": l.phone or "—",
         "status": l.status, "score": l.score}
        for l in leads
    ]
    msg = f"נמצאו {len(data)} לידים חמים." if data else "אין לידים חמים כרגע."
    return ExecutionResult(
        success=True, message=msg,
        output={"hot_leads": data, "count": len(data)},
        duration_ms=_elapsed_ms(started),
    )


def _handle_read_data(task: TaskModel) -> ExecutionResult:
    from services.storage.repositories.lead_repo import LeadRepository
    from agents.base.agent_registry import agent_registry
    started = _now_ms()
    leads   = LeadRepository().list_all()
    agents  = agent_registry.list_agents()
    data = {
        "leads": [
            {"id": l.id, "name": l.name, "city": l.city, "phone": l.phone,
             "source": l.source, "status": l.status, "score": l.score}
            for l in leads
        ],
        "agents_count": len(agents),
        "leads_count":  len(leads),
    }
    return ExecutionResult(
        success=True,
        message=f"נטענו {len(leads)} לידים ו-{len(agents)} סוכנים.",
        output=data,
        duration_ms=_elapsed_ms(started),
    )


# ── Assistant Handlers (Batch 2 — draft flow) ─────────────────────────────────

def _handle_draft_message(task: TaskModel) -> ExecutionResult:
    """Prepares a WhatsApp draft with contact resolution and deep link."""
    started = _now_ms()
    p       = _params(task)
    cmd     = _command(task)

    contact = p.get("contact_name") or p.get("name") or "איש קשר"
    text    = p.get("message") or (
        f"היי {contact}, רציתי לעדכן אותך לגבי הנושא שדיברנו עליו. "
        f"האם נוח לך לדבר?"
    )

    # Resolve contact phone from CRM
    phone    = ""
    lead_id  = ""
    try:
        from services.integrations.contacts import contacts_service
        resolved = contacts_service.resolve(contact)
        if resolved:
            phone   = resolved.phone or ""
            lead_id = resolved.lead_id or ""
            contact = resolved.name   # use exact DB name
    except Exception:
        pass

    # Build draft with deep link if phone found
    try:
        from services.integrations.whatsapp import whatsapp_service
        draft = whatsapp_service.prepare_draft(contact, phone, text, lead_id)
    except Exception:
        draft = {
            "action_type":    "whatsapp_draft",
            "contact_name":   contact,
            "phone":          phone,
            "draft_message":  text,
            "channel":        "whatsapp",
            "needs_approval": True,
            "next_step":      "approve_or_edit",
        }

    return ExecutionResult(
        success=True,
        message=f"טיוטת הודעה מוכנה ל-{contact}" + (f" ({phone})" if phone else " — לא נמצא טלפון"),
        output={**draft, "command": cmd},
        duration_ms=_elapsed_ms(started),
    )


def _handle_draft_meeting(task: TaskModel) -> ExecutionResult:
    """Prepares a calendar event draft with deep link."""
    started = _now_ms()
    p       = _params(task)

    contact = p.get("contact_name") or p.get("name") or "איש קשר"
    date    = p.get("date") or ""
    notes   = p.get("notes") or ""

    try:
        from services.integrations.calendar import calendar_service, CalendarEvent
        event = CalendarEvent(
            title=f"פגישה עם {contact}",
            date=date or __import__("datetime").date.today().isoformat(),
            attendee_name=contact, notes=notes,
        )
        draft = calendar_service.prepare_draft(event)
    except Exception:
        draft = {
            "action_type":    "calendar_draft",
            "contact_name":   contact,
            "meeting_title":  f"פגישה עם {contact}",
            "meeting_date":   date or "לקביעה",
            "notes":          notes,
            "channel":        "calendar",
            "needs_approval": True,
            "next_step":      "approve_or_edit",
        }

    return ExecutionResult(
        success=True,
        message=f"טיוטת פגישה מוכנה עם {contact}",
        output=draft,
        duration_ms=_elapsed_ms(started),
    )


def _handle_set_reminder(task: TaskModel) -> ExecutionResult:
    """Creates a reminder entry."""
    started = _now_ms()
    p       = _params(task)
    cmd     = _command(task)

    contact = p.get("contact_name") or p.get("name") or ""
    date    = p.get("date") or "מחר"
    notes   = p.get("notes") or cmd

    reminder_text = f"לחזור ל{contact}" if contact else "תזכורת"

    return ExecutionResult(
        success=True,
        message=f"תזכורת נרשמה: {reminder_text} ב-{date}",
        output={
            "action_type":  "reminder",
            "contact_name": contact,
            "reminder_text": reminder_text,
            "date":         date,
            "notes":        notes,
            "status":       "set",
        },
        duration_ms=_elapsed_ms(started),
    )


def _handle_plan_action(task: TaskModel) -> ExecutionResult:
    """Generic plan action handler."""
    cmd = _command(task)
    return ExecutionResult(
        success=True,
        message="העוזר האישי ניתח את הבקשה",
        output={
            "status":             "planned",
            "command":            cmd,
            "suggested_next_steps": [
                "classify_request",
                "prepare_draft",
                "ask_for_approval_if_needed",
            ],
        },
    )


def _handle_update_dashboard(task: TaskModel) -> ExecutionResult:
    p      = _params(task)
    widget = p.get("widget") or "לידים חמים"
    return ExecutionResult(
        success=True,
        message=f"בקשת עדכון מסך הבית נרשמה: {widget}",
        output={
            "action_type":    "dashboard_update",
            "widget":         widget,
            "needs_approval": True,
            "next_step":      "apply_dashboard_update",
        },
    )


# ── Revenue Handlers ──────────────────────────────────────────────────────────

def _handle_revenue_insights(task: TaskModel) -> ExecutionResult:
    from services.storage.repositories.lead_repo import LeadRepository
    started = _now_ms()
    repo    = LeadRepository()
    leads   = repo.list_all()
    hot     = [l for l in leads if (l.score or 0) >= 70]
    stuck   = [l for l in leads if l.status == "ניסיון קשר" and (l.attempts or 0) >= 3]

    insights = []
    if hot:
        insights.append(f"⚡ {len(hot)} לידים חמים — פנה אליהם היום!")
    if stuck:
        insights.append(f"⚠️ {len(stuck)} לידים תקועים — שקול גישה שונה.")
    if not leads:
        insights.append("אין לידים במערכת. התחל להזין לידים.")
    if not hot and leads:
        insights.append("אין לידים חמים — שפר ציונים או הוסף לידים חדשים.")

    return ExecutionResult(
        success=True,
        message="\n".join(insights) or "אין תובנות כרגע.",
        output={"insights": insights, "total": len(leads), "hot": len(hot), "stuck": len(stuck)},
        duration_ms=_elapsed_ms(started),
    )


def _handle_bottleneck(task: TaskModel) -> ExecutionResult:
    from services.storage.repositories.lead_repo import LeadRepository
    started = _now_ms()
    leads   = LeadRepository().list_all()
    counts: dict = {}
    for l in leads:
        counts[l.status] = counts.get(l.status, 0) + 1

    bottlenecks = []
    if counts.get("ניסיון קשר", 0) > 3:
        bottlenecks.append(f"🔴 {counts['ניסיון קשר']} לידים תקועים בניסיון קשר")
    if counts.get("חדש", 0) > 5:
        bottlenecks.append(f"🟡 {counts['חדש']} לידים חדשים לא טופלו")

    msg = "\n".join(bottlenecks) if bottlenecks else "לא זוהו חסמים."
    return ExecutionResult(
        success=True, message=msg,
        output={"distribution": counts, "bottlenecks": bottlenecks},
        duration_ms=_elapsed_ms(started),
    )


def _handle_next_best_action(task: TaskModel) -> ExecutionResult:
    from services.storage.repositories.lead_repo import LeadRepository
    started = _now_ms()
    leads   = LeadRepository().get_pending_followup()[:5]
    actions = [
        {"name": l.name, "city": l.city or "—", "status": l.status, "score": l.score}
        for l in leads
    ]
    lines = [f"• {a['name']} ({a['city']}) — {a['status']}, ציון {a['score']}" for a in actions]
    msg   = "הפעולות הבאות המומלצות:\n" + "\n".join(lines) if lines else "אין פעולות דחופות."
    return ExecutionResult(
        success=True, message=msg,
        output={"next_actions": actions},
        duration_ms=_elapsed_ms(started),
    )


def _handle_generate_report(task: TaskModel) -> ExecutionResult:
    try:
        from engines.reporting_engine import daily_summary, build_text_report
        summary = daily_summary()
        report  = build_text_report(summary)
        return ExecutionResult(
            success=True, message="דוח יומי נוצר",
            output={"report": report, **summary},
        )
    except Exception as e:
        return ExecutionResult(
            success=False, message=f"שגיאה ביצירת דוח: {e}",
            output={"error": str(e)},
        )



# ── Agent Factory Handlers (Batch 3) ─────────────────────────────────────────

def _handle_create_agent(task: TaskModel) -> ExecutionResult:
    from agents.factory.agent_factory import agent_factory
    started = _now_ms()
    params  = _params(task)
    command = _command(task)

    spec = agent_factory.parse_create_request(command)
    if not spec:
        return ExecutionResult(
            success=False,
            message="לא הצלחתי להבין את הגדרת הסוכן.",
            output={"error": "parse_failed", "tip": "נסה: 'צור סוכן follow-up לאדריכלים'"},
        )

    result = agent_factory.create_agent(spec)
    if result.get("success"):
        return ExecutionResult(
            success=True,
            message=f"✅ סוכן '{result['name']}' נוצר ונרשם!",
            output=result,
            duration_ms=_elapsed_ms(started),
        )
    return ExecutionResult(
        success=False,
        message=f"שגיאה: {result.get('error')}",
        output=result,
    )


def _handle_revenue_report(task: TaskModel) -> ExecutionResult:
    from engines.revenue_engine import revenue_snapshot, build_revenue_report
    started = _now_ms()
    snap    = revenue_snapshot()
    report  = build_revenue_report(snap)
    return ExecutionResult(
        success=True,
        message="דוח הכנסות נוצר",
        output={
            "report":         report,
            "total_leads":    snap.total_leads,
            "hot_leads":      snap.hot_leads,
            "pipeline_value": snap.pipeline_value,
            "conversion_est": snap.conversion_est,
        },
        duration_ms=_elapsed_ms(started),
    )


# ── Handler Registry ──────────────────────────────────────────────────────────

_HANDLERS: Dict[str, Callable] = {
    # CRM
    "create_lead":          _handle_create_lead,
    "update_crm_status":    _handle_update_crm_status,
    "update_lead":          _handle_update_lead,
    "hot_leads":            _handle_hot_leads,
    "read_data":            _handle_read_data,

    # Assistant / Batch 2
    "draft_message":        _handle_draft_message,
    "draft_meeting":        _handle_draft_meeting,
    "set_reminder":         _handle_set_reminder,
    "plan_action":          _handle_plan_action,
    "update_dashboard":     _handle_update_dashboard,

    # Revenue intelligence
    "revenue_insights":     _handle_revenue_insights,
    "bottleneck_analysis":  _handle_bottleneck,
    "next_best_action":     _handle_next_best_action,

    # Reporting
    "generate_report":      _handle_generate_report,

    # Agent Factory (Batch 3)
    "create_agent":         _handle_create_agent,

    # Revenue (Batch 4)
    "revenue_report":       _handle_revenue_report,

    # Goal & Growth Engine (Batch 6)
    "set_goal":             _handle_set_goal,
    "list_goals":           _handle_list_goals,
    "growth_plan":          _handle_growth_plan,
}


# ── Batch 6 — Goal & Growth Engine ───────────────────────────────────────────

def _handle_set_goal(task: TaskModel) -> ExecutionResult:
    from engines.goal_engine import (
        decompose_goal, identify_opportunities,
        build_research_summary, build_asset_draft, build_outreach_plan,
    )
    from services.storage.repositories.goal_repo import GoalRepository
    from services.storage.repositories.opportunity_repo import OpportunityRepository
    from services.storage.repositories.outreach_repo import OutreachRepository

    started  = _now_ms()
    p        = _params(task)
    raw_goal = p.get("goal") or p.get("raw_goal") or _command(task)

    # 1. Decompose goal into tracks
    decomp  = decompose_goal(raw_goal)
    goal_id = decomp["goal_id"]

    # 2. Save goal to DB
    try:
        goal_db = GoalRepository().create(
            raw_goal=raw_goal,
            domain=decomp["domain"],
            primary_metric=decomp["primary_metric"],
            tracks=decomp["tracks"],
        )
        goal_id = goal_db.id
    except Exception as e:
        log.warning(f"[Executor] goal DB save failed: {e}")

    # 3. Identify opportunities
    opportunities = identify_opportunities(goal_id, decomp["tracks"])

    # 4. Save opportunities to DB
    saved_opps = []
    try:
        opp_repo = OpportunityRepository()
        for opp in opportunities[:6]:
            opp_db = opp_repo.create(
                goal_id=goal_id,
                track_id=opp["track_id"],
                title=opp["title"],
                audience=opp["audience"],
                channel=opp["channel"],
                potential=opp["potential"],
                effort=opp["effort"],
                next_action=opp["next_action"],
            )
            saved_opps.append(opp_db.to_dict())
    except Exception as e:
        log.warning(f"[Executor] opp DB save failed: {e}")
        saved_opps = opportunities[:6]

    # 5. Research summary
    top_audience = decomp["tracks"][0]["audience"] if decomp["tracks"] else "general"
    top_channel  = decomp["tracks"][0]["channel"]  if decomp["tracks"] else "whatsapp"
    research     = build_research_summary(goal_id, decomp["domain"], top_audience)

    # 6. Asset draft
    asset = build_asset_draft(goal_id, top_audience, top_channel)

    # 7. Outreach plan (based on top opportunity)
    top_opp      = opportunities[0] if opportunities else {"opp_id": "", "audience": top_audience, "channel": top_channel, "title": "", "next_action": ""}
    outreach_plan = build_outreach_plan(goal_id, top_opp)

    # 8. Save outreach record to DB
    try:
        OutreachRepository().create(
            goal_id=goal_id,
            opp_id=top_opp.get("opp_id", ""),
            contact_name="[ממתין לפרטי קשר]",
            contact_phone="",
            channel=top_channel,
            message_body=asset["message"]["body"],
        )
    except Exception as e:
        log.warning(f"[Executor] outreach DB save failed: {e}")

    return ExecutionResult(
        success=True,
        message=(
            f"✅ יעד עסקי הוגדר: {raw_goal}\n"
            f"תחום: {decomp['domain']} | "
            f"{len(decomp['tracks'])} מסלולי צמיחה | "
            f"{len(opportunities)} הזדמנויות"
        ),
        output={
            "goal": {
                "id":             goal_id,
                "raw_goal":       raw_goal,
                "domain":         decomp["domain"],
                "primary_metric": decomp["primary_metric"],
                "tracks":         decomp["tracks"],
            },
            "opportunities":  saved_opps,
            "research":       research,
            "asset_draft":    asset,
            "outreach_plan":  outreach_plan,
            "next_steps": [
                f"פנייה ראשונה ל-{top_audience}",
                "בניית רשימת קשרים",
                "שליחת תיק עבודות",
                "מעקב follow-up אחרי 3 ימים",
            ],
        },
        duration_ms=_elapsed_ms(started),
    )


def _handle_list_goals(task: TaskModel) -> ExecutionResult:
    from services.storage.repositories.goal_repo import GoalRepository
    started = _now_ms()
    goals   = GoalRepository().list_active()
    return ExecutionResult(
        success=True,
        message=f"יש {len(goals)} יעדים פעילים." if goals else "אין יעדים פעילים עדיין.",
        output={"goals": [g.to_dict() for g in goals], "total": len(goals)},
        duration_ms=_elapsed_ms(started),
    )


def _handle_growth_plan(task: TaskModel) -> ExecutionResult:
    from engines.goal_engine import decompose_goal, build_research_summary, build_asset_draft
    started  = _now_ms()
    raw_goal = _params(task).get("goal") or _command(task)
    decomp   = decompose_goal(raw_goal)
    goal_id  = decomp["goal_id"]
    top_audience = decomp["tracks"][0]["audience"] if decomp["tracks"] else "general"
    top_channel  = decomp["tracks"][0]["channel"]  if decomp["tracks"] else "whatsapp"
    research = build_research_summary(goal_id, decomp["domain"], top_audience)
    asset    = build_asset_draft(goal_id, top_audience, top_channel)
    plan     = []
    for track in decomp["tracks"]:
        plan.append({
            "track":   track["name"],
            "channel": track["channel"],
            "actions": track["actions"],
        })
    return ExecutionResult(
        success=True,
        message=f"תוכנית צמיחה נבנתה עבור: {raw_goal}",
        output={
            "goal":     raw_goal,
            "domain":   decomp["domain"],
            "tracks":   plan,
            "research": research,
            "asset":    asset,
        },
        duration_ms=_elapsed_ms(started),
    )

def execute(task: TaskModel) -> ExecutionResult:
    """
    Priority:
      1. AgentRegistry — agent-based
      2. _HANDLERS     — direct handlers
      3. Unhandled     — ExecutionResult(success=False)
    """
    action    = task.action
    task_type = task.type

    # 1. AgentRegistry
    try:
        from agents.base.agent_registry import agent_registry
        agent = agent_registry.find(task_type, action)
        if agent is not None:
            log.debug(f"[Executor] ({task_type},{action}) → {agent.name!r}")
            return agent.execute(task)
    except Exception as e:
        log.error(f"[Executor] registry error: {e}", exc_info=True)

    # 2. Direct handlers
    handler = _HANDLERS.get(action)
    if handler:
        try:
            return handler(task)
        except Exception as e:
            log.error(f"[Executor] handler crashed action={action}: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                message=f"שגיאה בביצוע '{action}': {e}",
                output={"error": str(e)},
            )

    # 3. Unhandled
    log.warning(f"[Executor] no handler for ({task_type},{action}) task={task.id}")
    return ExecutionResult(
        success=False,
        message=f"אין handler לפעולה '{action}'",
        output={"error": "unhandled_action", "action": action, "task_type": task_type},
    )
