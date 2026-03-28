"""
api/routes/crm.py — Revenue CRM endpoints.

Deals:
  GET    /api/crm/deals                  list active deals
  POST   /api/crm/deals                  create deal
  GET    /api/crm/deals/<id>             get deal + stage history
  PUT    /api/crm/deals/<id>             update deal fields
  POST   /api/crm/deals/<id>/stage       transition stage

Activities:
  POST   /api/crm/leads/<id>/activities  log activity (call/email/note)
  GET    /api/crm/leads/<id>/activities  list activities

Timeline:
  GET    /api/crm/leads/<id>/timeline    unified timeline

Calendar:
  GET    /api/crm/calendar/today         daily revenue plan
  GET    /api/crm/calendar/week          weekly calendar
  POST   /api/crm/calendar/events        create calendar event
"""

import datetime
import logging
import uuid

import pytz
from flask import Blueprint, request

from api.middleware import require_auth, log_request, ok, _error

log   = logging.getLogger(__name__)
bp    = Blueprint("crm", __name__)
_IL   = pytz.timezone("Asia/Jerusalem")


# ── Deals ──────────────────────────────────────────────────────────────────────

@bp.route("/crm/deals", methods=["GET"])
@require_auth
@log_request
def list_deals():
    stage = request.args.get("stage")
    try:
        from services.storage.db import get_session
        from services.storage.models.deal import DealModel
        with get_session() as s:
            q = s.query(DealModel)
            if stage:
                q = q.filter_by(stage=stage)
            deals = q.order_by(DealModel.value_ils.desc()).limit(100).all()
        return ok({"deals": [d.to_dict() for d in deals], "total": len(deals)})
    except Exception as e:
        return _error(str(e), 500)


@bp.route("/crm/deals", methods=["POST"])
@require_auth
@log_request
def create_deal():
    body = request.get_json(silent=True) or {}
    lead_id = body.get("lead_id", "").strip()
    title   = body.get("title", "").strip()
    if not lead_id or not title:
        return _error("lead_id and title are required", 400)

    from services.storage.db import get_session
    from services.storage.models.deal import DealModel, DEAL_STAGES
    from services.storage.models.base import new_uuid

    stage = body.get("stage", "new")
    if stage not in DEAL_STAGES:
        return _error(f"stage must be one of {DEAL_STAGES}", 400)

    deal_id = new_uuid()
    with get_session() as s:
        s.add(DealModel(
            id=deal_id,
            lead_id=lead_id,
            title=title,
            stage=stage,
            value_ils=int(body.get("value_ils", 0)),
            probability=float(body.get("probability", 0.20)),
            expected_close_date=body.get("expected_close_date"),
            source=body.get("source"),
            next_action=body.get("next_action"),
        ))
    return ok({"deal_id": deal_id, "stage": stage}, status=201)


@bp.route("/crm/deals/<deal_id>", methods=["GET"])
@require_auth
@log_request
def get_deal(deal_id: str):
    from services.storage.db import get_session
    from services.storage.models.deal import DealModel
    from services.storage.models.stage_history import StageHistoryModel
    with get_session() as s:
        deal = s.query(DealModel).filter_by(id=deal_id).first()
        if not deal:
            return _error(f"deal '{deal_id}' not found", 404)
        deal_data = deal.to_dict()
        history = (s.query(StageHistoryModel)
                   .filter_by(deal_id=deal_id)
                   .order_by(StageHistoryModel.created_at)
                   .all())
        history_data = [h.to_dict() for h in history]
    return ok({"deal": deal_data, "stage_history": history_data})


@bp.route("/crm/deals/<deal_id>", methods=["PUT"])
@require_auth
@log_request
def update_deal(deal_id: str):
    body = request.get_json(silent=True) or {}
    from services.storage.db import get_session
    from services.storage.models.deal import DealModel
    with get_session() as s:
        deal = s.query(DealModel).filter_by(id=deal_id).first()
        if not deal:
            return _error(f"deal '{deal_id}' not found", 404)
        for field_name in ("title", "value_ils", "probability", "expected_close_date",
                           "next_action", "next_action_at", "close_reason", "source"):
            if field_name in body:
                setattr(deal, field_name, body[field_name])
    return ok({"deal_id": deal_id, "updated": list(body.keys())})


