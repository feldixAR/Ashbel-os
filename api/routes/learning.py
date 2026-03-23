from flask import Blueprint, request, jsonify
import logging
log = logging.getLogger(__name__)
bp = Blueprint("learning", __name__)

@bp.route("/learning/performance", methods=["GET"])
def get_performance():
    try:
        from engines.learning_engine import measure_outreach_performance
        p=measure_outreach_performance(int(request.args.get("days",30)))
        return jsonify({"success":True,"performance":{"generated_at":p.generated_at,"total_outreach":p.total_outreach,"total_replies":p.total_replies,"overall_reply_rate":p.overall_reply_rate,"total_deals":p.total_deals,"total_revenue":p.total_revenue,"top_channel":p.top_channel,"top_audience":p.top_audience,"channels":[{"channel":c.channel,"sent":c.total_sent,"replied":c.replied,"reply_rate":c.reply_rate,"roi_score":c.roi_score} for c in p.channel_breakdown]}})
    except Exception as e: return jsonify({"success":False,"error":str(e)}),500

@bp.route("/learning/ab", methods=["GET"])
def get_ab_analysis():
    try:
        from engines.learning_engine import run_ab_analysis
        reports=run_ab_analysis(request.args.get("audience"))
        return jsonify({"success":True,"count":len(reports),"reports":[{"audience":r.audience,"winner":{"label":r.winner.label,"reply_rate":r.winner.reply_rate,"message":r.winner.message},"loser":{"label":r.loser.label,"reply_rate":r.loser.reply_rate},"improvement":r.improvement,"recommendation":r.recommendation} for r in reports]})
    except Exception as e: return jsonify({"success":False,"error":str(e)}),500

@bp.route("/learning/resources", methods=["GET"])
def get_resource_plan():
    try:
        from engines.learning_engine import allocate_resources
        plan=allocate_resources()
        return jsonify({"success":True,"plan":[{"audience":r.audience,"channel":r.channel,"priority":r.priority,"daily_quota":r.daily_quota,"reason":r.reason,"roi_score":r.roi_score} for r in plan]})
    except Exception as e: return jsonify({"success":False,"error":str(e)}),500

@bp.route("/learning/bottlenecks", methods=["GET"])
def get_bottlenecks():
    try:
        from engines.learning_engine import detect_bottlenecks_deep
        return jsonify({"success":True,"bottlenecks":detect_bottlenecks_deep()})
    except Exception as e: return jsonify({"success":False,"error":str(e)}),500

@bp.route("/learning/improve", methods=["POST"])
def run_improvements():
    try:
        from engines.learning_engine import auto_improve_agents
        r=auto_improve_agents()
        return jsonify({"success":True,"summary":r.summary,"improvements":[{"agent":i.agent_name,"action":i.action_taken} for i in r.improvements],"routing_updates":r.routing_updates,"template_updates":r.template_updates})
    except Exception as e: return jsonify({"success":False,"error":str(e)}),500

@bp.route("/learning/reply", methods=["POST"])
def record_reply():
    try:
        data=request.get_json() or {}
        from engines.learning_engine import record_reply
        ok=record_reply(data.get("outreach_id",""),data.get("reply_text",""),data.get("positive",True))
        return jsonify({"success":ok})
    except Exception as e: return jsonify({"success":False,"error":str(e)}),500

@bp.route("/learning/cycle", methods=["POST"])
def run_learning_cycle():
    try:
        from engines.learning_engine import full_learning_cycle
        result=full_learning_cycle()
        return jsonify({"success":True,"summary":result.cycle_summary,"next_actions":result.next_actions,"bottlenecks_count":len(result.bottlenecks),"ab_reports_count":len(result.ab_reports),"improvements":result.improvements.summary,"resource_plan":[{"audience":r.audience,"daily_quota":r.daily_quota} for r in result.resource_plan]})
    except Exception as e:
        log.error(f"[Learning] cycle error: {e}",exc_info=True)
        return jsonify({"success":False,"error":str(e)}),500

@bp.route("/learning/roi", methods=["GET"])
def get_roi_report():
    try:
        from engines.learning_engine import build_roi_report
        return jsonify({"success":True,"report":build_roi_report()})
    except Exception as e: return jsonify({"success":False,"error":str(e)}),500
