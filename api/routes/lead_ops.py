"""
api/routes/lead_ops.py — Lead Operations API
Phase 12–14: Lead Acquisition OS

Endpoints:
  POST /api/lead_ops/discover          — run acquisition from goal + signals
  POST /api/lead_ops/inbound           — process inbound lead
  POST /api/lead_ops/website           — run website growth analysis
  GET  /api/lead_ops/queue             — get current work queue
  GET  /api/lead_ops/discovery_plan    — get strategy from goal (no DB)
  POST /api/lead_ops/draft             — draft a message for a lead
  GET  /api/lead_ops/status            — summary counts
  GET  /api/lead_ops/brief/<id>        — AI briefing for a specific lead
  POST /api/lead_ops/batch_score       — batch score unscored leads
  POST /api/lead_ops/execute/<id>      — execute an approved outreach action
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
        result = run_acquisition(goal=goal, signals=signals)
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
        lead_id = _process(lead_data=data)
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
        from services.storage.repositories.lead_repo import LeadRepository
        repo  = LeadRepository()
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
        from services.storage.repositories.lead_repo import LeadRepository
        repo  = LeadRepository()
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


# ── Phase 14: Brief / Batch Score / Execute ───────────────────────────────────

@bp.route("/lead_ops/brief/<lead_id>", methods=["GET"])
@require_api_key
def lead_brief(lead_id: str):
    """
    Return an AI-generated briefing for a specific lead.
    Uses Haiku for cheap, fast analysis — deterministic fallback always available.
    """
    try:
        from services.storage.repositories.lead_repo import LeadRepository
        from skills.outreach_intelligence import choose_action, choose_timing
        from skills.israeli_context import is_good_timing, get_best_send_window, geo_fit, get_hebrew_tone
        import datetime

        repo = LeadRepository()
        lead = repo.get(lead_id)
        if not lead:
            return jsonify({"success": False, "error": "lead not found"}), 404

        lead_dict = {
            "id":            lead.id,
            "name":          lead.name,
            "phone":         lead.phone,
            "email":         lead.email,
            "city":          lead.city,
            "company":       lead.company,
            "status":        lead.status,
            "score":         lead.score,
            "source_type":   getattr(lead, "source_type", ""),
            "segment":       getattr(lead, "segment", ""),
            "is_inbound":    str(getattr(lead, "is_inbound", "false")).lower() in ("true", "1"),
            "outreach_action": getattr(lead, "outreach_action", ""),
            "notes":         getattr(lead, "notes", ""),
        }

        # Deterministic signals (0 tokens)
        now         = datetime.datetime.now()
        good_time   = is_good_timing(now)
        send_window = get_best_send_window(now)
        city_fit    = geo_fit(lead.city or "")
        tone        = get_hebrew_tone(lead_dict.get("segment") or "")
        action      = choose_action(lead_dict)
        timing      = choose_timing(lead_dict)

        # AI briefing summary (Haiku — cheap)
        ai_summary = _build_lead_briefing(lead_dict, action, tone)

        return jsonify({
            "success":      True,
            "lead_id":      lead.id,
            "name":         lead.name,
            "score":        lead.score,
            "status":       lead.status,
            "city":         lead.city,
            "geo_fit":      city_fit,
            "recommended_action": action.action,
            "recommended_channel": action.channel,
            "tone":         tone,
            "good_time_now": good_time,
            "best_send_window": send_window,
            "timing_notes": timing.notes,
            "ai_summary":   ai_summary,
        })
    except Exception as e:
        log.error(f"[lead_ops/brief] {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


def _build_lead_briefing(lead: dict, action, tone: str) -> str:
    """Generate AI briefing using Haiku. Falls back to deterministic summary."""
    try:
        from routing.model_router import model_router
        from routing.cost_tracker import cost_tracker

        system = (
            "אתה עוזר מכירות של אשבל אלומיניום. "
            "צור תקציר מכירתי קצר בעברית לנציג המכירות לפני שיחה עם ליד. "
            "עד 3 משפטים. כלול: מה לדגיש, מה לשאול, ואיך לגשת."
        )
        user = (
            f"ליד: {lead.get('name')} | עיר: {lead.get('city')} | "
            f"ציון: {lead.get('score')} | סטטוס: {lead.get('status')} | "
            f"פעולה מומלצת: {action.action} | ערוץ: {action.channel} | "
            f"הערות: {lead.get('notes') or ''}"
        )
        result = model_router.call(
            task_type="classification",
            system_prompt=system,
            user_prompt=user,
            priority="cheap",
            max_tokens=150,
        )
        cost_tracker.flush_to_session_log("lead_brief_endpoint")
        return result
    except Exception:
        # Deterministic fallback
        return (
            f"ליד {lead.get('name')} מ{lead.get('city') or 'לא ידוע'}, "
            f"ציון {lead.get('score') or 0}. "
            f"פעולה מומלצת: {action.action} ({action.channel}). "
            f"טון מומלץ: {tone}."
        )


@bp.route("/lead_ops/batch_score", methods=["POST"])
@require_api_key
def batch_score_leads():
    """
    Batch-score unscored or low-scored leads using call_batch().
    Body: { "rescore_all": false, "limit": 20 }
    """
    data       = request.get_json(silent=True) or {}
    rescore_all = bool(data.get("rescore_all", False))
    limit       = min(int(data.get("limit") or 20), 50)

    try:
        from services.storage.repositories.lead_repo import LeadRepository
        from engines.lead_engine import compute_score
        from routing.model_router import model_router
        from routing.cost_tracker import cost_tracker

        repo  = LeadRepository()
        leads = repo.list_all(limit=limit)

        # Filter to unscored (or all if rescore_all)
        targets = [l for l in leads if rescore_all or not l.score or l.score == 0]
        if not targets:
            return jsonify({"success": True, "scored": 0, "message": "אין לידים לדירוג"})

        # Deterministic scoring via lead_engine (0 tokens) for all
        scored_results = []
        for lead in targets:
            score = compute_score(lead)
            repo.update_score(lead.id, score)
            scored_results.append({"lead_id": lead.id, "name": lead.name, "score": score})

        # AI enrichment: batch-generate score explanations for top 5 (Haiku)
        top5 = sorted(scored_results, key=lambda x: x["score"], reverse=True)[:5]
        if top5:
            prompts = [
                f"ליד {r['name']}, ציון {r['score']}/100. הסבר קצר (עד 10 מילים) מדוע הציון הזה."
                for r in top5
            ]
            system = "אתה מנהל מכירות. הסבר ציוני לידים בעברית קצרה."
            try:
                explanations = model_router.call_batch(
                    task_type="classification",
                    system_prompt=system,
                    user_prompts=prompts,
                    priority="cheap",
                    max_tokens=50,
                )
                cost_tracker.flush_to_session_log("batch_score_endpoint")
                for r, ex in zip(top5, explanations):
                    r["explanation"] = ex
            except Exception:
                pass   # explanations are optional

        return jsonify({
            "success": True,
            "scored":  len(scored_results),
            "top_5":   top5,
            "message": f"דורגו {len(scored_results)} לידים",
        })
    except Exception as e:
        log.error(f"[lead_ops/batch_score] {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/lead_ops/execute/<approval_id>", methods=["POST"])
@require_api_key
def execute_outreach(approval_id: str):
    """
    Execute an approved outreach action.
    Delegates to ApprovalRepository.resolve() for DB update, then emits
    APPROVAL_GRANTED/DENIED, logs activity, publishes LEAD_OUTREACH_SENT,
    and records learning outcome.
    Body: { "action": "approve" | "deny", "note": "..." }
    """
    data   = request.get_json(silent=True) or {}
    action = data.get("action") or "approve"
    note   = data.get("note") or ""

    if action not in ("approve", "deny"):
        return jsonify({"success": False, "error": "action must be approve or deny"}), 400

    try:
        from services.storage.repositories.approval_repo import ApprovalRepository
        from events.event_bus import event_bus
        import events.event_types as ET
        import json as _json

        repo   = ApprovalRepository()
        status = "approved" if action == "approve" else "denied"
        result = repo.resolve(approval_id, status=status,
                               resolved_by="lead_ops_api", note=note)

        if not result:
            return jsonify({"success": False,
                            "error": "approval not found or already resolved"}), 404

        # Emit APPROVAL_GRANTED/DENIED (canonical event for audit trail)
        event_type = ET.APPROVAL_GRANTED if action == "approve" else ET.APPROVAL_DENIED
        event_bus.publish(event_type, payload={
            "approval_id": approval_id,
            "action":      result.action,
            "resolved_by": "lead_ops_api",
            "task_id":     result.task_id,
        })

        details = result.details or {}
        if isinstance(details, str):
            try:    details = _json.loads(details)
            except Exception: details = {}
        lead_id   = details.get("lead_id") or ""
        lead_name = details.get("lead_name") or ""
        channel   = details.get("channel") or ""
        body      = details.get("body") or details.get("draft_body") or ""

        if action == "approve" and lead_id:
            from services.storage.db import get_session
            from services.storage.models.activity import ActivityModel
            with get_session() as s:
                s.add(ActivityModel(
                    lead_id=lead_id,
                    activity_type="note",
                    subject=f"הודעת פנייה אושרה — {channel}",
                    notes=body[:500],
                    outcome="completed",
                    performed_by="lead_ops_api",
                ))
            event_bus.publish(
                ET.LEAD_OUTREACH_SENT,
                payload={"lead_id": lead_id, "lead_name": lead_name,
                         "channel": channel, "approval_id": approval_id},
            )
            try:
                from skills.learning_skills import record_template_outcome
                if body:
                    record_template_outcome(
                        template_type="outreach",
                        template_text=body[:500],
                        outcome="sent",
                        segment=details.get("action_type"),
                        channel=channel,
                    )
            except Exception:
                pass

        return jsonify({
            "success":     True,
            "approval_id": approval_id,
            "status":      status,
            "lead_id":     lead_id,
            "lead_name":   lead_name,
        })
    except Exception as e:
        log.error(f"[lead_ops/execute] {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
