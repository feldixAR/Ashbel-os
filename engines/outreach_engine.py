"""
outreach_engine.py — Outreach & Execution Engine (Batch 8)
Real-world execution: send, follow-up, pipeline management, daily prioritization.
"""
import datetime, logging, re, urllib.parse, uuid as _uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional

log = logging.getLogger(__name__)

@dataclass
class OutreachTask:
    task_id: str; lead_id: str; lead_name: str; phone: str
    channel: str; message: str; audience: str; priority: int
    urgency: str; reason: str; goal_id: str = ""; opp_id: str = ""
    attempt: int = 1; deep_link: str = ""

@dataclass
class OutreachResult:
    success: bool; task_id: str; lead_name: str; channel: str; mode: str
    message_id: str = ""; deep_link: str = ""; error: str = ""; sent_at: str = ""

@dataclass
class PipelineEntry:
    outreach_id: str; lead_name: str; phone: str; channel: str
    status: str; attempt: int; sent_at: str; next_followup: str; message_body: str

@dataclass
class DailySummary:
    date: str; total_due: int; sent_today: int; replied_today: int
    pending: int; overdue: int; top_priorities: List[OutreachTask]; pipeline: List[PipelineEntry]

FOLLOWUP_TEMPLATES = {
    "architects": {
        1: "שלום {name},\n\nשלחתי לך הצעה לפני מספר ימים — רציתי לוודא שהגיעה.\nיש לי תיק עבודות שעשוי לעניין אותך.\nמתי נוח לשיחה קצרה?\n\nבברכה",
        2: "שלום {name},\n\nרק רציתי לשאול אם יש פרויקט שאנחנו יכולים לעזור בו.\nזמינים גם לכמויות קטנות.\n\nבברכה",
        3: "שלום {name},\n\nפנייה אחרונה ממני. אם תצטרך בעתיד ספק אמין — נשמח.\n\nבברכה",
    },
    "contractors": {
        1: "שלום {name},\n\nשלחתי הצעת מחיר לפני מספר ימים — קיבלת?\nנשמח לענות על שאלות.\n\nבברכה",
        2: "שלום {name},\n\nיש לנו מבצע השבוע לקבלנים — הנחה על הזמנות מעל ₪20,000.\nמעניין?\n\nבברכה",
        3: "שלום {name},\n\nנסיון קשר אחרון. כשיהיה פרויקט מתאים — נשמח.\n\nבברכה",
    },
    "private": {
        1: "שלום {name},\n\nרציתי לעקוב — האם עדיין מתכנן שיפוץ?\nנשמח לבוא לסקר ללא התחייבות.\n\nבברכה",
        2: "שלום {name},\n\nיש לנו מקום פנוי בלוח הזמנים — מעוניין להתחיל לתכנן?\n\nבברכה",
        3: "שלום {name},\n\nאם תרצה בעתיד — אנחנו כאן.\nבברכה",
    },
    "general": {
        1: "שלום {name},\n\nרציתי לעקוב אחרי הפנייה שלי — האם יש עניין?\n\nבברכה",
        2: "שלום {name},\n\nעוקב שוב — נשמח לשמוע אם יש שאלות.\n\nבברכה",
        3: "שלום {name},\n\nנסיון אחרון מצידנו. כשתהיה מוכן — אנחנו כאן.\n\nבברכה",
    },
}

def _biz_name() -> str:
    try:
        from config.business_registry import get_active_business
        return get_active_business().name
    except Exception:
        return "החברה שלנו"

def _biz_domain() -> str:
    try:
        from config.business_registry import get_active_business
        return get_active_business().domain
    except Exception:
        return "עסק"

