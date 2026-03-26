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
        repo.update_status(lead_id, body["status"])
    if "score" in body:
        repo.update_score(lead_id, int(body["score"]))

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
        "created_at":   str(lead.created_at) if lead.created_at else None,
    }
