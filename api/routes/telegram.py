"""
telegram.py — POST /api/telegram/webhook

Receives inbound Telegram updates, authenticates via WEBHOOK_VERIFY_TOKEN,
forwards message text to the orchestrator, and replies via TelegramService.

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

    # ── Extract text ──────────────────────────────────────────────────────
    message  = body.get("message") or body.get("edited_message") or {}
    text     = (message.get("text") or "").strip()
    chat_id  = str(message.get("chat", {}).get("id", ""))
    username = message.get("from", {}).get("username", "telegram_user")

    if not text:
        return ok({"status": "ignored", "reason": "no text"})

    log.info(f"[Telegram] inbound from={username} chat={chat_id} text={text!r}")

    # ── Dispatch to orchestrator ──────────────────────────────────────────
    try:
        result = orchestrator.handle_command(text, source="telegram")
        reply  = result.message if result.success else (result.message or "שגיאה פנימית")
    except Exception as exc:
        log.exception(f"[Telegram] orchestrator error: {exc}")
        reply = "המערכת נתקלה בשגיאה. נסה שוב."

    # ── Reply via Telegram ────────────────────────────────────────────────
    telegram_service.send(reply)

    return ok({"status": "ok", "reply": reply})
