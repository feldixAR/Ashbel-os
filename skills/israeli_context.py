"""
skills/israeli_context.py — Israeli Context Skill
Phase 12: Lead Acquisition OS

Hebrew business tone, timing, holiday awareness, geo fit, local signals.
Stateless — all inputs explicit, zero tokens (no AI calls).

CONTRACT:
  get_hebrew_tone(segment: str) -> str
  is_good_timing(dt: datetime | None) -> bool
  get_best_send_window() -> str
  get_holiday_context(dt: datetime | None) -> dict
  local_signal_detection(text: str) -> dict
  geo_fit(city: str) -> float
  compliance_hints(channel: str) -> list[str]
"""

from __future__ import annotations
import datetime
from typing import Any


# ── Hebrew tone by segment ─────────────────────────────────────────────────────

_SEGMENT_TONE: dict[str, str] = {
    "architects":      "professional",   # מקצועי, ישיר, קצר
    "interior_design": "creative",       # יצירתי, חם, ויזואלי
    "contractors":     "direct",         # ישיר, מעשי, ללא מלמול
    "developers":      "business",       # עסקי, ROI-מוכוון
    "homeowners":      "warm",           # חם, שירותי, סבלני
    "business":        "professional",
    "default":         "professional",
}

_TONE_OPENINGS: dict[str, str] = {
    "professional": "שלום {name},",
    "creative":     "היי {name} 👋",
    "direct":       "שלום {name},",
    "business":     "שלום {name},",
    "warm":         "שלום {name}, תודה שיצרת קשר!",
    "light":        "היי {name},",
}


def get_hebrew_tone(segment: str) -> str:
    return _SEGMENT_TONE.get(segment, _SEGMENT_TONE["default"])


def get_tone_opening(segment: str, name: str = "שלום") -> str:
    tone = get_hebrew_tone(segment)
    template = _TONE_OPENINGS.get(tone, _TONE_OPENINGS["professional"])
    return template.replace("{name}", name)


# ── Israeli business timing ───────────────────────────────────────────────────
# Israeli work week: Sun–Thu, 08:00–18:00 (Fri 08:00–14:00)
# Avoid: Shabbat (Fri eve–Sat), major holidays

_GOOD_HOURS = (8, 18)      # 08:00–18:00
_FRIDAY_CUTOFF = 14        # Friday stop at 14:00

_JEWISH_HOLIDAYS_2026 = {
    # (month, day) in Gregorian approximate
    (4, 13): "פסח",   (4, 14): "פסח",  (4, 19): "פסח", (4, 20): "פסח",
    (5, 1):  "יום הזיכרון", (5, 2): "יום העצמאות",
    (6, 2):  "שבועות",
    (9, 22): "ראש השנה", (9, 23): "ראש השנה",
    (10, 1): "יום כיפור",
    (10, 6): "סוכות",   (10, 7): "סוכות",
    (10, 13): "שמחת תורה",
    (12, 25): "חנוכה",
}


def is_good_timing(dt: datetime.datetime | None = None) -> bool:
    """Return True if now is an appropriate time to send in Israel."""
    now = dt or _now_il()
    weekday = now.weekday()   # 0=Mon … 6=Sun
    hour = now.hour
    is_friday   = weekday == 4
    is_saturday = weekday == 5

    if is_saturday:
        return False
    if is_friday and hour >= _FRIDAY_CUTOFF:
        return False
    if hour < _GOOD_HOURS[0] or hour >= _GOOD_HOURS[1]:
        return False
    if (now.month, now.day) in _JEWISH_HOLIDAYS_2026:
        return False
    return True


def get_best_send_window(dt: datetime.datetime | None = None) -> str:
    """Return a human-readable best send window string."""
    now = dt or _now_il()
    weekday = now.weekday()
    # If currently in good window
    if is_good_timing(now):
        return "היום, שעות הבוקר (09:00–11:00)"
    # Find next available window
    if weekday == 4:  # Friday — next Sunday
        return "יום ראשון, 09:00"
    if weekday == 5:  # Saturday — Sunday
        return "יום ראשון, 09:00"
    if now.hour >= _GOOD_HOURS[1]:
        return "מחר, 09:00"
    return "היום, 09:00"


