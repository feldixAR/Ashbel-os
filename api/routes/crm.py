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