def build_initial_message(audience: str, name: str) -> str:
    biz = _biz_name()
    domain = _biz_domain()
    templates = {
        "architects": f"שלום {{name}},\n\nאני מ{biz} — מתמחים ב{domain} לאדריכלים.\nאשמח לשלוח תיק עבודות רלוונטי.\nהאם מתאים?\n\nבברכה",
        "contractors": f"שלום {{name}},\n\nאני מ{biz} — ספק עם ניסיון רב בעבודה עם קבלנים.\nמחירים תחרותיים, אספקה בזמן, תנאי אשראי גמישים.\nהאם תרצה הצעת מחיר?\n\nבברכה",
        "private": f"שלום {{name}},\n\nאני מ{biz} — מתמחים ב{domain} לבית.\nנשמח לבוא לסקר ולתת הצעת מחיר ללא התחייבות.\n\nבברכה",
        "general": f"שלום {{name}},\n\nאני מ{biz} — נשמח להכיר ולדון בשיתוף פעולה.\n\nבברכה",
    }
    return templates.get(audience, templates["general"]).replace("{name}", name)

def build_followup_message(audience: str, name: str, attempt: int) -> str:
    templates = FOLLOWUP_TEMPLATES.get(audience, FOLLOWUP_TEMPLATES["general"])
    key = min(attempt, max(templates.keys()))
    return templates[key].replace("{name}", name)

def _detect_audience(lead) -> str:
    combined = ((lead.notes or "") + (lead.source or "") + (lead.name or "")).lower()
    if any(w in combined for w in ["אדריכל","מעצב","architect","designer"]): return "architects"
    if any(w in combined for w in ["קבלן","יזם","contractor","developer"]): return "contractors"
    return "private"

