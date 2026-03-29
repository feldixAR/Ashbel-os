"""
Phase 11 — GET /api/daily_revenue_queue
Returns all active leads scored and sorted by Phase 11 priority formula.
"""
import logging
from flask import Blueprint, request, jsonify
from api.middleware import require_auth

log = logging.getLogger(__name__)
bp = Blueprint("revenue_queue", __name__)


@bp.route("/daily_revenue_queue", methods=["GET"])
@require_auth
def daily_revenue_queue():
    try:
        from services.storage.repositories.lead_repo import LeadRepository
        from services.storage.models.deal import DealModel
        from services.storage.db import get_session
        from engines.phase11_engine import build_revenue_queue

        leads = LeadRepository().list_all()

        # Build lead_id → latest deal map in one query
        with get_session() as s:
            all_deals = s.query(DealModel).filter(
                DealModel.stage.notin_(["won", "lost"])
            ).all()

        deals_by_lead: dict = {}
        for d in all_deals:
            # Keep deal with highest value per lead
            existing = deals_by_lead.get(d.lead_id)
            if existing is None or (d.value_ils or 0) > (existing.value_ils or 0):
                deals_by_lead[d.lead_id] = d

        queue = build_revenue_queue(leads, deals_by_lead)

        # Optional limit param
        limit = request.args.get("limit", type=int)
        if limit:
            queue = queue[:limit]

        return jsonify({
            "success": True,
            "total":   len(queue),
            "queue": [
                {
                    "lead_id":          r.lead_id,
                    "lead_name":        r.lead_name,
                    "priority_score":   r.priority_score,
                    "priority_reason":  r.priority_reason,
                    "business_state":   r.business_state,
                    "blocked_state":    r.blocked_state,
                    "blocked_reason":   r.blocked_reason,
                    "next_best_action": r.next_best_action,
                    "next_action_at":   r.next_action_at,
                }
                for r in queue
            ],
        })
    except Exception as e:
        log.exception("[Phase11] daily_revenue_queue error")
        return jsonify({"success": False, "error": str(e)}), 500
