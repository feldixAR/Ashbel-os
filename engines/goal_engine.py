"""
goal_engine.py — Goal & Growth Engine (Batch 6)

Single module that handles the full vertical slice:
  1. GoalEngine     — decompose goal into tracks
  2. OpportunityEngine — identify opportunities per track
  3. ResearchEngine — audience profile + market insights
  4. AssetEngine    — first message + portfolio draft
"""

import uuid
import copy
import datetime
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

log = logging.getLogger(__name__)


# ── Domain knowledge ──────────────────────────────────────────────────────────

DOMAIN_KEYWORDS = {
    "aluminum": ["אלומיניום", "חלונות", "דלתות", "סורגים", "פרגולה", "aluminum"],
    "real_estate": ["נדלן", "נדל\"ן", "דירות", "בתים"],
}

DOMAIN_TRACKS: Dict[str, list] = {
    "aluminum": [
        {"name": "אדריכלים ומעצבי פנים", "channel": "whatsapp", "audience": "architects", "priority": 1,
         "actions": ["מחקר אדריכלים רלוונטיים", "התאמת תיק עבודות לסגנון", "בניית פנייה מותאמת", "follow-up sequence"]},
        {"name": "קבלנים ויזמים",          "channel": "whatsapp", "audience": "contractors", "priority": 2,
         "actions": ["מיפוי קבלנים פעילים", "הצעת שיתוף פעולה", "מחיר תחרותי לכמויות", "פגישת היכרות"]},
        {"name": "לקוחות פרטיים — שיפוצים","channel": "whatsapp", "audience": "private",     "priority": 3,
         "actions": ["קבוצות פייסבוק שיפוצים", "תוכן אורגני", "המלצות", "מבצעים עונתיים"]},
        {"name": "לינקדאין ותוכן מקצועי",  "channel": "linkedin", "audience": "architects",  "priority": 4,
         "actions": ["פרסום תיקי עבודות", "מאמרים מקצועיים", "חיבורים עם אדריכלים"]},
    ],
    "default": [
        {"name": "מסלול ראשי", "channel": "whatsapp", "audience": "general", "priority": 1,
         "actions": ["מחקר שוק", "פנייה ראשונה", "מעקב"]},
    ],
}

OPPORTUNITY_TEMPLATES: Dict[str, list] = {
    "architects": [
        {"title": "פנייה לאדריכלים עם פרויקטים בסגנון מודרני", "potential": "high",   "effort": "medium",
         "next_action": "מחקר אדריכלים + בניית תיק עבודות מותאם"},
        {"title": "שיתוף פעולה קבוע עם משרד אדריכלים",        "potential": "high",   "effort": "high",
         "next_action": "פגישת היכרות + הצעת תנאים"},
    ],
    "contractors": [
        {"title": "הסכם ספק קבוע עם קבלן פעיל", "potential": "high",   "effort": "medium",
         "next_action": "מיפוי קבלנים + הצעת מחיר לכמויות"},
    ],
    "private": [
        {"title": "פנייה לרוכשי דירות חדשות", "potential": "medium", "effort": "low",
         "next_action": "קבוצות פייסבוק + תוכן שיווקי"},
    ],
    "general": [
        {"title": "מחקר שוק ומיפוי לקוחות", "potential": "medium", "effort": "low",
         "next_action": "סקר שוק ראשוני"},
    ],
}

AUDIENCE_PROFILES: Dict[str, dict] = {
    "architects": {
        "pain_points":  ["ספקים שלא עומדים בזמנים", "חומרים שלא תואמים לתכנון"],
        "motivations":  ["איכות גבוהה", "ספק אמין", "גמישות עיצובית"],
        "channels":     ["whatsapp", "email", "linkedin"],
        "message_tone": "מקצועי, מכבד, עם דגש על איכות ואמינות",
    },
    "contractors": {
        "pain_points":  ["מחירים גבוהים", "אספקה לא בזמן"],
        "motivations":  ["מחיר תחרותי", "אספקה מהירה", "קרדיט"],
        "channels":     ["whatsapp", "phone"],
        "message_tone": "ישיר, עסקי, עם דגש על מחיר וזמינות",
    },
    "private": {
        "pain_points":  ["לא יודעים כמה יעלה", "פחד מקבלנים לא אמינים"],
        "motivations":  ["מחיר שקוף", "ביטחון", "תוצאה יפה"],
        "channels":     ["whatsapp", "facebook"],
        "message_tone": "חם, אישי, עם דגש על ביטחון",
    },
    "general": {
        "pain_points":  ["לא ידוע"],
        "motivations":  ["איכות", "מחיר"],
        "channels":     ["whatsapp"],
        "message_tone": "מקצועי וידידותי",
    },
}

