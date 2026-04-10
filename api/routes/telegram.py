"""
telegram.py — POST /api/telegram/webhook

Handles:
  - Inbound text messages → orchestrator
  - callback_query (inline buttons) → approval flow
    approve:{id} → POST /api/approvals/{id} action=approve
    deny:{id}    → POST /api/approvals/{id} action=deny
    edit:{id}    → ask user for edited text (stateless prompt)

Governance: Wave One approved channel. No WhatsApp/Email/Calendar touched.
"""
import logging
import os

from flask import Blueprint, request

from api.middleware import ok, _error
from orchestration.orchestrator import orchestrator
from services.telegram_service import telegram_service

log = logging.getLogger(__name__)
bp  = Blueprint("telegram", __name__)

_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "")


@bp.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    # ── Auth ──────────────────────────────────────────────────────────────
    token = request.headers.get("X-Telegram-Token", "")
    if _VERIFY_TOKEN and token != _VERIFY_TOKEN:
        log.warning("[Telegram] rejected — bad token")
        return _error("unauthorized", 401)

    body = request.get_json(silent=True) or {}

    # ── callback_query (inline button press) ─────────────────────────────
    cbq = body.get("callback_query")
    if cbq:
        return _handle_callback(cbq)

    # ── Inbound text message ──────────────────────────────────────────────
    message  = body.get("message") or body.get("edited_message") or {}
    text     = (message.get("text") or "").strip()
    username = message.get("from", {}).get("username", "telegram_user")

    if not text:
        return ok({"status": "ignored", "reason": "no text"})

    log.info(f"[Telegram] inbound from={username} text={text!r}")

    try:
        result = orchestrator.handle_command(text, source="telegram")
        reply  = result.message if result.success else (result.message or "שגיאה פנימית")
    except Exception as exc:
        log.exception(f"[Telegram] orchestrator error: {exc}")
        reply = "המערכת נתקלה בשגיאה. נסה שוב."

    telegram_service.send(reply)
    return ok({"status": "ok", "reply": reply})


def _handle_callback(cbq: dict):
    """Handle inline keyboard button presses."""
    cbq_id   = cbq.get("id", "")
    data     = (cbq.get("data") or "").strip()
    username = cbq.get("from", {}).get("username", "operator")

    log.info(f"[Telegram] callback from={username} data={data!r}")

    if not data or ":" not in data:
        telegram_service.answer_callback(cbq_id, "פעולה לא מוכרת")
        return ok({"status": "ignored"})

    action, approval_id = data.split(":", 1)

    if action == "edit":
        telegram_service.answer_callback(cbq_id, "שלח את הנוסח המתוקן בהודעה הבאה")
        telegram_service.send(
            f"✏️ לעריכת פנייה `{approval_id}`:\n"
            f"שלח את הנוסח המתוקן בהודעה הבאה והמערכת תעדכן."
        )
        return ok({"status": "edit_requested", "approval_id": approval_id})

    if action in ("approve", "deny"):
        reply_action = "approve" if action == "approve" else "deny"
        try:
            from services.storage.repositories.approval_repo import ApprovalRepository
            from api.routes.approvals import _resolve_approval
            result_msg = _resolve_approval(approval_id, reply_action, source="telegram")
            telegram_service.answer_callback(cbq_id, "✅ בוצע" if action == "approve" else "❌ נדחה")
            telegram_service.send(result_msg)
        except Exception as e:
            log.error(f"[Telegram] callback approval error: {e}", exc_info=True)
            telegram_service.answer_callback(cbq_id, "שגיאה — נסה שוב")
            telegram_service.send(f"שגיאה בטיפול באישור: {e}")
        return ok({"status": "handled", "action": action, "approval_id": approval_id})

    telegram_service.answer_callback(cbq_id, "פעולה לא מוכרת")
    return ok({"status": "unknown_action"})