@bp.route("/crm/deals/<deal_id>/stage", methods=["POST"])
@require_auth
@log_request
def transition_stage(deal_id: str):
    body     = request.get_json(silent=True) or {}
    to_stage = (body.get("stage") or "").strip()
    reason   = body.get("reason", "")
    changed_by = body.get("changed_by", "api")

    from services.storage.models.deal import DEAL_STAGES
    if to_stage not in DEAL_STAGES:
        return _error(f"stage must be one of {DEAL_STAGES}", 400)

    from services.storage.db import get_session
    from services.storage.models.deal import DealModel
    from services.storage.models.stage_history import StageHistoryModel
    from services.storage.models.base import new_uuid

    now_il = datetime.datetime.now(_IL).isoformat()

    with get_session() as s:
        deal = s.query(DealModel).filter_by(id=deal_id).first()
        if not deal:
            return _error(f"deal '{deal_id}' not found", 404)
        from_stage = deal.stage
        if from_stage == to_stage:
            return _error(f"deal already in stage '{to_stage}'", 422)

        deal.stage = to_stage
        if to_stage in ("won", "lost"):
            deal.closed_at    = now_il
            deal.close_reason = reason
            deal.probability  = 1.0 if to_stage == "won" else 0.0

        s.add(StageHistoryModel(
            id=new_uuid(),
            deal_id=deal_id,
            lead_id=deal.lead_id,
            from_stage=from_stage,
            to_stage=to_stage,
            reason=reason,
            changed_by=changed_by,
            changed_at_il=now_il,
        ))

    log.info(f"[CRM] deal {deal_id}: {from_stage} → {to_stage}")
    return ok({"deal_id": deal_id, "from_stage": from_stage,
               "to_stage": to_stage, "changed_at_il": now_il})


# ── Activities ─────────────────────────────────────────────────────────────────

@bp.route("/crm/leads/<lead_id>/activities", methods=["POST"])
@require_auth
@log_request
def log_activity(lead_id: str):
    body = request.get_json(silent=True) or {}
    activity_type = body.get("activity_type", "note")
    from services.storage.models.activity import ACTIVITY_TYPES
    if activity_type not in ACTIVITY_TYPES:
        return _error(f"activity_type must be one of {ACTIVITY_TYPES}", 400)

    from services.storage.db import get_session
    from services.storage.models.activity import ActivityModel
    from services.storage.models.base import new_uuid

    act_id = new_uuid()
    now_il = datetime.datetime.now(_IL).isoformat()

    with get_session() as s:
        s.add(ActivityModel(
            id=act_id,
            lead_id=lead_id,
            deal_id=body.get("deal_id"),
            activity_type=activity_type,
            direction=body.get("direction", "outbound"),
            subject=body.get("subject"),
            notes=body.get("notes"),
            outcome=body.get("outcome"),
            duration_sec=body.get("duration_sec"),
            performed_by=body.get("performed_by", "operator"),
            performed_at_il=body.get("performed_at_il", now_il),
        ))
    return ok({"activity_id": act_id, "lead_id": lead_id}, status=201)


@bp.route("/crm/leads/<lead_id>/activities", methods=["GET"])
@require_auth
@log_request
def list_activities(lead_id: str):
    from services.storage.db import get_session
    from services.storage.models.activity import ActivityModel
    with get_session() as s:
        rows = (s.query(ActivityModel)
                .filter_by(lead_id=lead_id)
                .order_by(ActivityModel.created_at.desc())
                .limit(50).all())
    return ok({"activities": [r.to_dict() for r in rows], "total": len(rows)})


# ── Timeline ───────────────────────────────────────────────────────────────────

@bp.route("/crm/leads/<lead_id>/timeline", methods=["GET"])
@require_auth
@log_request
def get_timeline(lead_id: str):
    limit = min(int(request.args.get("limit", 30)), 100)
    from services.crm.timeline import build_timeline
    events = build_timeline(lead_id, limit=limit)
    return ok({"lead_id": lead_id, "total": len(events),
               "events": [e.to_dict() for e in events]})


