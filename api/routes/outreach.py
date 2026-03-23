from flask import Blueprint, request, jsonify
import logging, uuid as _uuid
log = logging.getLogger(__name__)
bp = Blueprint("outreach", __name__)

@bp.route("/outreach/queue", methods=["GET"])
def get_outreach_queue():
    try:
        from engines.outreach_engine import build_outreach_queue, prioritize_daily
        from services.storage.repositories.lead_repo import LeadRepository
        leads = LeadRepository().list_all(); queue = build_outreach_queue(leads); daily = prioritize_daily(queue)
        return jsonify({"success": True, "total_queue": len(queue), "daily_count": len(daily), "daily_tasks": [{"task_id": t.task_id, "lead_name": t.lead_name, "phone": t.phone, "channel": t.channel, "message": t.message, "audience": t.audience, "priority": t.priority, "urgency": t.urgency, "reason": t.reason, "attempt": t.attempt, "deep_link": t.deep_link} for t in daily]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/outreach/summary", methods=["GET"])
def get_daily_summary():
    try:
        from engines.outreach_engine import daily_outreach_summary
        s = daily_outreach_summary()
        return jsonify({"success": True, "date": s.date, "total_due": s.total_due, "pending": s.pending, "overdue": s.overdue, "top_priorities": [{"lead_name": t.lead_name, "phone": t.phone, "message": t.message[:100], "urgency": t.urgency, "reason": t.reason, "deep_link": t.deep_link} for t in s.top_priorities], "pipeline": [{"outreach_id": p.outreach_id, "lead_name": p.lead_name, "status": p.status, "attempt": p.attempt, "next_followup": p.next_followup} for p in s.pipeline]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/outreach/execute", methods=["POST"])
def execute_task():
    try:
        data = request.get_json() or {}
        from engines.outreach_engine import OutreachTask, execute_outreach, record_outreach_sent
        task = OutreachTask(task_id=data.get("task_id", str(_uuid.uuid4())), lead_id=data.get("lead_id",""), lead_name=data.get("lead_name",""), phone=data.get("phone",""), channel=data.get("channel","whatsapp"), message=data.get("message",""), audience=data.get("audience","general"), priority=data.get("priority",2), urgency=data.get("urgency","today"), reason=data.get("reason",""), goal_id=data.get("goal_id",""), opp_id=data.get("opp_id",""), attempt=data.get("attempt",1), deep_link=data.get("deep_link",""))
        result = execute_outreach(task)
        if result.success and task.lead_id: record_outreach_sent(task)
        return jsonify({"success": result.success, "lead_name": result.lead_name, "mode": result.mode, "message_id": result.message_id, "deep_link": result.deep_link, "sent_at": result.sent_at, "error": result.error})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/outreach/send", methods=["POST"])
def send_to_lead():
    try:
        data = request.get_json() or {}
        name = data.get("name",""); phone = data.get("phone",""); message = data.get("message",""); lead_id = data.get("lead_id","")
        if not phone and name:
            from services.storage.repositories.lead_repo import LeadRepository
            for l in LeadRepository().list_all():
                if name.lower() in l.name.lower(): phone = l.phone or ""; lead_id = l.id; break
        if not phone: return jsonify({"success": False, "error": "לא נמצא טלפון"}), 400
        if not message: return jsonify({"success": False, "error": "חסרה הודעה"}), 400
        from engines.outreach_engine import _build_whatsapp_link, OutreachTask, execute_outreach
        task = OutreachTask(task_id=str(_uuid.uuid4()), lead_id=lead_id, lead_name=name, phone=phone, channel="whatsapp", message=message, audience="general", priority=1, urgency="today", reason="שליחה ידנית", attempt=1, deep_link=_build_whatsapp_link(phone, message))
        result = execute_outreach(task)
        return jsonify({"success": result.success, "lead_name": name, "phone": phone, "mode": result.mode, "deep_link": result.deep_link, "message_id": result.message_id, "sent_at": result.sent_at})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/outreach/<outreach_id>/status", methods=["PUT"])
def update_status(outreach_id):
    try:
        data = request.get_json() or {}
        from engines.outreach_engine import update_pipeline_status
        ok = update_pipeline_status(outreach_id, data.get("status","sent"), data.get("notes",""))
        return jsonify({"success": ok, "outreach_id": outreach_id, "status": data.get("status")})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/outreach/pipeline", methods=["GET"])
def get_pipeline():
    try:
        from services.storage.repositories.outreach_repo import OutreachRepository
        records = OutreachRepository().list_due_followup()
        return jsonify({"success": True, "count": len(records), "pipeline": [r.to_dict() for r in records]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/outreach/daily", methods=["POST"])
def run_daily_cycle():
    try:
        from engines.outreach_engine import build_outreach_queue, prioritize_daily, execute_outreach, record_outreach_sent
        from services.storage.repositories.lead_repo import LeadRepository
        leads = LeadRepository().list_all(); queue = build_outreach_queue(leads); daily = prioritize_daily(queue, 5)
        results = []
        for task in daily:
            result = execute_outreach(task)
            if result.success and task.lead_id: record_outreach_sent(task)
            results.append({"lead_name": task.lead_name, "mode": result.mode, "deep_link": result.deep_link, "message_id": result.message_id, "success": result.success})
        return jsonify({"success": True, "total_queue": len(queue), "executed": len(results), "results": results})
    except Exception as e:
        log.error(f"[Outreach] daily cycle error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
