"""
telegram.py — POST /api/telegram/webhook

Phase 16: Full intake-normalizer routing.
Handles all Telegram payload types:
  text       → orchestrator (business_action / system_change / inbound_lead)
  voice      → transcription → orchestrator (or fallback prompt)
  document   → download → document_intelligence → parse_document handler
  photo      → log_only (guidance reply)
  contact    → process_inbound (inbound lead)
  location   → log_only
  reaction   → log_only
  callback_query (inline buttons) → approval flow

Governance: Wave One approved channel. No WhatsApp/Email/Calendar touched.
"""
import base64
import logging
import os

import requests
from flask import Blueprint, request

from api.middleware import ok, _error
from orchestration.orchestrator import orchestrator
from services.intake.normalizer import normalize_telegram
from services.telegram_service import telegram_service

log = logging.getLogger(__name__)
bp  = Blueprint("telegram", __name__)

_VERIFY_TOKEN  = os.getenv("WEBHOOK_VERIFY_TOKEN", "")
_BOT_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN", "")

_VOICE_FALLBACK = (
    "🎤 קיבלתי הודעה קולית, אבל לא הצלחתי לתמלל אותה.\n"
    "אנא שלח את בקשתך בטקסט."
)
_IMAGE_REPLY   = "📷 תמונה התקבלה — כרגע אני עובד עם טקסט בלבד. שלח פקודה בטקסט."
_LOCATION_REPLY = "📍 מיקום התקבל ונרשם. אם תרצה פעולה, שלח פקודה בטקסט."


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

    # ── All other message types via normalizer ────────────────────────────
    message = body.get("message") or body.get("edited_message") or {}
    if not message:
        return ok({"status": "ignored", "reason": "no message"})

    payload = normalize_telegram(message)
    log.info(
        f"[Telegram] modality={payload.modality} "
        f"meaning={payload.business_meaning} "
        f"action={payload.required_action} "
        f"sender={payload.sender}"
    )

    # ── Route by required_action ──────────────────────────────────────────
    if payload.required_action == "request_text_fallback":
        telegram_service.send(_VOICE_FALLBACK)
        return ok({"status": "voice_fallback"})

    if payload.required_action == "log_only":
        if payload.modality == "image":
            telegram_service.send(_IMAGE_REPLY)
        elif payload.modality == "location":
            telegram_service.send(_LOCATION_REPLY)
        return ok({"status": "logged", "modality": payload.modality})

    if payload.required_action == "parse_document":
        return _handle_document_payload(payload)

    if payload.required_action == "process_lead":
        return _handle_lead_payload(payload)

    # execute_command or preview_system_change → orchestrator dispatch
    if payload.extracted_content or payload.raw_content:
        return _dispatch_text(
            payload.extracted_content or payload.raw_content,
            sender_id=str(message.get("from", {}).get("id", "")),
        )

    return ok({"status": "ignored", "reason": "empty content"})


# ── Sub-handlers ──────────────────────────────────────────────────────────────

def _dispatch_text(text: str, sender_id: str = ""):
    """
    Send text through the orchestrator and reply.
    If sender has a pending edit context, apply edited body to approval first.
    """
    log.info(f"[Telegram] dispatch text={text!r} sender={sender_id!r}")

    # ── Check for pending edit context ────────────────────────────────────
    if sender_id:
        try:
            from memory.memory_store import MemoryStore
            pending = MemoryStore.read("telegram", f"pending_edit_{sender_id}")
            if pending and isinstance(pending, dict) and pending.get("approval_id"):
                return _apply_edit(pending["approval_id"], text, sender_id)
        except Exception as _e:
            log.debug(f"[Telegram] pending edit check error: {_e}")

    try:
        result = orchestrator.handle_command(text)
        reply  = result.message if result.success else (result.message or "שגיאה פנימית")
    except Exception as exc:
        log.exception(f"[Telegram] orchestrator error: {exc}")
        reply = "המערכת נתקלה בשגיאה. נסה שוב."
    telegram_service.send(reply)
    return ok({"status": "ok", "reply": reply})