# ── Calendar ───────────────────────────────────────────────────────────────────

@bp.route("/crm/calendar/today", methods=["GET"])
@require_auth
@log_request
def daily_plan():
    budget = int(request.args.get("budget_minutes", 240))
    from services.crm.daily_plan import build_daily_plan
    plan = build_daily_plan(budget_minutes=budget)
    return ok(plan.to_dict())


@bp.route("/crm/calendar/week", methods=["GET"])
@require_auth
@log_request
def weekly_calendar():
    from services.crm.weekly_calendar import build_weekly_calendar
    cal = build_weekly_calendar()
    return ok(cal.to_dict())


@bp.route("/crm/calendar/events", methods=["POST"])
@require_auth
@log_request
def create_event():
    body = request.get_json(silent=True) or {}
    lead_id    = body.get("lead_id", "").strip()
    title      = body.get("title", "").strip()
    starts_at  = body.get("starts_at_il", "").strip()
    if not lead_id or not title or not starts_at:
        return _error("lead_id, title, starts_at_il are required", 400)

    from services.storage.db import get_session
    from services.storage.models.calendar_event import CalendarEventModel
    from services.storage.models.base import new_uuid

    ev_id = new_uuid()
    with get_session() as s:
        s.add(CalendarEventModel(
            id=ev_id,
            lead_id=lead_id,
            deal_id=body.get("deal_id"),
            title=title,
            event_type=body.get("event_type", "meeting"),
            starts_at_il=starts_at,
            ends_at_il=body.get("ends_at_il"),
            location=body.get("location"),
            notes=body.get("notes"),
            created_by=body.get("created_by", "api"),
        ))
    return ok({"event_id": ev_id, "lead_id": lead_id}, status=201)


# ── Lead Full Record View (Batch 7) ────────────────────────────────────────────

@bp.route("/crm/leads/<lead_id>/full", methods=["GET"])
@require_auth
@log_request
def lead_full(lead_id: str):
    """
    Full record view: lead + open deals + unified timeline + AI summary.
    GET /api/crm/leads/<lead_id>/full
    """
    try:
        from services.storage.db import get_session
        from services.storage.models.lead import LeadModel
        from services.storage.models.deal import DealModel
        from services.storage.models.activity import ActivityModel
        from services.storage.models.message import MessageModel
        from services.storage.models.stage_history import StageHistoryModel
        from services.storage.models.calendar_event import CalendarEventModel
        from services.engines.priority_engine import compute_lead_score

        with get_session() as s:
            lead = s.query(LeadModel).filter_by(id=lead_id).first()
            if not lead:
                return _error("lead not found", 404)

            deals   = s.query(DealModel).filter_by(lead_id=lead_id).all()
            acts    = s.query(ActivityModel).filter_by(lead_id=lead_id)\
                       .order_by(ActivityModel.created_at.desc()).limit(30).all()
            msgs    = s.query(MessageModel).filter_by(lead_id=lead_id)\
                       .order_by(MessageModel.created_at.desc()).limit(20).all()
            stages  = s.query(StageHistoryModel).filter_by(lead_id=lead_id)\
                       .order_by(StageHistoryModel.created_at.desc()).limit(15).all()
            events  = s.query(CalendarEventModel).filter_by(lead_id=lead_id)\
                       .order_by(CalendarEventModel.starts_at_il.desc()).limit(10).all()

            lead_dict  = _lead_to_dict(lead)
            deal_dicts = [d.to_dict() for d in deals]
            ev_dicts   = [e.to_dict() for e in events]

        priority = compute_lead_score(lead_dict, deals=deal_dicts, events=ev_dicts)
        timeline = _build_timeline(acts, msgs, stages, events)
        summary  = _ai_summary(lead_dict, deal_dicts, acts)

        return ok({
            "lead":           lead_dict,
            "open_deals":     [d for d in deal_dicts if d["stage"] not in ("won", "lost")],
            "timeline":       timeline,
            "priority_score": priority,
            "ai_summary":     summary,
        })
    except Exception as e:
        log.exception("[CRM] lead_full error")
        return _error(str(e), 500)


