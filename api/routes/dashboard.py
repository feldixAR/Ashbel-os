
from flask import Blueprint, request, jsonify
import logging
import datetime
log = logging.getLogger(__name__)
bp = Blueprint("dashboard", __name__)

from api.middleware import require_auth, ok, _error


@bp.route("/dashboard/summary", methods=["GET"])
@require_auth
def dashboard_summary():
    """
    Command Center data feed.
    GET /api/dashboard/summary
    Returns: today_queue, hot_leads, stuck_deals, bottlenecks,
             recommended_actions, revenue_snapshot.
    """
    try:
        from services.storage.db import get_session
        from services.storage.models.lead import LeadModel
        from services.storage.models.deal import DealModel
        from services.storage.models.activity import ActivityModel
        from services.engines.priority_engine import compute_lead_score

        cutoff = (datetime.datetime.now(datetime.timezone.utc) -
                  datetime.timedelta(days=5)).isoformat()

        with get_session() as s:
            leads = s.query(LeadModel).filter(
                LeadModel.status != "לא רלוונטי"
            ).limit(300).all()

            deals = s.query(DealModel).filter(
                ~DealModel.stage.in_(["won", "lost"])
            ).order_by(DealModel.value_ils.desc()).limit(100).all()

            recent_lead_ids = {
                row[0] for row in
                s.query(ActivityModel.lead_id).filter(
                    ActivityModel.created_at > cutoff
                ).distinct().all()
            }

        # Build scored lead dicts
        def _lead_dict(l):
            return {
                "id":              l.id,
                "name":            l.name,
                "company":         getattr(l, "company", None),
                "status":          l.status,
                "phone":           l.phone,
                "source":          l.source,
                "potential_value": getattr(l, "potential_value", 0) or 0,
                "next_action":     getattr(l, "next_action", None),
                "next_action_due": getattr(l, "next_action_due", None),
                "last_activity_at": getattr(l, "last_activity_at", None) or l.last_contact,
                "priority_score":  getattr(l, "priority_score", 0) or 0,
            }

        lead_dicts = [_lead_dict(l) for l in leads]
        for ld in lead_dicts:
            ld["_score"] = compute_lead_score(ld)
        lead_dicts.sort(key=lambda x: x["_score"], reverse=True)

        deal_dicts     = [d.to_dict() for d in deals]
        pipeline_total = sum(d.get("value_ils", 0) or 0 for d in deal_dicts)
        weighted_total = sum(d.get("weighted_value", 0) or 0 for d in deal_dicts)

        today_queue = [{
            "lead_id":         ld["id"],
            "lead_name":       ld["name"],
            "company":         ld["company"],
            "status":          ld["status"],
            "score":           ld["_score"],
            "next_action":     ld["next_action"],
            "next_action_due": ld["next_action_due"],
            "potential_value": ld["potential_value"],
        } for ld in lead_dicts[:7]]

        hot_leads   = [ld for ld in lead_dicts if ld["status"] == "חם"][:6]
        stuck_deals = [d for d in deal_dicts if d["lead_id"] not in recent_lead_ids][:5]
        bottlenecks = [ld for ld in lead_dicts if not ld["next_action"]][:5]

        recommendations = []
        for ld in lead_dicts[:3]:
            if not ld["next_action"]:
                reason = "חסרה פעולה הבאה"
            elif ld["status"] == "חם":
                reason = "ליד חם — פעל מיד"
            else:
                reason = "בעדיפות גבוהה לפי ציון"
            recommendations.append({
                "lead_id":   ld["id"],
                "lead_name": ld["name"],
                "action":    ld["next_action"] or "הגדר פעולה הבאה",
                "reason":    reason,
                "score":     ld["_score"],
            })

        return ok({
            "today_queue":         today_queue,
            "hot_leads":           hot_leads,
            "stuck_deals":         stuck_deals,
            "bottlenecks":         bottlenecks,
            "recommended_actions": recommendations,
            "revenue_snapshot": {
                "pipeline":        pipeline_total,
                "weighted":        weighted_total,
                "active_deals":    len(deal_dicts),
                "hot_leads_count": len(hot_leads),
            },
        })
    except Exception as e:
        log.exception("[Dashboard] summary error")
        return _error(str(e), 500)

@bp.route("/dashboard", methods=["GET"])
def get_dashboard():
    """Dashboard מלא — KPIs, התראות, סיכומים."""
    try:
        from engines.dashboard_engine import build_dashboard
        data = build_dashboard()
        return jsonify({
            "success": True,
            "generated_at": data.generated_at,
            "business_name": data.business_name,
            "kpis": [{"key":k.key,"label":k.label,"value":k.value,"unit":k.unit,"trend":k.trend,"target":k.target,"status":k.status} for k in data.kpis],
            "alerts": [{"alert_id":a.alert_id,"severity":a.severity,"category":a.category,"message":a.message,"action":a.action} for a in data.alerts],
            "revenue_summary": data.revenue_summary,
            "pipeline_summary": data.pipeline_summary,
            "outreach_summary": data.outreach_summary,
            "learning_summary": data.learning_summary,
            "system_health": data.system_health,
        })
    except Exception as e:
        log.error(f"[Dashboard] error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/dashboard/text", methods=["GET"])
def get_dashboard_text():
    """Dashboard בפורמט טקסט קריא."""
    try:
        from engines.dashboard_engine import build_dashboard, format_dashboard_text
        return jsonify({"success": True, "report": format_dashboard_text(build_dashboard())})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/dashboard/kpis", methods=["GET"])
def get_kpis():
    """KPIs בלבד."""
    try:
        from engines.dashboard_engine import build_dashboard
        data = build_dashboard()
        return jsonify({"success": True, "kpis": [{"key":k.key,"label":k.label,"value":k.value,"unit":k.unit,"status":k.status,"target":k.target} for k in data.kpis]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/dashboard/alerts", methods=["GET"])
def get_alerts():
    """התראות פעילות."""
    try:
        from engines.dashboard_engine import build_dashboard
        data = build_dashboard()
        severity = request.args.get("severity")
        alerts = [a for a in data.alerts if not severity or a.severity == severity]
        return jsonify({"success": True, "count": len(alerts), "alerts": [{"alert_id":a.alert_id,"severity":a.severity,"category":a.category,"message":a.message,"action":a.action} for a in alerts]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/businesses", methods=["GET"])
def list_businesses():
    """רשימת עסקים רשומים."""
    try:
        from config.business_registry import list_businesses, get_active_business
        active = get_active_business()
        return jsonify({"success": True, "active": active.business_id, "businesses": [{"id":b.business_id,"name":b.name,"domain":b.domain,"avg_deal_size":b.avg_deal_size} for b in list_businesses()]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/businesses/<business_id>", methods=["GET"])
def get_business(business_id: str):
    """פרטי עסק ספציפי."""
    try:
        from config.business_registry import get_business
        b = get_business(business_id)
        if not b: return jsonify({"success": False, "error": "business not found"}), 404
        return jsonify({"success": True, "business": {"id":b.business_id,"name":b.name,"domain":b.domain,"products":b.products,"target_clients":b.target_clients,"primary_channel":b.primary_channel,"avg_deal_size":b.avg_deal_size,"currency":b.currency,"language":b.language}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