def _handle_document_payload(payload):
    """Download a Telegram document and dispatch as parse_document."""
    attachment = (payload.attachments or [{}])[0]
    file_id    = attachment.get("file_id", "") or payload.structured_fields.get("file_id", "")
    file_name  = attachment.get("file_name", "") or payload.structured_fields.get("file_name", "")

    if not file_id or not _BOT_TOKEN:
        log.warning("[Telegram] document: missing file_id or bot token")
        telegram_service.send("📄 קיבלתי קובץ אבל לא הצלחתי לטעון אותו. נסה שוב.")
        return ok({"status": "error", "reason": "missing file_id"})

    try:
        # 1. Get file path
        resp = requests.get(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/getFile",
            params={"file_id": file_id}, timeout=10,
        )
        resp.raise_for_status()
        file_path = resp.json().get("result", {}).get("file_path", "")
        if not file_path:
            raise ValueError("empty file_path from Telegram")

        # 2. Download content
        dl = requests.get(
            f"https://api.telegram.org/file/bot{_BOT_TOKEN}/{file_path}",
            timeout=30,
        )
        dl.raise_for_status()
        content_bytes = dl.content

    except Exception as e:
        log.error(f"[Telegram] document download failed: {e}")
        telegram_service.send(f"📄 שגיאה בהורדת הקובץ: {e}")
        return ok({"status": "error", "reason": str(e)})

    # 3. Dispatch parse_document via task_manager
    import uuid as _uuid
    from orchestration.task_manager import task_manager
    try:
        task = task_manager.create_task(
            type="acquisition",
            action="parse_document",
            input_data={
                "command": f"עבד קובץ {file_name}",
                "intent":  "document_upload",
                "context": "command",
                "params":  {
                    "content_base64": base64.b64encode(content_bytes).decode(),
                    "file_name":      file_name,
                    "sender":         payload.sender,
                },
            },
            priority=5,
            trace_id=str(_uuid.uuid4()),
        )
        task_manager.transition(task.id, "queued")
        dispatch_result = task_manager.dispatch(task)
        output    = dispatch_result.get("output") or {}
        row_count = output.get("row_count", 0)
        saved     = output.get("saved", 0)
        reply = f"📄 הקובץ עובד — {row_count} שורות, {saved} לידים נשמרו."
    except Exception as e:
        log.error(f"[Telegram] parse_document dispatch failed: {e}")
        reply = f"📄 קיבלתי את הקובץ אבל לא הצלחתי לעבד אותו: {e}"

    telegram_service.send(reply)
    return ok({"status": "ok", "reply": reply})


def _apply_edit(approval_id: str, edited_body: str, sender_id: str):
    """
    Apply edited draft text to a pending approval.
    Called when user sends follow-up message after clicking Edit on an approval card.
    Clears the pending edit context, updates approval details, sends preview.
    """
    import json as _json
    try:
        from memory.memory_store import MemoryStore
        from services.storage.db import get_session
        from services.storage.models.approval import ApprovalModel

        # Clear pending edit context immediately
        MemoryStore.delete("telegram", f"pending_edit_{sender_id}")

        with get_session() as s:
            approval = s.get(ApprovalModel, approval_id)
            if not approval or approval.status != "pending":
                telegram_service.send(
                    f"❌ הפנייה `{approval_id[:8]}` לא נמצאה או כבר טופלה.\n"
                    f"הנוסח לא עודכן."
                )
                return ok({"status": "edit_not_applicable", "approval_id": approval_id})

            raw = approval.details or {}
            if isinstance(raw, str):
                try:    raw = _json.loads(raw)
                except Exception: raw = {}
            # Build a new dict so SQLAlchemy detects the JSON column change
            details = dict(raw)
            details["body"]       = edited_body
            details["draft_body"] = edited_body
            approval.details = details
            try:
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(approval, "details")
            except Exception:
                pass
            lead_name = details.get("lead_name", "")
            channel   = details.get("channel", "")

        log.info(f"[Telegram] edit applied approval={approval_id[:8]} sender={sender_id}")
        telegram_service.send(
            f"✅ הנוסח עודכן — {lead_name}\n\n"
            f"📝 *נוסח:*\n{edited_body[:500]}\n\n"
            f"ניתן לאשר את הפנייה כעת."
        )
        return ok({"status": "edit_applied", "approval_id": approval_id})

    except Exception as e:
        log.error(f"[Telegram] _apply_edit error: {e}", exc_info=True)
        telegram_service.send(f"❌ שגיאה בעדכון הנוסח: {e}")
        return ok({"status": "edit_error"})


def _handle_lead_payload(payload):
    """Process a contact-based or text-based inbound lead directly."""
    fields  = payload.structured_fields or {}
    command = payload.extracted_content or f"ליד נכנס: {fields.get('name', '')} {fields.get('phone', '')}"
    log.info(f"[Telegram] inbound lead from={payload.sender}: {command!r}")
    return _dispatch_text(command)


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
        # Store pending edit context so the follow-up message is captured
        try:
            from memory.memory_store import MemoryStore
            sender_id = str(cbq.get("from", {}).get("id", ""))
            if sender_id:
                MemoryStore.write(
                    "telegram", f"pending_edit_{sender_id}",
                    {"approval_id": approval_id},
                    updated_by="telegram",
                )
        except Exception as _e:
            log.debug(f"[Telegram] edit context store error: {_e}")

        telegram_service.answer_callback(cbq_id, "שלח את הנוסח המתוקן בהודעה הבאה")
        telegram_service.send(
            f"✏️ לעריכת פנייה `{approval_id[:8]}`:\n"
            f"שלח את הנוסח המתוקן בהודעה הבאה והמערכת תעדכן."
        )
        return ok({"status": "edit_requested", "approval_id": approval_id})

    if action in ("approve", "deny"):
        reply_action = "approve" if action == "approve" else "deny"
        try:
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
