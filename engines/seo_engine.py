"""
SEOEngine — pure SEO content structure builder.

No side effects. No event emission. No DB writes.
Stage 4: deterministic templates with keyword injection.
Stage 5: AI-generated content via model_router.

Functions:
    build_seo_structure(topic, keywords) -> dict
    build_meta(topic, keywords)          -> dict
    suggest_keywords(topic)              -> List[str]
"""

import logging
from typing import List
from config.settings import COMPANY_NAME

log = logging.getLogger(__name__)

# Default keywords per product category
_CATEGORY_KEYWORDS = {
    "חלונות":  ["חלונות אלומיניום", "חלון כפול זכוכית", "חלון בידוד אקוסטי"],
    "דלתות":   ["דלתות אלומיניום", "דלת כניסה", "דלת פנורמית"],
    "פרגולות": ["פרגולה אלומיניום", "פרגולה לגינה", "פרגולה מוטורית"],
    "מסתורים": ["מסתור כביסה אלומיניום", "מסתור לדירה", "מרפסת שמש"],
    "גדרות":   ["גדר אלומיניום", "גדר לבית פרטי", "גדר לגינה"],
    "חיפוי":   ["חיפוי קיר אלומיניום", "חיפוי חוץ", "קלאדינג אלומיניום"],
}


def build_seo_structure(topic: str, keywords: List[str] = None) -> dict:
    """
    Build a full SEO content structure for the given topic.
    Returns a dict with: title, meta_description, h1, outline, intro_paragraph.
    """
    if not keywords:
        keywords = suggest_keywords(topic)

    primary_kw = keywords[0] if keywords else topic
    kw_str     = ", ".join(keywords[:3])

    return {
        "title":            _build_title(topic, primary_kw),
        "meta_description": _build_meta_desc(topic, primary_kw),
        "h1":               _build_h1(topic),
        "keywords":         keywords,
        "outline":          _build_outline(topic),
        "intro_paragraph":  _build_intro(topic, primary_kw, kw_str),
    }


def build_meta(topic: str, keywords: List[str] = None) -> dict:
    """Build only the meta tags (title + description) for the topic."""
    if not keywords:
        keywords = suggest_keywords(topic)
    primary_kw = keywords[0] if keywords else topic
    return {
        "title":       _build_title(topic, primary_kw),
        "description": _build_meta_desc(topic, primary_kw),
        "keywords":    ", ".join(keywords),
    }


def suggest_keywords(topic: str) -> List[str]:
    """
    Return a list of suggested SEO keywords for the given topic.
    Matches against known categories; falls back to generic aluminium keywords.
    """
    topic_lower = topic.lower()
    for category, kws in _CATEGORY_KEYWORDS.items():
        if category in topic_lower or topic_lower in category:
            base = kws.copy()
            base.append(f"{topic} ישראל")
            base.append(f"{COMPANY_NAME}")
            return base

    # Generic fallback
    return [
        f"{topic} אלומיניום",
        f"{topic} לבית פרטי",
        f"{topic} ישראל",
        "אלומיניום איכותי",
        COMPANY_NAME,
    ]


# ── Private builders ──────────────────────────────────────────────────────────

def _build_title(topic: str, primary_kw: str) -> str:
    title = f"{primary_kw} — {COMPANY_NAME} | מומחים לאלומיניום"
    return title[:60] if len(title) > 60 else title


def _build_meta_desc(topic: str, primary_kw: str) -> str:
    desc = (f"{COMPANY_NAME} מתמחה ב{primary_kw}. "
            f"חומרים איכותיים, ביצוע מקצועי, מחירים תחרותיים. "
            f"קבלו הצעת מחיר ללא התחייבות.")
    return desc[:155] if len(desc) > 155 else desc


def _build_h1(topic: str) -> str:
    return f"{topic} — {COMPANY_NAME}"


def _build_outline(topic: str) -> list:
    return [
        f"מהו {topic} ולמה זה חשוב לבית שלכם?",
        f"סוגי {topic} — מה ההבדלים?",
        f"יתרונות אלומיניום על פני חומרים אחרים",
        f"כיצד בוחרים {topic} מקצועי?",
        f"אשבל אלומיניום — הניסיון שלנו ב{topic}",
    ]


def _build_intro(topic: str, primary_kw: str, kw_str: str) -> str:
    return (
        f"בחירת {primary_kw} היא החלטה חשובה שמשפיעה על המראה, "
        f"הבידוד והערך של הנכס שלכם. "
        f"ב-{COMPANY_NAME}, אנחנו מתמחים ב{kw_str} ומביאים ניסיון רב שנים "
        f"בביצוע פרויקטים מכל הסוגים — מבתים פרטיים ועד מבני מסחר. "
        f"במאמר זה נעזור לכם להבין מה חשוב לדעת לפני שמתחילים."
    )