def _build_whatsapp_link(phone: str, message: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0"): digits = "972" + digits[1:]
    if not digits: return ""
    return f"https://wa.me/{digits}?text={urllib.parse.quote(message)}"

def _get_lead_score(leads: list, lead_id: str) -> int:
    for l in leads:
        if l.id == lead_id: return l.score or 0
    return 0

def build_outreach_queue(leads: list, goals: list = None) -> List[OutreachTask]:
    tasks = []
    closed = {"סגור_זכה","סגור_הפסיד"}
    for lead in leads:
        if (lead.status or "") in closed: continue
        if not (lead.phone or "").strip(): continue
        score = lead.score or 0; attempts = lead.attempts or 0; status = lead.status or "חדש"
        audience = _detect_audience(lead)
        if attempts >= 5: continue
        if attempts == 0:
            message = build_initial_message(audience, lead.name)
            urgency = "today" if score >= 60 else "this_week"
            reason = f"פנייה ראשונה — ציון {score}"; priority = 1 if score >= 70 else 2
        else:
            message = build_followup_message(audience, lead.name, attempts)
            urgency = "today" if score >= 50 else "this_week"
            reason = f"follow-up #{attempts + 1} — {status}"; priority = 2 if score >= 50 else 3
        deep_link = _build_whatsapp_link(lead.phone, message)
        tasks.append(OutreachTask(task_id=str(_uuid.uuid4()), lead_id=lead.id, lead_name=lead.name, phone=lead.phone, channel="whatsapp", message=message, audience=audience, priority=priority, urgency=urgency, reason=reason, attempt=attempts + 1, deep_link=deep_link))
    return sorted(tasks, key=lambda t: (t.priority, -_get_lead_score(leads, t.lead_id)))

def prioritize_daily(queue: List[OutreachTask], max_tasks: int = 10) -> List[OutreachTask]:
    today = [t for t in queue if t.urgency == "today"]
    week  = [t for t in queue if t.urgency == "this_week"]
    return (today + week)[:max_tasks]

def _normalize_e164(phone: str) -> str:
    """Convert Israeli phone (05X-XXXXXXX, 05XXXXXXXX, +972...) to E.164 (9725XXXXXXX)."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("972"):
        return digits
    if digits.startswith("0") and len(digits) >= 9:
        return "972" + digits[1:]
    return digits


def _send_email(task: OutreachTask) -> OutreachResult:
    """Send via SMTP when configured; fall back to 'logged' mode if not."""
    import os, smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    host = os.environ.get("SMTP_HOST", "")
    user = os.environ.get("SMTP_USER", "")
    pwd  = os.environ.get("SMTP_PASS", "")
    to   = task.phone  # for email channel, 'phone' field carries the email address

    if host and user and pwd and "@" in (to or ""):
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"{_biz_name()} — {task.lead_name}"
            msg["From"]    = user
            msg["To"]      = to
            msg.attach(MIMEText(task.message, "plain", "utf-8"))
            port = int(os.environ.get("SMTP_PORT", "587"))
            with smtplib.SMTP(host, port, timeout=10) as srv:
                srv.starttls()
                srv.login(user, pwd)
                srv.sendmail(user, [to], msg.as_string())
            log.info(f"[Email] sent to {to} lead={task.lead_id}")
            return OutreachResult(
                success=True, task_id=task.task_id, lead_name=task.lead_name,
                channel="email", mode="smtp", message_id="", sent_at=now,
            )
        except Exception as e:
            log.error(f"[Email] SMTP failed to={to}: {e}")
            return OutreachResult(
                success=False, task_id=task.task_id, lead_name=task.lead_name,
                channel="email", mode="smtp", error=str(e), sent_at=now,
            )

    # SMTP not configured — log the intended message, return 'logged' mode
    log.info(f"[Email] SMTP not configured — logged lead={task.lead_id} to={to}")
    return OutreachResult(
        success=True, task_id=task.task_id, lead_name=task.lead_name,
        channel="email", mode="logged", message_id="", sent_at=now,
    )


def execute_outreach(task: OutreachTask) -> OutreachResult:
    import os
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # ── Cultural adaptation (pure Python, 0 tokens) ────────────────────────────
    try:
        from services.integrations.cultural_adapter import cultural_adapter
        lead_stub = type("L", (), {
            "name":   task.lead_name,
            "notes":  "",
            "status": task.audience or "",
            "source": "",
        })()
        task = task.__class__(
            **{**task.__dict__,
               "message": cultural_adapter.adapt_message(lead_stub, task.message, task.attempt or 0)}
        )
    except Exception as _ca_err:
        log.debug(f"[Outreach] cultural_adapter skipped: {_ca_err}")

    # ── Email channel ──────────────────────────────────────────────────────────
    if task.channel == "email":
        return _send_email(task)

    # ── WhatsApp channel ───────────────────────────────────────────────────────
    try:
        from services.integrations.whatsapp_client import WhatsAppClient
        token    = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
        phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        if token and phone_id:
            e164 = _normalize_e164(task.phone)   # FIX: normalize before API call
            result = WhatsAppClient(phone_id, token).send_text(e164, task.message)
            if result.get("success"):
                return OutreachResult(
                    success=True, task_id=task.task_id, lead_name=task.lead_name,
                    channel=task.channel, mode="api",
                    message_id=result.get("message_id", ""), sent_at=now,
                )
            # API returned failure — log and fall through to deeplink
            log.warning(f"[Outreach] WhatsApp API returned failure: {result.get('error')}")
    except Exception as e:
        log.warning(f"[Outreach] WhatsApp API exception: {e}")

    # ── Safe deeplink fallback (all other channels or API unavailable) ─────────
    return OutreachResult(
        success=True, task_id=task.task_id, lead_name=task.lead_name,
        channel=task.channel, mode="deeplink", deep_link=task.deep_link, sent_at=now,
    )

def _write_activity(lead_id: str, atype: str, subject: str, notes: str,
                    direction: str = "outbound", outcome: str = "completed") -> bool:
    """Write an outreach execution event to ActivityModel → appears in lead timeline."""
    if not lead_id:
        return False
    try:
        import uuid as _u, datetime as _dt
        import pytz
        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel
        tz = pytz.timezone("Asia/Jerusalem")
        now_il = _dt.datetime.now(tz).isoformat()
        with get_session() as s:
            s.add(ActivityModel(
                id=str(_u.uuid4()), lead_id=lead_id,
                activity_type=atype, direction=direction,
                subject=subject, notes=notes, outcome=outcome,
                performed_by="system", performed_at_il=now_il,
            ))
        return True
    except Exception as e:
        log.error(f"[Outreach] _write_activity failed: {e}")
        return False


def record_outreach_sent(task: OutreachTask, mode: str = "deeplink") -> bool:
    try:
        import datetime as _dt
        from services.storage.repositories.outreach_repo import OutreachRepository
        from services.storage.repositories.lead_repo import LeadRepository
        from services.storage.db import get_session
        from services.storage.models.outreach import OutreachModel

        # Create outreach record
        repo    = OutreachRepository()
        created = repo.create(
            goal_id=task.goal_id or "", opp_id=task.opp_id or "",
            contact_name=task.lead_name, contact_phone=task.phone,
            channel=task.channel, message_body=task.message,
        )

        # Advance lifecycle: awaiting_response + next follow-up date
        next_action = (_dt.datetime.now(datetime.timezone.utc) + _dt.timedelta(days=3)).isoformat()
        with get_session() as s:
            rec = s.get(OutreachModel, created.id)
            if rec:
                rec.lifecycle_status = "awaiting_response"
                rec.next_action_at   = next_action
                rec.status           = "sent"
                rec.sent_at          = _dt.datetime.now(datetime.timezone.utc).isoformat()

        # Lead counters
        LeadRepository().increment_attempts(task.lead_id)
        if task.attempt == 1:
            LeadRepository().update_status(task.lead_id, "ניסיון קשר")

        # Write to unified timeline
        ch_label = {"whatsapp": "WhatsApp", "email": "אימייל", "sms": "SMS"}.get(task.channel, task.channel)
        _write_activity(
            lead_id   = task.lead_id,
            atype     = task.channel if task.channel in ("whatsapp", "email") else "note",
            subject   = f"שליחת {ch_label} (ניסיון {task.attempt})",
            notes     = (task.message or "")[:300],
            direction = "outbound",
            outcome   = "follow_up_needed",
        )
        return True
    except Exception as e:
        log.error(f"[Outreach] record failed: {e}"); return False


def record_outreach_failed(task: OutreachTask, error: str = "") -> bool:
    """Record a send failure to OutreachModel + timeline."""
    try:
        import uuid as _u, datetime as _dt
        from services.storage.db import get_session
        from services.storage.models.outreach import OutreachModel
        from services.storage.repositories.outreach_repo import OutreachRepository

        created = OutreachRepository().create(
            goal_id=task.goal_id or "", opp_id=task.opp_id or "",
            contact_name=task.lead_name, contact_phone=task.phone,
            channel=task.channel, message_body=task.message,
        )
        with get_session() as s:
            rec = s.get(OutreachModel, created.id)
            if rec:
                rec.status          = "failed"
                rec.delivery_status = "failed"
                rec.failure_reason  = error[:400] if error else "unknown"
                rec.lifecycle_status = "sent"  # stays at sent — not awaiting_response

        _write_activity(
            lead_id   = task.lead_id,
            atype     = "note",
            subject   = f"שגיאת שליחה ב-{task.channel}",
            notes     = error[:200] if error else "שגיאה לא ידועה",
            direction = "outbound",
            outcome   = "no_answer",
        )
        return True
    except Exception as e:
        log.error(f"[Outreach] record_failed error: {e}"); return False

def update_pipeline_status(outreach_id: str, status: str, notes: str = "") -> bool:
    try:
        from services.storage.db import get_session
        from services.storage.models.outreach import OutreachModel
        import datetime as dt
        with get_session() as s:
            r = s.get(OutreachModel, outreach_id)
            if not r: return False
            r.status = status
            if status == "sent": r.sent_at = dt.datetime.now(datetime.timezone.utc).isoformat()
            if status == "replied": r.replied_at = dt.datetime.now(datetime.timezone.utc).isoformat()
            if notes: r.notes = notes
            if status == "sent":
                days = 3 if r.attempt == 1 else 5
                r.next_followup = (dt.datetime.now(datetime.timezone.utc) + dt.timedelta(days=days)).isoformat()
        return True
    except Exception as e:
        log.error(f"[Outreach] update failed: {e}"); return False

def daily_outreach_summary() -> DailySummary:
    today = datetime.date.today().isoformat(); now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        from services.storage.repositories.outreach_repo import OutreachRepository
        from services.storage.repositories.lead_repo import LeadRepository
        repo = OutreachRepository(); due = repo.list_due_followup()
        leads = LeadRepository().list_all(); queue = build_outreach_queue(leads); top5 = prioritize_daily(queue, 5)
        pipeline = [PipelineEntry(outreach_id=o.id, lead_name=o.contact_name, phone=o.contact_phone or "", channel=o.channel, status=o.status, attempt=o.attempt, sent_at=o.sent_at or "", next_followup=o.next_followup or "", message_body=(o.message_body or "")[:100]) for o in due]
        return DailySummary(date=today, total_due=len(due), sent_today=0, replied_today=0, pending=len([o for o in due if o.status=="pending"]), overdue=len([o for o in due if (o.next_followup or "")<now]), top_priorities=top5, pipeline=pipeline)
    except Exception as e:
        log.error(f"[Outreach] summary failed: {e}")
        return DailySummary(date=today, total_due=0, sent_today=0, replied_today=0, pending=0, overdue=0, top_priorities=[], pipeline=[])


# ── OutreachEngineService — unified API for executor + scheduler ──────────────

class OutreachEngineService:
    """
    Thin service wrapper that exposes a stable method API over the module-level
    functions above. Used by executor handlers and the revenue scheduler.
    """

    def run_outreach_batch(self, goal_id: str) -> List[OutreachResult]:
        """Send initial outreach for all pending leads under a goal."""
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            from services.storage.repositories.goal_repo import GoalRepository
            leads = LeadRepository().list_all()
            goals = GoalRepository().list_active()
            queue = build_outreach_queue(leads, goals)
            # Filter to first-contact tasks only
            first_contact = [t for t in queue if t.attempt == 1]
            daily = prioritize_daily(first_contact, max_tasks=20)
            results = []
            for task in daily:
                task.goal_id = goal_id
                result = execute_outreach(task)
                if result.success:
                    record_outreach_sent(task)
                    update_pipeline_status(task.task_id, "sent")
                results.append(result)
            return results
        except Exception as e:
            log.error(f"[OutreachEngine] run_outreach_batch failed: {e}", exc_info=True)
            return []

    def run_followup_batch(self, goal_id: str) -> List[OutreachResult]:
        """Send due follow-ups for a given goal."""
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            from services.storage.repositories.outreach_repo import OutreachRepository
            import datetime as dt

            now   = dt.datetime.now(datetime.timezone.utc).isoformat()
            due   = OutreachRepository().list_due_followup()
            leads = LeadRepository().list_all()
            lead_map = {l.id: l for l in leads}

            results = []
            for record in due:
                lead = next((l for l in leads if l.name == record.contact_name), None)
                if not lead:
                    continue
                audience = _detect_audience(lead)
                attempt  = (record.attempt or 1) + 1
                if attempt > 3:
                    continue
                message   = build_followup_message(audience, lead.name, attempt)
                deep_link = _build_whatsapp_link(record.contact_phone or "", message)
                task = OutreachTask(
                    task_id=str(_uuid.uuid4()), lead_id=lead.id,
                    lead_name=lead.name, phone=record.contact_phone or "",
                    channel="whatsapp", message=message, audience=audience,
                    priority=2, urgency="today",
                    reason=f"follow-up #{attempt}", goal_id=goal_id,
                    attempt=attempt, deep_link=deep_link,
                )
                result = execute_outreach(task)
                if result.success:
                    record_outreach_sent(task)
                    update_pipeline_status(record.id, "sent")
                results.append(result)
            return results
        except Exception as e:
            log.error(f"[OutreachEngine] run_followup_batch failed: {e}", exc_info=True)
            return []

    def build_daily_summary(self) -> DailySummary:
        """Alias for module-level daily_outreach_summary."""
        return daily_outreach_summary()

    def get_followup_queue(self) -> List[PipelineEntry]:
        """Return all outreach records that are due for follow-up."""
        try:
            from services.storage.repositories.outreach_repo import OutreachRepository
            due = OutreachRepository().list_due_followup()
            return [
                PipelineEntry(
                    outreach_id=o.id, lead_name=o.contact_name,
                    phone=o.contact_phone or "", channel=o.channel,
                    status=o.status, attempt=o.attempt,
                    sent_at=o.sent_at or "", next_followup=o.next_followup or "",
                    message_body=(o.message_body or "")[:100],
                )
                for o in due
            ]
        except Exception as e:
            log.error(f"[OutreachEngine] get_followup_queue failed: {e}", exc_info=True)
            return []


outreach_engine = OutreachEngineService()
