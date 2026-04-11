"""
api/routes/lead_ops.py — Lead Operations API
Phase 12: Lead Acquisition OS

Endpoints:
  POST /api/lead_ops/discover       — run acquisition from goal + signals
  POST /api/lead_ops/inbound        — process inbound lead
  POST /api/lead_ops/website        — run website growth analysis
  GET  /api/lead_ops/queue          — get current work queue
  GET  /api/lead_ops/discovery_plan — get strategy from goal (no DB)
  POST /api/lead_ops/draft          — draft a message for a lead
  GET  /api/lead_ops/status         — summary counts
"""

import logging
from flask import Blueprint, request, jsonify
from api.middleware import require_api_key

log = logging.getLogger(__name__)
bp = Blueprint("lead_ops", __name__)


@bp.route("/lead_ops/discover", methods=["POST"])
@require_api_key
def discover_leads():
    """Run lead acquisition pipeline from a business goal."""
    data    = request.get_json(silent=True) or {}
    goal    = data.get("goal") or ""
    signals = data.get("signals") or []

    if not goal:
        return jsonify({"success": False, "error": "goal required"}), 400

    try:
        from engines.lead_acquisition_engine import run_acquisition
        from services.storage.db import get_session
        with get_session() as session:
            result = run_acquisition(goal=goal, signals=signals, session=session)
        return jsonify({
            "success":          True,
            "session_id":       result.session_id,
            "total_discovered": result.total_discovered,
            "new_leads":        result.new_leads,
            "duplicates":       result.duplicates,
            "work_queue":       result.work_queue,
            "discovery_plan":   result.discovery_plan,
            "errors":           result.errors,
        })
    except Exception as e:
        log.error(f"[lead_ops/discover] {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/lead_ops/inbound", methods=["POST"])
@require_api_key
def process_inbound():
    """Process an inbound lead (from form/Telegram/WhatsApp)."""
    data = request.get_json(silent=True) or {}
    if not data.get("name") and not data.get("phone"):
        return jsonify({"success": False, "error": "name or phone required"}), 400
    try:
        from engines.lead_acquisition_engine import process_inbound as _process
        from services.storage.db import get_session
        with get_session() as session:
            lead_id = _process(lead_data=data, session=session)
        return jsonify({"success": True, "lead_id": lead_id})
    except Exception as e:
        log.error(f"[lead_ops/inbound] {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/lead_ops/website", methods=["POST"])
@require_api_key
def website_analysis():
    """Run website growth analysis."""
    data = request.get_json(silent=True) or {}
    url  = data.get("url") or ""
    html = data.get("html") or ""
    if not url and not html:
        return jsonify({"success": False, "error": "url or html required"}), 400
    try:
        from engines.lead_acquisition_engine import run_website_analysis
        result = run_website_analysis(url=url, html=html)
        return jsonify({
            "success":             True,
            "url":                 result.url,
            "audit_score":         result.audit_score,
            "lead_capture_score":  result.lead_capture_score,
            "top_recommendations": result.top_recommendations,
            "content_gaps":        result.content_gaps,
            "priority_plan":       result.priority_plan,
            "seo":                 result.seo,
        })
    except Exception as e:
        log.error(f"[lead_ops/website] {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/lead_ops/queue", methods=["GET"])
@require_api_key
def lead_ops_queue():
    """Return current lead ops work queue."""
    limit = int(request.args.get("limit") or 50)
    try:
        from services.storage.db import get_session
        from services.storage.repositories.lead_repo import LeadRepository
        with get_session() as session:
            repo  = LeadRepository(session)
            leads = repo.list_all(limit=limit)

            def _d(l):
                return {
                    "id":             l.id,
                    "name":           l.name,
                    "status":         l.status,
                    "score":          l.score,
                    "source_type":    getattr(l, "source_type", None),
                    "is_inbound":     str(getattr(l, "is_inbound", "false")).lower() in ("true", "1"),
                    "outreach_action": getattr(l, "outreach_action", None),
                    "outreach_draft":  getattr(l, "outreach_draft", None),
                    "next_action":    l.next_action,
                    "next_action_due": l.next_action_due,
                    "meeting_suggested": str(getattr(l, "meeting_suggested", "false")).lower() in ("true", "1"),
                    "city":           l.city,
                    "phone":          l.phone,
                    "segment":        getattr(l, "segment", None),
                    "geo_fit_score":  getattr(l, "geo_fit_score", 0),
                }

            discovered    = [_d(l) for l in leads if getattr(l, "source_type", None) and
                             str(getattr(l, "is_inbound", "false")).lower() not in ("true", "1")]
            inbound       = [_d(l) for l in leads if str(getattr(l, "is_inbound", "false")).lower() in ("true", "1")]
            pending       = [_d(l) for l in leads if getattr(l, "outreach_draft", None)
                             and l.status not in ("סגור זכה", "לא רלוונטי")]
            needing_meeting = [_d(l) for l in leads if str(getattr(l, "meeting_suggested", "false")).lower() in ("true", "1")]

        return jsonify({
            "success":    True,
            "discovered": discovered,
            "inbound":    inbound,
            "pending_action": pending,
            "meeting_suggestions": needing_meeting,
            "counts": {
                "discovered": len(discovered),
                "inbound":    len(inbound),
                "pending_action": len(pending),
                "meeting_suggestions": len(needing_meeting),
            },
        })
    except Exception as e:
        log.error(f"[lead_ops/queue] {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/lead_ops/discovery_plan", methods=["GET", "POST"])