DOMAIN_INSIGHTS: Dict[str, list] = {
    "aluminum": [
        {"category": "שוק",    "content": "ביקוש לאלומיניום בישראל גדל ב-15% בשנים האחרונות",
         "action": "מנף את הביקוש הגובר בפנייה לקבלנים"},
        {"category": "קהל",    "content": "אדריכלים מחפשים ספקים שמבינים עיצוב",
         "action": "בנה תיק עבודות עם דגש על עיצוב ואסתטיקה"},
        {"category": "ערוץ",   "content": "WhatsApp הוא הערוץ המועדף לתקשורת עסקית בישראל",
         "action": "התמקד ב-WhatsApp כערוץ ראשי"},
        {"category": "תחרות",  "content": "רוב ספקי האלומיניום לא משקיעים בשיווק דיגיטלי",
         "action": "יתרון תחרותי ברור בנוכחות דיגיטלית"},
    ],
}

MESSAGE_TEMPLATES: Dict[str, dict] = {
    "architects": {
        "subject": "שיתוף פעולה בתחום האלומיניום",
        "body": (
            "שלום,\n\n"
            "ראיתי את הפרויקטים שלך ואני מתרשם מהסגנון המקצועי.\n\n"
            "אנחנו מתמחים באלומיניום איכותי שמתאים לדרישות עיצוביות מדויקות — "
            "חלונות, דלתות, פרגולות.\n\n"
            "האם תרצה לקבל דוגמאות עבודה רלוונטיות?\n\n"
            "בברכה"
        ),
    },
    "contractors": {
        "subject": "הצעת שיתוף פעולה — אלומיניום לכמויות",
        "body": (
            "שלום,\n\n"
            "אנחנו ספק אלומיניום עם ניסיון רב בעבודה עם קבלנים.\n\n"
            "מחירים תחרותיים לכמויות, אספקה בזמן, אחריות מלאה.\n\n"
            "האם תרצה הצעת מחיר?\n\nבברכה"
        ),
    },
    "private": {
        "subject": "אלומיניום לבית — הצעה אישית",
        "body": (
            "שלום,\n\n"
            "שמענו שאתה מתכנן שיפוץ.\n\n"
            "אנחנו מתמחים באלומיניום איכותי לבית — חלונות, דלתות, פרגולות.\n\n"
            "הצעת מחיר ללא עלות ומחויבות.\n\nבברכה"
        ),
    },
    "general": {
        "subject": "פנייה ראשונית",
        "body": "שלום,\n\nנשמח להכיר ולדון בשיתוף פעולה.\n\nבברכה",
    },
}

PORTFOLIO_TEMPLATES: Dict[str, dict] = {
    "architects": {
        "title": "תיק עבודות — אלומיניום לפרויקטים אדריכליים",
        "description": "פתרונות אלומיניום מותאמים אישית לפרויקטים אדריכליים עם דגש על עיצוב ודיוק ביצוע.",
        "highlights": [
            "התאמה לכל סגנון — מינימליסטי, מודרני, כפרי",
            "חומרים מאושרים עם אחריות יצרן",
            "ביצוע מהיר ומדויק לפי תוכניות",
            "ליווי מקצועי לאורך כל הפרויקט",
        ],
    },
    "contractors": {
        "title": "תיק עבודות — פתרונות אלומיניום לקבלנים",
        "description": "ספק אמין לקבלנים עם מחירים תחרותיים, אספקה בזמן ואחריות מלאה.",
        "highlights": [
            "מחירים מיוחדים לכמויות גדולות",
            "אספקה תוך 48 שעות למרכז",
            "מגוון רחב של פרופילים ומידות",
            "תמיכה טכנית זמינה",
        ],
    },
    "general": {
        "title": "תיק עבודות",
        "description": "פתרונות איכותיים מותאמים לצרכים שלך.",
        "highlights": ["איכות גבוהה", "מחיר הוגן", "שירות מקצועי"],
    },
}

FOLLOWUP_SEQUENCES: Dict[str, list] = {
    "architects": [
        {"day": 3,  "message": "שלום, רציתי לוודא שקיבלת את הפנייה. האם יש זמן לשיחה קצרה?"},
        {"day": 7,  "message": "שלום, יש לי תיק עבודות חדש שעשוי לעניין אותך."},
        {"day": 14, "message": "שלום, ההצעה שלי עדיין פתוחה. נשמח לשיתוף פעולה."},
    ],
    "contractors": [
        {"day": 2, "message": "שלום, האם קיבלת את הצעת המחיר? נשמח לענות על שאלות."},
        {"day": 5, "message": "שלום, יש לנו מבצע השבוע לקבלנים. מעניין?"},
    ],
    "general": [
        {"day": 3,  "message": "שלום, רציתי לעקוב אחרי הפנייה שלי."},
        {"day": 7,  "message": "שלום, עדיין זמינים לשיחה."},
    ],
}


