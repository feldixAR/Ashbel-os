"""
policy_engine.py — Local-first policy checks. Zero AI tokens.
Called before every outreach execution.

check_timing(audience)  → dict {allowed, reason, next_slot}
check_quota(channel)    → dict {allowed, used, limit, reason}
check_compliance(msg)   → dict {allowed, warnings}
"""

import datetime
import logging

from config.business_knowledge import (
    ISRAELI_TIMING,
    AUDIENCE_PLAYBOOK,
    CHANNEL_RULES,
    ISRAELI_CULTURAL_RULES,
    WHATSAPP_POLICY,
)

log = logging.getLogger(__name__)

# ── In-memory quota counters (reset daily) ────────────────────────────────────
_quota: dict = {}
_quota_day: str = ""


def _get_quota(channel: str, key: str) -> int:
    global _quota, _quota_day
    today = datetime.date.today().isoformat()
    if today != _quota_day:
        _quota = {}
        _quota_day = today
    return _quota.get(f"{channel}:{key}", 0)


def _inc_quota(channel: str, key: str) -> None:
    global _quota, _quota_day
    today = datetime.date.today().isoformat()
    if today != _quota_day:
        _quota = {}
        _quota_day = today
    k = f"{channel}:{key}"
    _quota[k] = _quota.get(k, 0) + 1


# ── Public API ────────────────────────────────────────────────────────────────

def check_timing(audience: str = "general") -> dict:
    """
    Returns {allowed: bool, reason: str, next_slot: str|None}.
    Pure Python — 0 tokens.
    """
    now = datetime.datetime.now()
    weekday = now.weekday()   # Mon=0 … Sun=6
    t = now.time()

    for block in ISRAELI_TIMING["blocked"]:
        if block.get("all_day") and weekday == block["day"]:
            return {"allowed": False, "reason": block["reason"], "next_slot": "ראשון בבוקר"}
        if "from" in block and weekday == block["day"] and t >= block["from"]:
            return {"allowed": False, "reason": block["reason"], "next_slot": "ראשון בבוקר"}

    # Night block
    for (start_h, end_h) in ISRAELI_TIMING["avoid_hours"]:
        if t.hour >= start_h or t.hour < end_h:
            return {
                "allowed": False,
                "reason": "שעות לילה — אין לשלוח",
                "next_slot": f"07:00",
            }

    # Best hours check (advisory, not blocking)
    best = ISRAELI_TIMING["best_hours"].get(audience, [(9, 17)])
    in_best = any(start <= t.hour < end for start, end in best)
    return {
        "allowed": True,
        "reason": "זמן מותר לשליחה" + (" (שעת שיא)" if in_best else ""),
        "next_slot": None,
    }


def check_quota(channel: str, contact_type: str = "existing") -> dict:
    """
    Returns {allowed: bool, used: int, limit: int, reason: str}.
    Pure Python — 0 tokens.
    """
    rules = CHANNEL_RULES.get(channel, {})
    if not rules:
        return {"allowed": True, "used": 0, "limit": 0, "reason": "ערוץ לא מוגדר"}

    if channel == "whatsapp":
        limit_key = "daily_limit_new_contacts" if contact_type == "new" else "daily_limit_existing"
        limit = rules.get(limit_key, 50)
        quota_key = f"new" if contact_type == "new" else "existing"
    else:
        limit = rules.get("daily_limit", 100) or 9999
        quota_key = "all"

    used = _get_quota(channel, quota_key)
    allowed = used < limit
    return {
        "allowed": allowed,
        "used": used,
        "limit": limit,
        "reason": "מותר" if allowed else f"מכסה יומית מוצתה ({used}/{limit})",
    }


def record_sent(channel: str, contact_type: str = "existing") -> None:
    """Call after a successful send to track quota."""
    quota_key = "new" if contact_type == "new" else ("all" if channel != "whatsapp" else "existing")
    _inc_quota(channel, quota_key)


def check_compliance(message: str) -> dict:
    """
    Returns {allowed: bool, warnings: list[str]}.
    Checks cliche blacklist and length rules.
    Pure Python — 0 tokens.
    """
    warnings = []
    msg_lower = message.lower()

    for cliche in ISRAELI_CULTURAL_RULES["cliche_blacklist"]:
        if cliche in message:
            warnings.append(f"קלישאה שיווקית: '{cliche}'")

    if len(message) > CHANNEL_RULES["whatsapp"]["max_message_length"]:
        warnings.append(f"הודעה ארוכה מדי ({len(message)} תווים, מקסימום 500)")

    sentences = [s.strip() for s in message.split(".") if s.strip()]
    if len(sentences) > ISRAELI_CULTURAL_RULES["max_whatsapp_sentences"] + 1:
        warnings.append(f"יותר מ-{ISRAELI_CULTURAL_RULES['max_whatsapp_sentences']} משפטים לוואטסאפ")

    return {"allowed": len(warnings) == 0, "warnings": warnings}


def get_audience(lead) -> str:
    """Detect audience type from lead data. Pure Python — 0 tokens."""
    notes = (getattr(lead, "notes", "") or "").lower()
    status = (getattr(lead, "status", "") or "").lower()
    source = (getattr(lead, "source", "") or "").lower()

    playbooks = AUDIENCE_PLAYBOOK
    for audience, pb in playbooks.items():
        if any(kw in notes or kw in status for kw in pb.get("keywords", [])):
            return audience
    return "general"


# ── Singleton ─────────────────────────────────────────────────────────────────
policy_engine = type("PolicyEngine", (), {
    "check_timing":    staticmethod(check_timing),
    "check_quota":     staticmethod(check_quota),
    "check_compliance":staticmethod(check_compliance),
    "record_sent":     staticmethod(record_sent),
    "get_audience":    staticmethod(get_audience),
})()