def get_holiday_context(dt: datetime.datetime | None = None) -> dict[str, Any]:
    now = dt or _now_il()
    holiday = _JEWISH_HOLIDAYS_2026.get((now.month, now.day))
    weekday = now.weekday()
    is_shabbat = weekday == 5
    is_erev    = weekday == 4 and now.hour >= 14

    next_biz = _next_business_day(now)
    return {
        "is_holiday":        bool(holiday),
        "holiday_name":      holiday,
        "is_shabbat":        is_shabbat,
        "is_erev_shabbat":   is_erev,
        "next_business_day": next_biz.strftime("%A %d/%m"),
        "send_now":          is_good_timing(now),
    }


# ── Local signal detection ────────────────────────────────────────────────────

_LOCAL_SIGNALS: dict[str, list[str]] = {
    "high_value":   ["פרויקט חדש", "בנייה", "שיפוץ", "הרחבה", "אחוזה", "וילה", "בניין"],
    "industry":     ["אדריכל", "מעצב פנים", "קבלן", "יזם", "הנדסאי", "קבלן משנה"],
    "aluminium":    ["אלומיניום", "חלונות", "דלתות", "פרגולה", "גדר", "גגון", "קיר וילון"],
    "competitor":   ["מתחרה", "אחר נותן", "עם ספק אחר"],
    "geo_israel":   ["ישראל", "תל אביב", "ירושלים", "חיפה", "ראשל\"צ", "נתניה", "הרצליה"],
}


def local_signal_detection(text: str) -> dict[str, Any]:
    """Scan text for Israeli business signals. Returns signal dict."""
    tl = text.lower()
    found: dict[str, list[str]] = {}
    for category, keywords in _LOCAL_SIGNALS.items():
        hits = [kw for kw in keywords if kw.lower() in tl]
        if hits:
            found[category] = hits
    strength = min(1.0, len(found) * 0.25)
    return {
        "signals_found":  found,
        "signal_strength": strength,
        "is_israeli":     "geo_israel" in found,
        "is_in_sector":   "aluminium" in found or "industry" in found,
        "has_buying_intent": "high_value" in found,
    }


# ── Geo fit ───────────────────────────────────────────────────────────────────

_TIER1 = {"תל אביב", "תל-אביב", "גוש דן", "הרצליה", "רמת גן", "גבעתיים", "בני ברק",
           "ירושלים", "חיפה", "רעננה", "כפר סבא", "הוד השרון", "פתח תקווה", "ראשון לציון"}
_TIER2 = {"נתניה", "אשדוד", "מודיעין", "ראש העין", "לוד", "רמלה", "יבנה", "נס ציונה",
           "קרית גת", "אשקלון", "חדרה", "זכרון יעקב"}


def geo_fit(city: str) -> float:
    """Return geo fit score 0.0–1.0 for Israeli city."""
    if not city:
        return 0.3
    c = city.strip()
    if c in _TIER1:
        return 1.0
    if c in _TIER2:
        return 0.7
    if "ישראל" in c or "israel" in c.lower():
        return 0.5
    return 0.3


# ── Compliance hints ──────────────────────────────────────────────────────────

_CHANNEL_COMPLIANCE: dict[str, list[str]] = {
    "whatsapp":     [
        "שליחת WhatsApp דורשת הסכמה מפורשת של הנמען.",
        "מסר שיווקי ב-WhatsApp חייב לכלול אפשרות הסרה.",
    ],
    "email":        [
        "כל דוא\"ל שיווקי חייב לפי חוק ספאם ישראלי (2008) לכלול Opt-Out.",
        "שמור רשומת הסכמה לפני שליחה.",
    ],
    "linkedin_dm":  [
        "LinkedIn: פנייה ישירה מותרת לפרופילים ציבוריים — אל תשלח מעל 20 DMs ביום.",
    ],
    "instagram_dm": [
        "Instagram: DM לחשבונות שלא עוקבים אחריך עלול להיות מסומן כספאם.",
    ],
    "telegram":     [
        "Telegram: מותר לשלוח רק לאנשים שנתנו לך את המספר שלהם.",
    ],
    "default":      ["ודא שיש לך הרשאה לפנות לנמען בערוץ זה."],
}


def compliance_hints(channel: str) -> list[str]:
    return _CHANNEL_COMPLIANCE.get(channel, _CHANNEL_COMPLIANCE["default"])


# ── Private helpers ────────────────────────────────────────────────────────────

def _now_il() -> datetime.datetime:
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Asia/Jerusalem")
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=2))
    return datetime.datetime.now(tz)


def _next_business_day(dt: datetime.datetime) -> datetime.datetime:
    next_day = dt + datetime.timedelta(days=1)
    while next_day.weekday() == 5:  # skip Sat
        next_day += datetime.timedelta(days=1)
    return next_day
