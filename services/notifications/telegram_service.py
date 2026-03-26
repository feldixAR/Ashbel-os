"""
services/notifications/telegram_service.py — Batch 10.1: Daily Learning Push.

send_daily_learning_report():
  Pulls data from the learning engine directly (no HTTP roundtrip),
  formats a professional Hebrew Markdown digest, and sends it via
  the Telegram Bot API using TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.

Environment variables required:
    TELEGRAM_BOT_TOKEN  — bot token from @BotFather
    TELEGRAM_CHAT_ID    — operator chat/channel ID
    OS_API_KEY          — verified present but not used for direct calls

Resilience:
    Missing env vars → warning logged, no crash.
    Learning engine errors → fallback "no data" message sent.
    Telegram API errors → logged, not raised.
"""

from __future__ import annotations

import datetime
import logging
import os

import httpx
import pytz
from sqlalchemy.exc import IntegrityError

log = logging.getLogger(__name__)
_IL_TZ       = pytz.timezone("Asia/Jerusalem")
_TG_API      = "https://api.telegram.org/bot{token}/sendMessage"
_AVG_DEAL    = 15_000   # ILS — Ashbal Aluminum baseline

# Sentinel key used in sent_notifications to deduplicate the learning report.
# Must not collide with any real lead_id — prefixed to guarantee uniqueness.
_DEDUP_KEY   = "__daily_learning_report__"


# ── Public entry point ─────────────────────────────────────────────────────────

def send_daily_learning_report() -> dict:
    """
    Fetch today's learning KPIs, format Hebrew Markdown digest, send via Telegram.

    Cross-process deduplication:
        Uses the same DB-lock pattern as Axis 6 (telegram_delivery).
        All Gunicorn workers race to INSERT SentNotificationModel(
            lead_id='__daily_learning_report__', delivery_date=<today_IL>
        ).
        UNIQUE(lead_id, delivery_date) ensures exactly one INSERT wins.
        Losers receive IntegrityError → skipped immediately.

    Returns:
        dict with keys: success (bool), message_id (str), error (str),
                        skipped (bool, True when dedup lock was held by another worker)
    """
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        log.warning(
            "[DailyLearning] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — "
            "daily learning report skipped"
        )
        return {"success": False, "skipped": True,
                "message_id": "", "error": "missing_env_vars"}

    # ── 1. Acquire cross-process dedup lock ───────────────────────────────────
    today_il = datetime.datetime.now(_IL_TZ).date()   # datetime.date, Israel TZ
    lock_acquired = _acquire_dedup_lock(_DEDUP_KEY, today_il)

    if not lock_acquired:
        log.info(
            f"[DailyLearning] pid={os.getpid()} — "
            f"duplicate detected for date={today_il}, skipping"
        )
        return {"success": True, "skipped": True,
                "message_id": "", "error": ""}

    log.info(
        f"[DailyLearning] pid={os.getpid()} — "
        f"lock acquired for date={today_il}, sending report"
    )

    # ── 2. Gather data ────────────────────────────────────────────────────────
    data = _collect_report_data()

    # ── 3. Format Telegram message ────────────────────────────────────────────
    text = _format_message(data)

    # ── 4. Send ───────────────────────────────────────────────────────────────
    result = _send(token, chat_id, text)
    result["skipped"] = False
    return result


# ── Dedup lock ─────────────────────────────────────────────────────────────────

def _acquire_dedup_lock(job_key: str, delivery_date) -> bool:
    """
    Attempt to INSERT a SentNotificationModel row with the given sentinel key
    and today's Israel-timezone date.

    Returns True  — this worker won the race; proceed with delivery.
    Returns False — IntegrityError: another worker already inserted; skip.

    The UNIQUE constraint idx_lead_delivery_date_unique on
    (lead_id, delivery_date) is the atomic gate. Both SQLite and
    PostgreSQL enforce this at the storage engine level.
    """
    from services.storage.db import SessionLocal
    from services.storage.models.notification import SentNotificationModel

    db = SessionLocal()
    try:
        db.add(SentNotificationModel(
            lead_id=job_key,
            delivery_date=delivery_date,
            status="sent",
        ))
        db.commit()
        return True                  # lock acquired
    except IntegrityError:
        db.rollback()
        return False                 # another worker holds the lock
    finally:
        db.close()


# ── Data collector ─────────────────────────────────────────────────────────────

