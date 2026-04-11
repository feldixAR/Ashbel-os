"""
executor.py — Execution entry point for all task actions.

Batch 1+2: Full handler registry for CRM, assistant, revenue, and reporting.
Contract: execute(task) -> ExecutionResult (never raises)
"""

import logging
import datetime
from typing import Dict, Callable

from services.storage.models.task import TaskModel
from services.execution.result import ExecutionResult  # noqa: F401 — re-exported

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)

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
    from engines.revenue_engine import next_best_actions
    started = _now_ms()
    leads   = LeadRepository().list_all()
    actions = next_best_actions(leads, n=5)
    if actions:
        lines = [f"• {a.lead_name} — {a.action} ({a.urgency})" for a in actions]
        msg   = "הפעולות הבאות המומלצות:\n" + "\n".join(lines)
        out   = {"next_actions": [{"lead_name": a.lead_name, "action": a.action,
                                   "channel": a.channel, "urgency": a.urgency,
                                   "reason": a.reason} for a in actions]}
    else:
        msg = "אין פעולות דחופות כרגע."
        out = {"next_actions": []}
    return ExecutionResult(
        success=True, message=msg, output=out,
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


# ── Sales handler (C3 fix) ───────────────────────────────────────────────────

def _handle_sales(task: TaskModel) -> ExecutionResult:
    """Generic sales intent — routes to create_lead or hot_leads based on params."""
    p = _params(task)
    if p.get("name"):
        return _handle_create_lead(task)
    return _handle_hot_leads(task)


# ── Agent Factory handlers (H1 fix) ──────────────────────────────────────────

def _handle_update_agent(task: TaskModel) -> ExecutionResult:
    from agents.factory.agent_factory import agent_factory
    started  = _now_ms()
    p        = _params(task)
    agent_id = p.get("agent_id") or p.get("id") or ""
    spec_updates = {k: v for k, v in p.items() if k not in ("agent_id", "id")}
    if not agent_id:
        return ExecutionResult(
            success=False,
            message="חסר מזהה סוכן לעדכון. נסה: 'עדכן סוכן [id]'",
            output={"error": "missing_agent_id"},
        )
    try:
        agent_factory.update_agent(agent_id, spec_updates)
        return ExecutionResult(
            success=True,
            message=f"סוכן {agent_id} עודכן בהצלחה.",
            output={"agent_id": agent_id},
            duration_ms=_elapsed_ms(started),
        )
    except Exception as e:
        log.error(f"[Executor] update_agent failed: {e}", exc_info=True)
        return ExecutionResult(success=False, message=f"שגיאה בעדכון סוכן: {e}", output={"error": str(e)})


def _handle_retire_agent(task: TaskModel) -> ExecutionResult:
    from agents.factory.agent_factory import agent_factory
    started  = _now_ms()
    p        = _params(task)
    agent_id = p.get("agent_id") or p.get("id") or ""
    if not agent_id:
        return ExecutionResult(
            success=False,
            message="חסר מזהה סוכן לפרישה. נסה: 'פרוש סוכן [id]'",
            output={"error": "missing_agent_id"},
        )
    try:
        agent_factory.retire_agent(agent_id)
        return ExecutionResult(
            success=True,
            message=f"סוכן {agent_id} הוצא משירות.",
            output={"agent_id": agent_id},
            duration_ms=_elapsed_ms(started),
        )
    except Exception as e:
        log.error(f"[Executor] retire_agent failed: {e}", exc_info=True)
        return ExecutionResult(success=False, message=f"שגיאה בפרישת סוכן: {e}", output={"error": str(e)})


# ── Batch 6 — Goal & Growth Engine ───────────────────────────────────────────

def _handle_set_goal(task: TaskModel) -> ExecutionResult:
    """
    E2E pipeline: Objective → Goal Engine → Research → Scoring → Committee → DB.
    Delegates to services/growth/pipeline.py.
    """
    started  = _now_ms()
    p        = _params(task)
    raw_goal = p.get("goal") or p.get("raw_goal") or _command(task)

    from services.growth.pipeline import run
    result = run(raw_goal)

    if not result.success:
        return ExecutionResult(
            success=False,
            message=f"שגיאה בהגדרת יעד: {result.error}",
            output={"error": result.error},
            duration_ms=_elapsed_ms(started),
        )

    decision = result.committee_decision
    winner   = decision.get("winner", {})
    return ExecutionResult(
        success=True,
        message=(
            f"✅ יעד עסקי הוגדר: {raw_goal}\n"
            f"תחום: {result.domain} | "
            f"{len(result.tracks)} מסלולי צמיחה | "
            f"{len(result.scored_opportunities)} הזדמנויות מדורגות\n"
            f"מנצח ועדה [{winner.get('normalized_score',0)}/100]: {winner.get('title','')}"
        ),
        output={
            "goal": {
                "id":      result.goal_id,
                "raw_goal": result.raw_goal,
                "domain":   result.domain,
                "metric":   result.metric,
                "tracks":   result.tracks,
            },
            "research":             result.research,
            "scored_opportunities": result.scored_opportunities,
            "committee_decision":   result.committee_decision,
            "asset_draft":          result.asset_draft,
            "outreach_plan":        result.outreach_plan,
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
    """
    Growth plan: E2E pipeline → Committee decision → ranked prioritized_actions.
    """
    started  = _now_ms()
    raw_goal = _params(task).get("goal") or _command(task)

    from services.growth.pipeline import run
    result = run(raw_goal)

    if not result.success:
        return ExecutionResult(
            success=False,
            message=f"שגיאה בתוכנית צמיחה: {result.error}",
            output={"error": result.error},
            duration_ms=_elapsed_ms(started),
        )

    decision = result.committee_decision
    winner   = decision.get("winner", {})
    actions  = decision.get("prioritized_actions", [])
    return ExecutionResult(
        success=True,
        message=(
            f"תוכנית צמיחה: {raw_goal}\n"
            f"מנצח ועדה: {winner.get('title','')} "
            f"[{winner.get('normalized_score',0)}/100]\n"
            f"פעולה ראשונה: {actions[0] if actions else '—'}"
        ),
        output={
            "goal":                 raw_goal,
            "domain":               result.domain,
            "research":             result.research,
            "scored_opportunities": result.scored_opportunities,
            "committee_decision":   result.committee_decision,
            "asset":                result.asset_draft,
            "outreach_plan":        result.outreach_plan,
        },
        duration_ms=_elapsed_ms(started),
    )


# ── Batch 7 — Research & Asset Engine ────────────────────────────────────────

def _handle_research_audience(task: TaskModel) -> ExecutionResult:
    from engines.research_engine import build_client_profile, build_market_map
    started  = _now_ms()
    p        = _params(task)
    audience = p.get("audience") or "architects"
    domain   = p.get("domain")   or "aluminum"
    profile  = build_client_profile(audience, domain)
    market   = build_market_map(domain)
    return ExecutionResult(
        success=True,
        message=f"פרופיל קהל '{audience}' נוצר.",
        output={"profile": profile.__dict__ if hasattr(profile, "__dict__") else str(profile),
                "market":  market.__dict__  if hasattr(market,  "__dict__") else str(market)},
        duration_ms=_elapsed_ms(started),
    )


def _handle_build_portfolio(task: TaskModel) -> ExecutionResult:
    from engines.research_engine import build_niche_portfolio
    started  = _now_ms()
    p        = _params(task)
    audience = p.get("audience") or "architects"
    portfolio = build_niche_portfolio(audience)
    return ExecutionResult(
        success=True,
        message=f"תיק עבודות לקהל '{audience}' נוצר.",
        output={"portfolio": portfolio.__dict__ if hasattr(portfolio, "__dict__") else str(portfolio)},
        duration_ms=_elapsed_ms(started),
    )


def _handle_build_outreach_copy(task: TaskModel) -> ExecutionResult:
    from engines.research_engine import build_collaboration_proposal
    started  = _now_ms()
    p        = _params(task)
    audience = p.get("audience") or "architects"
    proposal = build_collaboration_proposal(audience)
    return ExecutionResult(
        success=True,
        message=f"נוסח פנייה לקהל '{audience}' נוצר.",
        output={"copy": proposal.__dict__ if hasattr(proposal, "__dict__") else str(proposal)},
        duration_ms=_elapsed_ms(started),
    )


# ── Batch 8 — Outreach & Execution Engine ────────────────────────────────────

def _handle_send_outreach(task: TaskModel) -> ExecutionResult:
    from engines.outreach_engine import outreach_engine
    from services.storage.repositories.goal_repo import GoalRepository
    started = _now_ms()
    p       = _params(task)
    goal_id = p.get("goal_id") or ""
    # Use most recent active goal if not specified
    if not goal_id:
        goals = GoalRepository().list_active()
        if goals:
            goal_id = goals[0].id
    if not goal_id:
        return ExecutionResult(
            success=False,
            message="לא נמצא יעד פעיל. הגדר יעד קודם עם 'הגדל מכירות ב...'",
            output={"error": "no_active_goal"},
        )
    result = outreach_engine.run_outreach_batch(goal_id)
    sent   = len(result) if result else 0
    return ExecutionResult(
        success=True,
        message=f"נשלחו {sent} פניות.",
        output={"sent": sent, "tasks": [t.__dict__ if hasattr(t, "__dict__") else t for t in (result or [])]},
        duration_ms=_elapsed_ms(started),
    )


def _handle_daily_plan(task: TaskModel) -> ExecutionResult:
    import dataclasses
    from engines.outreach_engine import outreach_engine
    started = _now_ms()
    try:
        summary = outreach_engine.build_daily_summary()
        lines   = []
        if hasattr(summary, "top_priorities") and summary.top_priorities:
            for ot in summary.top_priorities[:5]:
                lines.append(f"• {ot.lead_name} — {ot.message[:60]}...")
        msg = "תוכנית יומית:\n" + "\n".join(lines) if lines else "אין פניות דחופות להיום."
        safe_summary = dataclasses.asdict(summary) if dataclasses.is_dataclass(summary) else {}
        return ExecutionResult(
            success=True,
            message=msg,
            output={"summary": safe_summary},
            duration_ms=_elapsed_ms(started),
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            message=f"שגיאה בתוכנית יומית: {e}",
            output={"error": str(e)},
            duration_ms=_elapsed_ms(started),
        )


def _handle_followup_queue(task: TaskModel) -> ExecutionResult:
    from engines.outreach_engine import outreach_engine
    started = _now_ms()
    queue   = outreach_engine.get_followup_queue()
    lines   = [f"• {item.lead_name} ({item.channel}) — ניסיון #{item.attempt}"
               for item in (queue or [])[:10]]
    import dataclasses
    msg = f"תור follow-up — {len(queue or [])} פניות:\n" + "\n".join(lines) if lines else "תור follow-up ריק."
    return ExecutionResult(
        success=True,
        message=msg,
        output={"queue": [dataclasses.asdict(q) if dataclasses.is_dataclass(q) else q for q in (queue or [])]},
        duration_ms=_elapsed_ms(started),
    )


# ── Batch 9 — Revenue Learning ────────────────────────────────────────────────

def _handle_learning_cycle(task: TaskModel) -> ExecutionResult:
    from engines.learning_engine import learning_engine
    started = _now_ms()
    try:
        result = learning_engine.run_learning_cycle()
        return ExecutionResult(
            success=True,
            message=result.cycle_summary if hasattr(result, "cycle_summary") else "מחזור למידה הושלם.",
            output={"cycle": result.__dict__ if hasattr(result, "__dict__") else {}},
            duration_ms=_elapsed_ms(started),
        )
    except Exception as e:
        log.error(f"[Executor] learning_cycle failed: {e}", exc_info=True)
        return ExecutionResult(success=False, message=f"שגיאה במחזור למידה: {e}", output={"error": str(e)})


def _handle_performance_report(task: TaskModel) -> ExecutionResult:
    from engines.learning_engine import learning_engine
    started = _now_ms()
    try:
        report = learning_engine.build_performance_report()
        return ExecutionResult(
            success=True,
            message=f"דוח ביצועים — שיעור מענה: {getattr(report, 'overall_reply_rate', 0):.1f}%",
            output={"report": report.__dict__ if hasattr(report, "__dict__") else {}},
            duration_ms=_elapsed_ms(started),
        )
    except Exception as e:
        return ExecutionResult(success=False, message=f"שגיאה בדוח ביצועים: {e}", output={"error": str(e)})



# ── Handler Registry ──────────────────────────────────────────────────────────
# FIX (Axis 1 / Bootstrap): module-level dict defined AFTER all _handle_* functions.
# Replaces _get_handlers() wrapper — prevents NameError on import and satisfies
# AST-based bootstrap tests that scan for _HANDLERS at module scope.

_HANDLERS = {
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
    "update_agent":         _handle_update_agent,
    "retire_agent":         _handle_retire_agent,
    # Sales (C3 fix)
    "handle_sales":         _handle_sales,
    # Revenue (Batch 4)
    "revenue_report":       _handle_revenue_report,
    # Goal & Growth Engine (Batch 6)
    "set_goal":             _handle_set_goal,
    "list_goals":           _handle_list_goals,
    "growth_plan":          _handle_growth_plan,
    # Research & Asset Engine (Batch 7)
    "research_audience":    _handle_research_audience,
    "build_portfolio":      _handle_build_portfolio,
    "build_outreach_copy":  _handle_build_outreach_copy,
    # Outreach & Execution Engine (Batch 8)
    "send_outreach":        _handle_send_outreach,
    "daily_plan":           _handle_daily_plan,
    "followup_queue":       _handle_followup_queue,
    # Revenue Learning (Batch 9)
    "learning_cycle":       _handle_learning_cycle,
    "performance_report":   _handle_performance_report,
}


def execute(task: TaskModel) -> ExecutionResult:
    """
    Priority:
      1. _HANDLERS     — direct handlers (specific, always preferred)
      2. AgentRegistry — specific registered agents only (no fallback)
      3. AgentRegistry — fallback (GenericTaskAgent)
    """
    action    = task.action
    task_type = task.type

    # 1. Direct handlers — checked first so _HANDLERS always win over GenericTaskAgent fallback
    handler = _HANDLERS.get(action)
    if handler:
        try:
            log.debug(f"[Executor] ({task_type},{action}) → _HANDLERS")
            return handler(task)
        except Exception as e:
            log.error(f"[Executor] handler crashed action={action}: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                message=f"שגיאה בביצוע '{action}': {e}",
                output={"error": str(e)},
            )

    # 2. AgentRegistry (specific agents + fallback for truly unknown actions)
    try:
        from agents.base.agent_registry import agent_registry
        agent = agent_registry.find(task_type, action)
        if agent is not None:
            log.debug(f"[Executor] ({task_type},{action}) → {agent.name!r}")
            return agent.execute(task)
    except Exception as e:
        log.error(f"[Executor] registry error: {e}", exc_info=True)

    # 3. Unhandled
    log.warning(f"[Executor] no handler for ({task_type},{action}) task={task.id}")
    return ExecutionResult(
        success=False,
        message=f"אין handler לפעולה '{action}'",
        output={"error": "unhandled_action", "action": action, "task_type": task_type},
    )