# ── Helpers for lead_full ──────────────────────────────────────────────────────

def _lead_to_dict(lead) -> dict:
    return {
        "id":              lead.id,
        "name":            lead.name,
        "company":         getattr(lead, "company", None),
        "phone":           lead.phone,
        "email":           lead.email,
        "city":            lead.city,
        "source":          lead.source,
        "status":          lead.status,
        "sector":          lead.sector,
        "domain":          getattr(lead, "domain", None),
        "score":           lead.score,
        "potential_value": getattr(lead, "potential_value", 0) or 0,
        "owner":           getattr(lead, "owner", None),
        "next_action":     getattr(lead, "next_action", None),
        "next_action_due": getattr(lead, "next_action_due", None),
        "last_activity_at": getattr(lead, "last_activity_at", None) or lead.last_contact,
        "priority_score":  getattr(lead, "priority_score", 0) or 0,
        "notes":           lead.notes,
        "created_at":      str(lead.created_at) if lead.created_at else None,
        "updated_at":      str(lead.updated_at) if lead.updated_at else None,
    }


def _build_timeline(acts, msgs, stages, events) -> list:
    _ICON = {"call": "📞", "email": "📧", "whatsapp": "📱", "meeting": "🤝",
             "note": "📝", "demo": "🎯"}
    items = []
    for a in acts:
        d = a.to_dict()
        items.append({
            "type":  d["activity_type"],
            "icon":  _ICON.get(d["activity_type"], "●"),
            "title": d.get("subject") or d["activity_type"],
            "body":  d.get("notes") or "",
            "actor": d.get("performed_by") or "",
            "ts":    d.get("created_at") or "",
        })
    for m in msgs:
        d = m.to_dict()
        items.append({
            "type":  "message",
            "icon":  "💬",
            "title": d.get("subject") or f"{d['channel']} {d['direction']}",
            "body":  (d.get("body") or "")[:120],
            "actor": d.get("direction") or "",
            "ts":    d.get("created_at") or "",
        })
    for sh in stages:
        d = sh.to_dict()
        items.append({
            "type":  "stage_change",
            "icon":  "🔄",
            "title": f"שינוי שלב: {d['from_stage']} → {d['to_stage']}",
            "body":  d.get("reason") or "",
            "actor": d.get("changed_by") or "",
            "ts":    d.get("created_at") or "",
        })
    for ev in events:
        d = ev.to_dict()
        items.append({
            "type":  "calendar",
            "icon":  "📅",
            "title": d.get("title") or "אירוע",
            "body":  d.get("notes") or "",
            "actor": d.get("created_by") or "",
            "ts":    d.get("starts_at_il") or d.get("created_at") or "",
        })
    items.sort(key=lambda x: x["ts"] or "0", reverse=True)
    return items[:30]


def _ai_summary(lead: dict, deals: list, acts) -> dict:
    open_deals = [d for d in deals if d["stage"] not in ("won", "lost")]
    lost_deals  = [d for d in deals if d["stage"] == "lost"]

    what_they_want = ""
    if open_deals:
        top = max(open_deals, key=lambda d: d.get("value_ils", 0) or 0)
        what_they_want = f"עסקה בשלב {top['stage']} בשווי ₪{top.get('value_ils',0):,}"
    elif lead.get("notes"):
        what_they_want = str(lead["notes"])[:100]
    else:
        what_they_want = "לא ידוע — השלם פרטי ליד"

    risk = ""
    if not lead.get("next_action"):
        risk = "אין פעולה הבאה מוגדרת — סיכון לאיבוד קשר"
    elif lead.get("status") in ("קר", "לא רלוונטי"):
        risk = "ליד לא פעיל — בדוק רלוונטיות לפני פנייה"

    objection = ""
    if lost_deals:
        reason = lost_deals[-1].get("lost_reason") or lost_deals[-1].get("close_reason") or ""
        objection = f"עסקה קודמת אבדה: {reason[:80]}" if reason else "עסקה קודמת לא נסגרה"

    return {
        "what_they_want":             what_they_want,
        "what_was_promised":          "בדוק ציר הפעילות",
        "objection":                  objection or "לא ידוע",
        "risk":                       risk or "ללא אזהרות פעילות",
        "next_action_recommendation": lead.get("next_action") or "הגדר פעולה הבאה",
    }