# ── Core functions ────────────────────────────────────────────────────────────

def detect_domain(goal: str) -> str:
    gl = goal.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in gl for kw in keywords):
            return domain
    return "default"


def detect_metric(goal: str) -> str:
    if any(w in goal for w in ["מכירות", "הכנסות", "כסף", "רווח"]):
        return "revenue"
    if any(w in goal for w in ["לידים", "לקוחות", "פניות"]):
        return "leads"
    if any(w in goal for w in ["פגישות"]):
        return "meetings"
    return "revenue"


def decompose_goal(raw_goal: str) -> dict:
    """Returns goal dict with tracks ready for DB storage."""
    domain  = detect_domain(raw_goal)
    metric  = detect_metric(raw_goal)
    tracks_tmpl = DOMAIN_TRACKS.get(domain, DOMAIN_TRACKS["default"])
    tracks = []
    for t in tracks_tmpl:
        track = copy.deepcopy(t)
        track["track_id"] = str(uuid.uuid4())
        tracks.append(track)
    return {
        "goal_id":        str(uuid.uuid4()),
        "raw_goal":       raw_goal,
        "domain":         domain,
        "primary_metric": metric,
        "tracks":         tracks,
    }


def identify_opportunities(goal_id: str, tracks: list) -> list:
    """Returns list of opportunity dicts."""
    opps = []
    for track in tracks:
        audience  = track.get("audience", "general")
        track_id  = track.get("track_id", "")
        channel   = track.get("channel", "whatsapp")
        templates = OPPORTUNITY_TEMPLATES.get(audience, OPPORTUNITY_TEMPLATES["general"])
        for tmpl in templates:
            opps.append({
                "opp_id":      str(uuid.uuid4()),
                "goal_id":     goal_id,
                "track_id":    track_id,
                "title":       tmpl["title"],
                "audience":    audience,
                "channel":     channel,
                "potential":   tmpl["potential"],
                "effort":      tmpl["effort"],
                "next_action": tmpl["next_action"],
                "status":      "open",
            })
    opps.sort(key=lambda o: (
        {"high": 0, "medium": 1, "low": 2}[o["potential"]],
        {"low": 0, "medium": 1, "high": 2}[o["effort"]],
    ))
    return opps


def build_research_summary(goal_id: str, domain: str, top_audience: str) -> dict:
    """Returns research summary dict."""
    profile  = AUDIENCE_PROFILES.get(top_audience, AUDIENCE_PROFILES["general"])
    insights = DOMAIN_INSIGHTS.get(domain, [])
    return {
        "goal_id":        goal_id,
        "audience":       top_audience,
        "pain_points":    profile["pain_points"],
        "motivations":    profile["motivations"],
        "channels":       profile["channels"],
        "message_tone":   profile["message_tone"],
        "insights":       insights,
        "created_at":     datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def build_asset_draft(goal_id: str, top_audience: str, channel: str) -> dict:
    """Returns asset draft dict with first message + portfolio."""
    msg_tmpl  = MESSAGE_TEMPLATES.get(top_audience, MESSAGE_TEMPLATES["general"])
    port_tmpl = PORTFOLIO_TEMPLATES.get(top_audience, PORTFOLIO_TEMPLATES["general"])
    try:
        from config.business_registry import get_active_business
        p = get_active_business()
        subject = msg_tmpl["subject"].replace("אלומיניום", p.domain)
        body = msg_tmpl["body"]
    except Exception:
        subject = msg_tmpl["subject"]
        body = msg_tmpl["body"]
    return {
        "goal_id":   goal_id,
        "audience":  top_audience,
        "channel":   channel,
        "message": {
            "subject": subject,
            "body":    body,
            "type":    "first_touch",
        },
        "portfolio": {
            "title":       port_tmpl["title"],
            "description": port_tmpl["description"],
            "highlights":  port_tmpl["highlights"],
        },
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def build_outreach_plan(goal_id: str, top_opp: dict) -> dict:
    """Returns outreach plan dict for the top opportunity."""
    audience = top_opp.get("audience", "general")
    steps    = FOLLOWUP_SEQUENCES.get(audience, FOLLOWUP_SEQUENCES["general"])
    return {
        "goal_id":     goal_id,
        "opp_id":      top_opp.get("opp_id", ""),
        "channel":     top_opp.get("channel", "whatsapp"),
        "target":      top_opp.get("title", ""),
        "next_action": top_opp.get("next_action", ""),
        "followup_sequence": [
            {
                "day":     s["day"],
                "message": s["message"],
                "channel": "whatsapp",
                "status":  "pending",
            }
            for s in steps
        ],
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
