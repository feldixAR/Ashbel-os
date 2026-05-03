"""
Leads / CRM routes.

GET  /api/leads                 list leads (query: status, min_score)
POST /api/leads                 create lead
PATCH /api/leads/<lead_id>      update status or notes
"""

import logging
from flask import Blueprint, request
from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("leads", __name__)


@bp.route("/leads", methods=["GET"])
@require_auth
@log_request
def list_leads():
    from services.storage.repositories.lead_repo import LeadRepository
    repo      = LeadRepository()
    status    = request.args.get("status")
    min_score = request.args.get("min_score", type=int)

    leads = repo.list_all()
    if status:
        leads = [l for l in leads if l.status == status]
    if min_score is not None:
        leads = [l for l in leads if (l.score or 0) >= min_score]

    leads = sorted(leads, key=lambda l: l.score or 0, reverse=True)

    return ok({
        "leads": [_serialize_lead(l) for l in leads],
        "total": len(leads),
    })


@bp.route("/leads", methods=["POST"])
@require_auth
@log_request
def create_lead():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()

    if not name:
        return _error("field 'name' is required", 400)

    from services.storage.repositories.lead_repo import LeadRepository
    from events.event_bus                         import event_bus
    import events.event_types                     as ET

    lead = LeadRepository().create(
        name=name,
        city=(body.get("city")    or "").strip(),
        phone=(body.get("phone")  or "").strip(),
        email=(body.get("email")  or "").strip(),
        source=(body.get("source") or "manual").strip(),
        sector=(body.get("sector") or "").strip(),
        notes=(body.get("notes")  or "").strip(),
    )

    event_bus.publish(
        ET.LEAD_CREATED,
        payload={"lead_id": lead.id, "name": lead.name,
                 "source": lead.source},
    )

    return ok({"lead": _serialize_lead(lead)}, status=201)


@bp.route("/leads/<lead_id>", methods=["PATCH"])
@require_auth
@log_request
def update_lead(lead_id: str):
    body   = request.get_json(silent=True) or {}
    repo   = __import__("services.storage.repositories.lead_repo",
                         fromlist=["LeadRepository"]).LeadRepository()
    lead   = repo.get(lead_id)

    if not lead:
        return _error(f"lead '{lead_id}' not found", 404)

    if "status" in body:
        old_status = lead.status
        repo.update_status(lead_id, body["status"])
        _log_lead_action(
            lead_id,
            "Lead status changed",
            f"{old_status} -> {body['status']}",
            outcome="completed",
        )
    if "score" in body:
        old_score = lead.score
        repo.update_score(lead_id, int(body["score"]))
        _log_lead_action(
            lead_id,
            "Lead score changed",
            f"{old_score} -> {int(body['score'])}",
            outcome="completed",
        )

    lead = repo.get(lead_id)
    return ok({"lead": _serialize_lead(lead)})


# ── Serializer ────────────────────────────────────────────────────────────────

def _serialize_lead(lead) -> dict:
    return {
        "id":           lead.id,
        "name":         lead.name,
        "city":         lead.city,
        "phone":        lead.phone,
        "email":        lead.email,
        "sector":       lead.sector,
        "source":       lead.source,
        "status":       lead.status,
        "score":        lead.score,
        "attempts":     lead.attempts,
        "last_contact": lead.last_contact,
        "response":     lead.response,
        "notes":        lead.notes,
        "company":      getattr(lead, "company", None),
        "source_type":  getattr(lead, "source_type", None),
        "source_file":  getattr(lead, "source_file", None),
        "import_batch": getattr(lead, "import_batch", None),
        "work_type":    getattr(lead, "work_type", None),
        "project_stage": getattr(lead, "project_stage", None),
        "estimated_value": getattr(lead, "estimated_value", 0),
        "address":      getattr(lead, "address", None),
        "decision_maker": getattr(lead, "decision_maker", None),
        "priority":     getattr(lead, "priority", None),
        "score_reason": getattr(lead, "score_reason", None),
        "next_action":  getattr(lead, "next_action", None),
        "next_action_due": getattr(lead, "next_action_due", None),
        "proposal_readiness": {
            "ready_for_proposal": _as_bool(getattr(lead, "ready_for_proposal", False)),
            "missing_photos": _as_bool(getattr(lead, "missing_photos", True)),
            "missing_plans": _as_bool(getattr(lead, "missing_plans", True)),
            "missing_measurements": _as_bool(getattr(lead, "missing_measurements", True)),
            "missing_address": _as_bool(getattr(lead, "missing_address", True)),
            "missing_decision_maker": _as_bool(getattr(lead, "missing_decision_maker", True)),
            "missing_budget": _as_bool(getattr(lead, "missing_budget", True)),
            "missing_project_stage": _as_bool(getattr(lead, "missing_project_stage", True)),
            "proposal_followup_date": getattr(lead, "proposal_followup_date", None),
            "proposal_metadata": getattr(lead, "proposal_metadata", None) or {},
        },
        "created_at":   str(lead.created_at) if lead.created_at else None,
    }


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "1", "yes", "כן")


def _log_lead_action(lead_id: str, subject: str, notes: str, outcome: str = "completed") -> None:
    try:
        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel
        with get_session() as s:
            s.add(ActivityModel(
                lead_id=lead_id,
                activity_type="note",
                direction="inbound",
                subject=subject,
                notes=notes,
                outcome=outcome,
                performed_by="operator",
            ))
    except Exception as e:
        log.error(f"[leads] activity log failed: {e}")
