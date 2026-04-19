"""
MessagingEngine — pure message construction logic.

No side effects. No event emission. No DB writes.
Agents call these functions and own the side effects.

Functions:
    build_message(name, city, notes, attempts, msg_type) -> str
    build_followup(name, city, last_response, attempts)  -> str
    classify_response(response_text)                     -> str
"""

import logging

log = logging.getLogger(__name__)

# Response classification buckets
_POSITIVE_KEYWORDS   = ("כן", "מעוניין", "מתעניין", "בסדר", "נשמע טוב",
                         "אשמח", "בוא", "תשלח", "רוצה", "interested", "yes")
_NEGATIVE_KEYWORDS   = ("לא", "לא מעוניין", "תוריד", "עצור", "no", "not interested",
                         "remove", "הסר")
_TIMING_KEYWORDS     = ("אחר כך", "בהמשך", "מאוחר יותר", "חודש", "שנה",
                         "later", "next month")
_INFO_REQUEST        = ("מחיר", "עלות", "כמה", "פרטים", "תשלח", "price", "details")


def _profile():
    try:
        from config.business_registry import get_active_business
        return get_active_business()
    except Exception:
        return None


def build_message(name: str, city: str = "", notes: str = "",
                   attempts: int = 0) -> str:
    """
    Build an outreach message for a lead.
    attempts=0 → cold message. attempts>0 → follow-up.
    """
    if attempts == 0:
        return _cold_message(name, city, notes)
    return _followup_message(name, city, attempts)


def _cold_message(name: str, city: str, notes: str) -> str:
    p = _profile()
    biz_name = p.name if p else "החברה שלנו"
    products = p.products if p else "מוצרים ושירותים איכותיים"
    city_part  = f" מ{city}" if city else ""
    notes_part = f"\nהערה: {notes}" if notes else ""
    return (
        f"שלום {name}{city_part},\n"
        f"אני מ{biz_name} — מתמחים ב{products}.\n"
        f"האם תרצה לשמוע על הפתרונות שלנו?{notes_part}\n"
        f"נשמח לתת הצעת מחיר ללא התחייבות 😊"
    )


def _followup_message(name: str, city: str, attempts: int) -> str:
    p = _profile()
    domain = p.domain if p else "הפרויקט"
    city_part = f" מ{city}" if city else ""
    if attempts < 3:
        cta = "האם יש זמן נוח לשיחה קצרה?"
    elif attempts < 5:
        cta = "רק לוודא שהפנייה שלנו הגיעה — עדיין זמינים לשאלות."
    else:
        cta = "זוהי הודעתנו האחרונה — נשמח לעזור אם הצורך יתעורר בעתיד."
    return (
        f"שלום {name}{city_part},\n"
        f"רציתי לחזור אליך בנוגע ל{domain}.\n"
        f"עדיין זמינים לשאלות ולהצעת מחיר. {cta}"
    )


def build_followup(name: str, city: str = "",
                    last_response: str = "", attempts: int = 1) -> str:
    """
    Build a follow-up message aware of the last response.
    """
    p = _profile()
    domain = p.domain if p else "הנושא"
    city_part = f" מ{city}" if city else ""

    if last_response:
        response_type = classify_response(last_response)
        if response_type == "timing":
            return (f"שלום {name}{city_part},\n"
                    f"חזרנו כפי שביקשת — עדיין זמינים לשאלות ולהצעת מחיר 😊")
        if response_type == "info_request":
            return (f"שלום {name}{city_part},\n"
                    f"בהמשך לשיחתנו — הנה הפרטים שביקשת:\n"
                    f"נשמח לתאם פגישה ולהציג את הפתרונות שלנו ב{domain}.")

    return _followup_message(name, city, attempts)


def classify_response(response_text: str) -> str:
    """
    Classify a lead's response into one of:
        positive | negative | timing | info_request | unknown

    Pure function — no I/O.
    """
    if not response_text:
        return "unknown"

    text = response_text.lower().strip()

    for kw in _NEGATIVE_KEYWORDS:
        if kw in text:
            return "negative"

    for kw in _TIMING_KEYWORDS:
        if kw in text:
            return "timing"

    for kw in _INFO_REQUEST:
        if kw in text:
            return "info_request"

    for kw in _POSITIVE_KEYWORDS:
        if kw in text:
            return "positive"

    return "unknown"


# ── AI variants ───────────────────────────────────────────────────────────────

def _system_prompt() -> str:
    p = _profile()
    biz = p.name if p else "החברה"
    domain = p.domain if p else "עסק"
    return (
        f"אתה מומחה מכירות B2B של {biz}. "
        f"תחום: {domain}. "
        "כתוב הודעות קצרות, מקצועיות וממוקדות ל-WhatsApp. "
        "עד 100 מילה. CTA ברור בסוף. ללא emojis מוגזמים."
    )


def build_message_ai(name: str, city: str = "",
                      notes: str = "", attempts: int = 0) -> str:
    """AI-powered message. Falls back to template on any error."""
    result = _build_message_ai(name, city, notes, attempts)
    if result:
        return result
    return build_message(name, city, notes, attempts)


def _build_message_ai(name: str, city: str,
                       notes: str, attempts: int) -> str:
    try:
        from routing.model_router import model_router
        p = _profile()
        domain = p.domain if p else "עסק"
        msg_type   = "פנייה ראשונה" if attempts == 0 else f"פולואפ #{attempts}"
        city_part  = f" מ{city}" if city else ""
        notes_part = f" הערות: {notes}." if notes else ""
        user_prompt = (
            f"כתוב {msg_type} ל{name}{city_part}.{notes_part} "
            f"לקוח פוטנציאלי ל{domain}."
        )
        return model_router.call(
            task_type="sales",
            system_prompt=_system_prompt(),
            user_prompt=user_prompt,
            max_tokens=200,
        )
    except Exception as e:
        log.warning(f"[MessagingEngine] AI call failed, using template: {e}")
        return ""


def _build_followup_ai(name: str, city: str,
                        last_response: str, attempts: int) -> str:
    try:
        from routing.model_router import model_router
        p = _profile()
        domain = p.domain if p else "עסק"
        city_part = f" מ{city}" if city else ""
        resp_part = f" תגובתו האחרונה: '{last_response}'." if last_response else ""
        user_prompt = (
            f"כתוב פולואפ #{attempts} ל{name}{city_part}.{resp_part} "
            f"לקוח פוטנציאלי ל{domain}."
        )
        return model_router.call(
            task_type="followup",
            system_prompt=_system_prompt(),
            user_prompt=user_prompt,
            max_tokens=200,
        )
    except Exception as e:
        log.warning(f"[MessagingEngine] AI followup failed, using template: {e}")
        return ""
