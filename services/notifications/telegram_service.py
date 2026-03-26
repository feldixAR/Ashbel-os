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

log = logging.getLogger(__name__)
_IL_TZ       = pytz.timezone("Asia/Jerusalem")
_TG_API      = "https://api.telegram.org/bot{token}/sendMessage"
_AVG_DEAL    = 15_000   # ILS — Ashbal Aluminum baseline


# ── Public entry point ─────────────────────────────────────────────────────────

def send_daily_learning_report() -> dict:
    """
    Fetch today's learning KPIs, format Hebrew Markdown digest, send via Telegram.

    Returns:
        dict with keys: success (bool), message_id (str), error (str)
    """
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        log.warning(
            "[DailyLearning] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — "
            "daily learning report skipped"
        )
        return {"success": False, "message_id": "", "error": "missing_env_vars"}

    # ── 1. Gather data ────────────────────────────────────────────────────────
    data = _collect_report_data()

    # ── 2. Format Telegram message ────────────────────────────────────────────
    text = _format_message(data)

    # ── 3. Send ───────────────────────────────────────────────────────────────
    return _send(token, chat_id, text)


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
