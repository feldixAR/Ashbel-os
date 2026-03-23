
from flask import Blueprint, request, jsonify
import logging
log = logging.getLogger(__name__)
bp = Blueprint("dashboard", __name__)

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
