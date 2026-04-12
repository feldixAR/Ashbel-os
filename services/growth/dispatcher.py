"""
services/growth/dispatcher.py — Batch 8: Outreach Dispatch.

Dispatches a ready OutreachModel record via Telegram, delivering the
generated asset content to the operator with a WhatsApp deep-link
for the customer contact.

Status lifecycle:
    ready  →  sent      (Telegram delivery confirmed, provider_message_id set)
    ready  →  failed    (Telegram error, failure_reason logged)

No SMTP / WhatsApp API calls — Telegram is the single dispatch channel.
The WhatsApp deep-link is embedded in the Telegram message for the operator.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

try:
    import pytz as _pytz
except ImportError:
    _pytz = None

log = logging.getLogger(__name__)
_IL_TZ = (_pytz.timezone("Asia/Jerusalem") if _pytz else __import__("datetime").timezone(__import__("datetime").timedelta(hours=3)))

# WhatsApp business number (deep-link for operator to tap and open chat)
_WA_NUMBER = "972501234567"   # override via env in production


# ── Result contract ────────────────────────────────────────────────────────────

@dataclass
class DispatchResult:
    record_id:          str
    success:            bool
    delivery_status:    str   # delivered | failed
    provider_message_id: str  = ""
    failure_reason:     str   = ""

    def to_dict(self) -> dict:
        return {
            "record_id":           self.record_id,
            "success":             self.success,
            "delivery_status":     self.delivery_status,
            "provider_message_id": self.provider_message_id,
            "failure_reason":      self.failure_reason,
        }


# ── Main dispatcher ────────────────────────────────────────────────────────────

def dispatch_record(record_id: str) -> DispatchResult:
    """
    Fetch a 'ready' OutreachModel record, send via Telegram, update DB status.

    Args:
        record_id: OutreachModel.id (= ExecutionRecord.record_id)

    Returns:
        DispatchResult with success flag, delivery_status, and provider_message_id.
    """
    from services.storage.db import get_session
    from services.storage.models.outreach import OutreachModel
    from services.telegram_service import telegram_service

    # ── 1. Fetch record ───────────────────────────────────────────────────────
    with get_session() as session:
        record = session.query(OutreachModel).filter_by(id=record_id).first()
        if not record:
            log.warning(f"[Dispatcher] record not found: {record_id}")
            return DispatchResult(
                record_id=record_id,
                success=False,
                delivery_status="failed",
                failure_reason="record_not_found",
            )
        if record.status != "ready":
            log.info(f"[Dispatcher] record {record_id} status={record.status} — skipped")
            return DispatchResult(
                record_id=record_id,
                success=False,
                delivery_status=record.delivery_status or "skipped",
                failure_reason=f"status_was_{record.status}",
            )

        # Snapshot fields before session closes
        asset_content  = record.message_body or ""
        contact_name   = record.contact_name or ""
        channel        = record.channel
        opp_id         = record.opp_id or ""
        goal_id        = record.goal_id

    # ── 2. Build Telegram message ─────────────────────────────────────────────
    wa_link   = f"https://wa.me/{_WA_NUMBER}"
    tg_text   = _format_telegram(contact_name, channel, asset_content, wa_link)

    # ── 3. Send via Telegram ──────────────────────────────────────────────────
    tg_result = telegram_service.send(tg_text, parse_mode="Markdown")

    now_il = datetime.datetime.now(_IL_TZ).isoformat()

    # ── 4. Update DB status ───────────────────────────────────────────────────
    if tg_result.success:
        from services.growth.policy import compute_next_action_at
        next_action = compute_next_action_at(channel, now_il)
        _update_record(
            record_id=record_id,
            status="sent",
            delivery_status="delivered",
            lifecycle_status="sent",
            sent_at=now_il,
            next_action_at=next_action,
            provider_message_id=tg_result.message_id,
            failure_reason=None,
        )
        log.info(
            f"[Dispatcher] sent record_id={record_id} "
            f"tg_message_id={tg_result.message_id} goal_id={goal_id}"
        )
        return DispatchResult(
            record_id=record_id,
            success=True,
            delivery_status="delivered",
            provider_message_id=tg_result.message_id,
        )
    else:
        _update_record(
            record_id=record_id,
            status="failed",
            delivery_status="failed",
            lifecycle_status="sent",   # still 'sent' lifecycle — dispatch failed
            sent_at=None,
            next_action_at=None,
            provider_message_id=None,
            failure_reason=tg_result.error,
        )
        log.error(
            f"[Dispatcher] failed record_id={record_id} "
            f"reason={tg_result.error} goal_id={goal_id}"
        )
        return DispatchResult(
            record_id=record_id,
            success=False,
            delivery_status="failed",
            failure_reason=tg_result.error,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_telegram(contact_name: str, channel: str, asset_content: str,
                     wa_link: str) -> str:
    """
    Format the Telegram notification sent to the operator.
    Embeds the generated asset text + a WhatsApp deep-link.
    """
    # Strip asset_type prefix from contact_name: "[whatsapp] Title" → "Title"
    display_name = contact_name
    if "] " in contact_name:
        display_name = contact_name.split("] ", 1)[-1]

    # Truncate asset content for Telegram (4096 char limit)
    preview = asset_content[:1800].strip()
    if len(asset_content) > 1800:
        preview += "\n_[...קוצר לתצוגה]_"

    return (
        f"🚀 *AshbelOS: נכס פנייה מוכן*\n\n"
        f"*הזדמנות:* {display_name}\n"
        f"*ערוץ:* {channel}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*תוכן ההודעה ללקוח:*\n\n"
        f"{preview}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📲 [פתח WhatsApp ושלח ללקוח]({wa_link})"
    )


def _update_record(
    record_id:           str,
    status:              str,
    delivery_status:     str,
    lifecycle_status:    str,
    sent_at:             str | None,
    next_action_at:      str | None,
    provider_message_id: str | None,
    failure_reason:      str | None,
) -> None:
    """Idempotent DB update for dispatch outcome."""
    try:
        from services.storage.db import get_session
        from services.storage.models.outreach import OutreachModel

        with get_session() as session:
            record = session.query(OutreachModel).filter_by(id=record_id).first()
            if record:
                record.status              = status
                record.delivery_status     = delivery_status
                record.lifecycle_status    = lifecycle_status
                record.provider_message_id = provider_message_id or ""
                record.failure_reason      = failure_reason or ""
                if sent_at:
                    record.sent_at = sent_at
                if next_action_at:
                    record.next_action_at = next_action_at
    except Exception as e:
        log.error(f"[Dispatcher] DB update failed record_id={record_id}: {e}", exc_info=True)
