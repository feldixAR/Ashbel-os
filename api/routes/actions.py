"""
POST /api/actions/execute

Executes an approved draft action (WhatsApp send, Calendar create, Reminder).
Called from UI after user clicks "אשר ושלח".

Request body:
    {
      "action_type": "whatsapp_draft" | "calendar_draft" | "reminder",
      "payload": { ... draft data ... },
      "lead_id": "optional"
    }
"""

import logging
from flask import Blueprint, request
from api.middleware import require_auth, log_request, ok, _error

log = logging.getLogger(__name__)
bp  = Blueprint("actions", __name__)


@bp.route("/actions/execute", methods=["POST"])
@require_auth
@log_request
def execute_action():
    body        = request.get_json(silent=True) or {}
    action_type = body.get("action_type", "").strip()
    payload     = body.get("payload", {})
    lead_id     = body.get("lead_id", "")

    if not action_type:
        return _error("field 'action_type' is required", 400)

    from services.integrations.action_dispatcher import action_dispatcher
    result = action_dispatcher.dispatch(action_type, payload, lead_id)

    return ok({
        "action_type": action_type,
        "result":      result,
        "success":     result.get("success", False),
        "mode":        result.get("mode", "unknown"),
        "deep_link":   result.get("deep_link"),
        "message":     _result_message(action_type, result),
    })


def _result_message(action_type: str, result: dict) -> str:
    if not result.get("success"):
        return f"שגיאה: {result.get('error', 'לא ידוע')}"
    mode = result.get("mode", "")
    if action_type == "whatsapp_draft":
        if mode == "api":
            return f"✅ WhatsApp נשלח ל-{result.get('to_name')}"
        if result.get("deep_link"):
            return f"🔗 קישור WhatsApp מוכן — לחץ לפתיחה"
        return "✅ הודעה הוכנה"
    if action_type == "calendar_draft":
        if mode == "api":
            return f"✅ פגישה נוצרה: {result.get('title')}"
        if result.get("deep_link"):
            return f"🔗 קישור יומן מוכן — לחץ לפתיחה"
    if action_type == "reminder":
        return f"⏰ תזכורת נרשמה: {result.get('reminder_text')}"
    return "✅ בוצע"