# ── Batch 8: Operational Inbox ────────────────────────────────────────────────

@bp.route("/crm/inbox", methods=["GET"])
@require_auth
def inbox():
    """
    GET /api/crm/inbox
    Returns inbound messages from the last 30 days grouped by lead,
    with a needs_attention flag (no outbound reply within 24h).
    Query params: ?limit=50&days=30
    """
    import datetime as _dt
    from services.storage.db       import get_session
    from services.storage.models.message import MessageModel
    from services.storage.models.lead    import LeadModel

    limit = min(int(request.args.get("limit", 50)), 200)
    days  = min(int(request.args.get("days",  30)), 90)
    cutoff = (_dt.datetime.utcnow() - _dt.timedelta(days=days)).isoformat()
    now    = _dt.datetime.utcnow()

    try:
        with get_session() as s:
            # All inbound messages within window
            inbound = (
                s.query(MessageModel)
                .filter(
                    MessageModel.direction == "inbound",
                    MessageModel.sent_at_il >= cutoff,
                )
                .order_by(MessageModel.sent_at_il.desc())
                .limit(limit)
                .all()
            )

            # For each unique lead_id, check if there's a recent outbound reply
            lead_ids = list({m.lead_id for m in inbound if m.lead_id})
            outbound_lead_ids = set()
            if lead_ids:
                cutoff_24h = (_dt.datetime.utcnow() - _dt.timedelta(hours=24)).isoformat()
                recent_out = (
                    s.query(MessageModel.lead_id)
                    .filter(
                        MessageModel.direction == "outbound",
                        MessageModel.lead_id.in_(lead_ids),
                        MessageModel.sent_at_il >= cutoff_24h,
                    )
                    .distinct()
                    .all()
                )
                outbound_lead_ids = {r.lead_id for r in recent_out}

            # Fetch lead names
            lead_map = {}
            if lead_ids:
                leads = s.query(LeadModel.id, LeadModel.name, LeadModel.phone).filter(
                    LeadModel.id.in_(lead_ids)
                ).all()
                lead_map = {l.id: {"name": l.name, "phone": l.phone} for l in leads}

        threads = {}
        for m in inbound:
            lid = m.lead_id or "unknown"
            if lid not in threads:
                linfo = lead_map.get(lid, {})
                threads[lid] = {
                    "lead_id":        lid,
                    "lead_name":      linfo.get("name", "לא ידוע"),
                    "lead_phone":     linfo.get("phone", ""),
                    "needs_attention": lid not in outbound_lead_ids,
                    "message_count":  0,
                    "last_message":   None,
                    "messages":       [],
                }
            threads[lid]["message_count"] += 1
            msg_dict = {
                "id":        m.id,
                "channel":   m.channel,
                "direction": m.direction,
                "subject":   m.subject,
                "body":      (m.body or "")[:300],
                "status":    m.status,
                "sent_at":   m.sent_at_il,
            }
            if threads[lid]["last_message"] is None:
                threads[lid]["last_message"] = msg_dict
            threads[lid]["messages"].append(msg_dict)

        # Sort: needs_attention first, then by last message time
        result = sorted(
            threads.values(),
            key=lambda t: (
                not t["needs_attention"],
                -(t["last_message"]["sent_at"] or "0") if t["last_message"] else "0",
            ),
        )

        attention_count = sum(1 for t in result if t["needs_attention"])
        return ok({
            "total_threads":    len(result),
            "attention_count":  attention_count,
            "threads":          result,
        })

    except Exception as e:
        log.error(f"[Inbox] failed: {e}", exc_info=True)
        return _error(str(e), 500)