def _collect_report_data() -> dict:
    """
    Call the learning engine directly to get KPIs.
    Returns a safe dict even if the engine fails.
    """
    result = {
        "top_channel":      None,
        "top_audience":     None,
        "revenue_24h":      {"closed_won": 0, "revenue_ils": 0},
        "revenue_7d":       {"closed_won": 0, "revenue_ils": 0},
        "all_metrics_count": 0,
        "error":            None,
    }

    try:
        from services.growth.learning_engine import revenue_window
        from services.storage.db import get_session
        from services.storage.models.analytics import PerformanceMetric

        # Revenue windows (live query)
        result["revenue_24h"] = revenue_window(hours=24)
        result["revenue_7d"]  = revenue_window(hours=24 * 7)

        # Top performers from PerformanceMetric snapshot
        with get_session() as session:
            rows = (
                session.query(PerformanceMetric)
                .filter(PerformanceMetric.sample_size >= 3)
                .order_by(PerformanceMetric.conversion_rate.desc())
                .all()
            )
            all_metrics = [r.to_dict() for r in rows]

        result["all_metrics_count"] = len(all_metrics)

        channels  = [m for m in all_metrics if m["dim_type"] == "channel"]
        audiences = [m for m in all_metrics if m["dim_type"] == "audience"]

        result["top_channel"]  = channels[0]  if channels  else None
        result["top_audience"] = audiences[0] if audiences else None

    except Exception as e:
        log.error(f"[DailyLearning] data collection failed: {e}", exc_info=True)
        result["error"] = str(e)

    return result


# ── Message formatter ──────────────────────────────────────────────────────────

def _format_message(data: dict) -> str:
    now_il   = datetime.datetime.now(_IL_TZ)
    time_str = now_il.strftime("%d/%m/%Y %H:%M")

    # Top channel block
    ch = data.get("top_channel")
    if ch:
        conv_pct    = round(ch["conversion_rate"] * 100, 1)
        ch_line     = f"*{ch['dim_value'].capitalize()}* — המרה {conv_pct}% ({ch['total_won']} עסקאות)"
    else:
        ch_line     = "_אין מספיק נתונים עדיין_"

    # Top audience block
    aud = data.get("top_audience")
    if aud:
        aud_conv    = round(aud["conversion_rate"] * 100, 1)
        aud_line    = f"*{_heb_audience(aud['dim_value'])}* — {aud['total_won']} עסקאות ({aud_conv}% המרה)"
    else:
        aud_line    = "_אין מספיק נתונים עדיין_"

    # Revenue blocks
    r24 = data.get("revenue_24h", {})
    r7d = data.get("revenue_7d",  {})
    rev_24h_str = f"₪{r24.get('revenue_ils', 0):,} ({r24.get('closed_won', 0)} עסקאות)"
    rev_7d_str  = f"₪{r7d.get('revenue_ils', 0):,} ({r7d.get('closed_won', 0)} עסקאות)"

    # Error notice (appended silently if data collection had issues)
    err_note = ""
    if data.get("error"):
        err_note = f"\n⚠️ _שגיאת נתונים: {data['error'][:80]}_"

    return (
        f"📊 *AshbelOS \\- סיכום למידה יומי*\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🏆 *ערוץ מוביל:*\n"
        f"  {ch_line}\n\n"
        f"👥 *קהל מוביל:*\n"
        f"  {aud_line}\n\n"
        f"💰 *הכנסות:*\n"
        f"  • 24 שעות: {rev_24h_str}\n"
        f"  • 7 ימים: {rev_7d_str}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔒 *סטטוס:* מערכת פעילה ✅\n"
        f"⏰ *עודכן:* {time_str} IL"
        f"{err_note}"
    )


# ── Sender ─────────────────────────────────────────────────────────────────────

def _send(token: str, chat_id: str, text: str) -> dict:
    """POST message to Telegram Bot API. Returns result dict."""
    url = _TG_API.format(token=token)
    try:
        resp = httpx.post(
            url,
            json={
                "chat_id":                  chat_id,
                "text":                     text,
                "parse_mode":               "MarkdownV2",
                "disable_web_page_preview": True,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data       = resp.json()
        message_id = str(data.get("result", {}).get("message_id", ""))
        log.info(f"[DailyLearning] Telegram sent message_id={message_id}")
        return {"success": True, "message_id": message_id, "error": ""}
    except httpx.HTTPStatusError as e:
        err = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        log.error(f"[DailyLearning] Telegram HTTP error: {err}")
        return {"success": False, "message_id": "", "error": err}
    except Exception as e:
        log.error(f"[DailyLearning] Telegram send failed: {e}", exc_info=True)
        return {"success": False, "message_id": "", "error": str(e)}


# ── Audience label helper ──────────────────────────────────────────────────────

_AUD_HEB = {
    "contractors":        "קבלנים",
    "architects":         "אדריכלים",
    "interior_designers": "מעצבי פנים",
    "general":            "לקוחות כלליים",
}

def _heb_audience(key: str) -> str:
    return _AUD_HEB.get(key, key)