@require_api_key
def discovery_plan():
    """Return discovery strategy for a goal — no DB required."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        goal = data.get("goal") or ""
    else:
        goal = request.args.get("goal") or ""

    if not goal:
        return jsonify({"success": False, "error": "goal required"}), 400

    try:
        from skills.source_discovery import discover_sources, explain_source_strategy
        plan = discover_sources(goal)
        return jsonify({
            "success":           True,
            "goal":              plan.goal,
            "segments":          plan.segments,
            "source_types":      plan.source_types,
            "communities":       [
                {"name": c.name, "source_type": c.source_type,
                 "url_hint": c.url_hint, "signal_type": c.signal_type}
                for c in plan.communities
            ],
            "search_intents":    [
                {"query": i.query, "source_type": i.source_type, "priority": i.priority}
                for i in plan.search_intents
            ],
            "outreach_strategy": plan.outreach_strategy,
            "explanation":       explain_source_strategy(plan),
            "notes":             plan.notes,
        })
    except Exception as e:
        log.error(f"[lead_ops/discovery_plan] {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/lead_ops/draft", methods=["POST"])
@require_api_key
def draft_message():
    """Draft an outreach message for a lead."""
    data        = request.get_json(silent=True) or {}
    lead        = data.get("lead") or {}
    action_type = data.get("action_type") or "first_contact"
    extra       = data.get("extra") or {}

    try:
        from skills.outreach_intelligence import (
            draft_first_contact, draft_followup,
            draft_meeting_request, draft_inbound_response, draft_comment_reply,
        )
        drafters = {
            "first_contact":   lambda: draft_first_contact(lead),
            "follow_up":       lambda: draft_followup(lead, extra),
            "meeting_request": lambda: draft_meeting_request(lead),
            "inbound_response": lambda: draft_inbound_response(lead, extra.get("inbound_text", "")),
            "comment_reply":   lambda: draft_comment_reply(extra, lead),
        }
        fn = drafters.get(action_type, drafters["first_contact"])
        draft = fn()
        return jsonify({
            "success":     True,
            "subject":     draft.subject,
            "body":        draft.body,
            "language":    draft.language,
            "channel":     draft.channel,
            "action_type": draft.action_type,
            "tone":        draft.tone,
            "requires_approval": draft.requires_approval,
            "notes":       draft.notes,
        })
    except Exception as e:
        log.error(f"[lead_ops/draft] {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/lead_ops/status", methods=["GET"])
@require_api_key
def lead_ops_status():
    """Return lead ops summary counts for dashboard widget."""
    try:
        from services.storage.db import get_session
        from services.storage.repositories.lead_repo import LeadRepository
        with get_session() as session:
            repo  = LeadRepository(session)
            leads = repo.list_all(limit=200)
            discovered  = sum(1 for l in leads if getattr(l, "source_type", None) and
                              str(getattr(l, "is_inbound", "false")).lower() not in ("true", "1"))
            inbound     = sum(1 for l in leads if str(getattr(l, "is_inbound", "false")).lower() in ("true", "1"))
            pending     = sum(1 for l in leads if getattr(l, "outreach_draft", None)
                              and l.status not in ("סגור זכה", "לא רלוונטי"))
            meetings    = sum(1 for l in leads if str(getattr(l, "meeting_suggested", "false")).lower() in ("true", "1"))
        return jsonify({
            "success":    True,
            "discovered": discovered,
            "inbound":    inbound,
            "pending_action": pending,
            "meeting_suggestions": meetings,
        })
    except Exception as e:
        log.error(f"[lead_ops/status] {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
