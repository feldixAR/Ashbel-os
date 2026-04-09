"""
business_knowledge.py — Ashbal Aluminum business rules, Israeli market knowledge.
Single source of truth for timing, audience playbooks, channel rules, cultural rules.
Used by: policy_engine, cultural_adapter, chief_of_staff_agent.
"""

from datetime import time

# ── Israeli Timing Rules ──────────────────────────────────────────────────────

ISRAELI_TIMING = {
    "blocked": [
        {"day": 4, "from": time(13, 0), "reason": "ערב שבת — אין לשלוח"},   # Friday after 13:00
        {"day": 5, "all_day": True,     "reason": "שבת — אין לשלוח"},        # Saturday
    ],
    "best_hours": {
        "contractors":  [(8, 10), (13, 15)],
        "architects":   [(9, 11), (14, 16)],
        "private":      [(10, 12), (19, 21)],
        "general":      [(9, 12), (14, 17)],
    },
    "avoid_hours": [(22, 7)],  # night hours
    "holiday_aware": True,
}

# ── Audience Playbook ─────────────────────────────────────────────────────────

AUDIENCE_PLAYBOOK = {
    "contractors": {
        "tone":             "direct",
        "formality":        "informal",
        "hook":             "חוסך לך זמן בפרויקט",
        "opening":          "היי {name}",
        "best_time":        "08:00–10:00, 13:00–15:00",
        "channel_preference": "whatsapp",
        "max_attempts":     4,
        "urgency_threshold": 2,
        "avoid_words":      ["מבצע", "חסכון גדול", "הזדמנות פז"],
        "keywords":         ["קבלן", "פרויקט", "ביצוע", "יזם"],
    },
    "architects": {
        "tone":             "professional",
        "formality":        "formal",
        "hook":             "פתרון טכני מקצועי לפרויקט שלך",
        "opening":          "שלום {name}",
        "best_time":        "09:00–11:00, 14:00–16:00",
        "channel_preference": "email",
        "max_attempts":     3,
        "urgency_threshold": 3,
        "avoid_words":      ["זול", "מבצע", "מהר"],
        "keywords":         ["אדריכל", "מעצב", "תכנון", "ספסיפיקציה"],
    },
    "private": {
        "tone":             "warm",
        "formality":        "informal",
        "hook":             "פתרון מושלם לבית שלך",
        "opening":          "היי {name}",
        "best_time":        "10:00–12:00, 19:00–21:00",
        "channel_preference": "whatsapp",
        "max_attempts":     3,
        "urgency_threshold": 2,
        "avoid_words":      ["קבלן", "מסחרי", "תכנון מורכב"],
        "keywords":         ["בית", "דירה", "שיפוץ", "חלונות"],
    },
    "general": {
        "tone":             "friendly",
        "formality":        "semi-formal",
        "hook":             "אשבל אלומיניום — ייצור והתקנה מקצועיים",
        "opening":          "שלום {name}",
        "best_time":        "09:00–12:00, 14:00–17:00",
        "channel_preference": "whatsapp",
        "max_attempts":     3,
        "urgency_threshold": 3,
        "avoid_words":      ["מבצע מטורף", "אל תפספס"],
        "keywords":         [],
    },
}

# ── Channel Rules ─────────────────────────────────────────────────────────────

CHANNEL_RULES = {
    "whatsapp": {
        "daily_limit_new_contacts":    10,
        "daily_limit_existing":        50,
        "template_required_new":       True,
        "max_message_length":          500,
        "deeplink_fallback":           True,
        "approved_message_types":      ["text", "template"],
    },
    "email": {
        "daily_limit":                 100,
        "requires_opt_in":             False,
        "max_message_length":          2000,
    },
    "telegram": {
        "daily_limit":                 None,
        "internal_only":               True,
    },
}

# ── Israeli Cultural Rules ────────────────────────────────────────────────────

ISRAELI_CULTURAL_RULES = {
    "directness_level":    "high",
    "fluff_tolerance":     "low",
    "formality_default":   "semi-formal",
    "max_whatsapp_sentences": 3,
    "urgency_signals":     ["עכשיו", "היום", "מיידי", "דחוף"],
    "cliche_blacklist":    [
        "הצעה שאי אפשר לסרב לה",
        "מחיר מטורף",
        "אל תפספס",
        "הזדמנות פז",
        "מבצע להיום בלבד",
        "לחץ כאן",
        "ממש שווה לך",
        "תן לי לספר לך",
    ],
    "credibility_signals": [
        "ניסני עוז",
        "אשבל אלומיניום",
        "ניסיון של שנים",
        "פרויקטים מורכבים",
    ],
}

# ── WhatsApp Policy ───────────────────────────────────────────────────────────

WHATSAPP_POLICY = {
    "daily_quota_new":        10,
    "daily_quota_existing":   50,
    "template_first_contact": True,
    "deeplink_fallback":      True,
    "e164_required":          True,
    "il_prefix":              "972",
}
