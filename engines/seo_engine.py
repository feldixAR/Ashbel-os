"""
SEOEngine — Ashbal Aluminum SEO content builder.

Functions (original):
    build_seo_structure(topic, keywords) -> dict
    build_meta(topic, keywords)          -> dict
    suggest_keywords(topic)              -> List[str]

New class SEOEngine (Phase 9):
    generate_meta_descriptions() -> dict
    generate_city_pages()        -> list
    generate_blog_posts()        -> list
    generate_image_prompts()     -> list
"""

import logging
import re
from typing import List

log = logging.getLogger(__name__)


def _p():
    try:
        from config.business_registry import get_active_business
        return get_active_business()
    except Exception:
        return None

def _biz():
    p = _p(); return p.name if p else "החברה שלנו"
def _domain():
    p = _p(); return p.domain if p else "עסק"
def _products():
    p = _p(); return p.products if p else "מוצרים ושירותים"
def _targets():
    p = _p(); return p.target_clients if p else "לקוחות"
def _edge():
    p = _p(); return p.competitive_edge if p else "איכות ומקצועיות"
def _areas():
    p = _p(); return p.service_areas if p else []
def _keywords():
    p = _p(); return p.site_keywords if p else []
def _company_name():
    try:
        from config.settings import COMPANY_NAME
        return COMPANY_NAME
    except Exception:
        return _biz()


class SEOEngine:

    def generate_meta_descriptions(self) -> dict:
        biz = _biz(); domain = _domain(); products = _products()
        targets = _targets(); edge = _edge()
        return {
            "home":     f"{biz} – מתמחים ב{domain}. עובדים עם {targets} בכל הארץ.",
            "products": f"מוצרי {domain}: {products}. פתרונות לבנייה פרטית ומסחרית.",
            "about":    f"{biz} – {edge}. ניסיון של שנים בביצוע פרויקטים מורכבים.",
            "process":  f"תהליך העבודה של {biz}: ממדידה ותכנון ועד ביצוע ומסירה. שירות מקצועי ואמין.",
            "knowledge":f"מרכז הידע של {biz}: מדריכים, טיפים ומידע מקצועי על {domain}.",
            "contact":  f"צרו קשר עם {biz} לייעוץ, הצעת מחיר או תיאום פגישה. זמינים ל{targets}.",
        }

    def generate_city_pages(self) -> list:
        biz = _biz(); domain = _domain()
        areas = _areas() or ["תל אביב", "ירושלים", "חיפה"]
        kws = _keywords()
        pages = []
        for city in areas[:8]:
            slug = re.sub(r"[^\w]", "-", city.lower())
            kw_local = [f"{k} {city}" for k in (kws[:2] if kws else [domain])]
            pages.append({
                "slug":     f"{slug}",
                "title":    f"{domain} {city} | {biz}",
                "h1":       f"שירותי {domain} ב{city}",
                "content":  f"{biz} מספק שירותי {domain} ב{city} והסביבה. עובדים עם {_targets()}.",
                "keywords": kw_local + [f"קבלן {domain} {city}"],
            })
        return pages

    def generate_blog_posts(self) -> list:
        return [
            {
                "slug":    "kama-ole-chalon-aluminium",
                "title":   "כמה עולה חלון אלומיניום? מדריך מחירים לשנת 2026",
                "meta":    "מחירי חלונות אלומיניום לשנת 2026: חלונות ציר, בלגיים ומערכות הזזה. כל מה שצריך לדעת לפני שמזמינים.",
                "h1":      "כמה עולה חלון אלומיניום? מדריך מחירים מלא",
                "content": (
                    "חלונות אלומיניום הפכו לבחירה הנפוצה ביותר בבנייה ישראלית — הן בדירות חדשות והן בשיפוצים. "
                    "אבל מה העלות האמיתית?\n\n"
                    "**טווחי מחירים לשנת 2026:**\n"
                    "- חלון ציר רגיל (80×120 ס\"מ): ₪800–₪1,400\n"
                    "- חלון בלגי כפול-זכוכית: ₪1,200–₪2,200\n"
                    "- מערכת הזזה (2 מ' × 2.2 מ'): ₪3,500–₪6,000\n"
                    "- חלון פינתי ללא עמוד: ₪4,000–₪8,000\n\n"
                    "**גורמים שמשפיעים על המחיר:**\n"
                    "מידות החלון, סוג הזכוכית (יחידה/כפולה/משוריינת), "
                    "גוון הפרופיל, מנגנון הפתיחה, ורמת הבידוד האקוסטי.\n\n"
                    "**טיפים לקבלת הצעת מחיר:**\n"
                    "בקשו הצעה הכוללת ייצור, התקנה ואחריות. "
                    "השוו בין ספקים שמציגים מפרט טכני מלא. "
                    f"{_biz()} מספק הצעות מחיר ללא התחייבות."
                ),
            },
            {
                "slug":    "belgit-vs-hzaza",
                "title":   "חלון בלגי או מערכת הזזה? ההבדלים והיתרונות",
                "meta":    "השוואה בין חלונות בלגיים למערכות הזזה: מחיר, עיצוב, בידוד ותחזוקה. איזה מערכת מתאימה לבית שלך?",
                "h1":      "חלון בלגי מול מערכת הזזה – מה עדיף?",
                "content": (
                    "שתי המערכות הנפוצות ביותר בבנייה ישראלית — "
                    "אבל לכל אחת יתרונות שונים לחלוטין.\n\n"
                    "**חלון בלגי:**\n"
                    "נפתח כלפי חוץ. מתאים לחדרים פנימיים. "
                    "בידוד מצוין. עלות בינונית. פחות מתאים לפתחים גדולים.\n\n"
                    "**מערכת הזזה:**\n"
                    "חוסכת מקום. מתאימה לממ\"ד, סלון, מרפסת. "
                    "אידיאלית לחיבור פנים-חוץ. עלות גבוהה יותר אך ערך עיצובי גבוה.\n\n"
                    "**מה לבחור?**\n"
                    "לחדרי שינה וחדרי ילדים — חלון בלגי. "
                    "לסלון עם מרפסת או נוף — מערכת הזזה. "
                    f"{_biz()} ממליץ בהתאם לצרכים הספציפיים שלך."
                ),
            },
            {
                "slug":    "bechira-kablan-aluminium",
                "title":   "איך בוחרים ספק אלומיניום? 7 דברים שצריך לבדוק",
                "meta":    "מדריך לבחירת ספק אלומיניום: ניסיון, אחריות, מחיר ואיכות חומרים. טיפים מהשטח.",
                "h1":      "7 דברים שחייבים לבדוק לפני שבוחרים ספק אלומיניום",
                "content": (
                    "בחירת ספק אלומיניום לפרויקט בנייה היא החלטה שמשפיעה על לוחות הזמנים, "
                    "האיכות והתקציב. הנה מה שצריך לבדוק:\n\n"
                    "1. **ניסיון בפרויקטים דומים** — בקשו דוגמאות עבודה קודמות\n"
                    "2. **מפרט טכני מלא** — פרופיל, עובי, סוג זכוכית\n"
                    "3. **אחריות על ייצור והתקנה** — לא רק על חומרים\n"
                    "4. **לוח זמנים ריאלי** — אחור בספקות עוצר פרויקטים שלמים\n"
                    "5. **יכולת ייצור מקומית** — ספק שמייצר בעצמו שולט באיכות\n"
                    "6. **תגובה מהירה** — ספק שלא עונה לפני חתימה לא יענה אחריה\n"
                    "7. **מחיר כולל** — ייצור + התקנה + פינוי פסולת\n\n"
                    f"{_biz()}: {_edge()}. אחריות מלאה."
                ),
            },
        ]

    def generate_image_prompts(self) -> list:
        return [
            {
                "name":   "hero_belgian_windows",
                "prompt": "Photorealistic interior photograph, Israeli modern living room, floor-to-ceiling black aluminum Belgian-style windows, Mediterranean garden view, white plastered walls, light oak flooring, linen sofa, architecture book on coffee table, late afternoon golden light casting long shadows, Canon EOS R5 24mm f/2.8 eye level, architectural magazine quality, no overhead lighting",
            },
            {
                "name":   "sliding_doors_terrace",
                "prompt": "Photorealistic interior photograph, contemporary Israeli villa, large black aluminum lift-and-slide glass doors fully open to stone-paved terrace with olive trees, polished concrete floor, minimalist furniture, glass on windowsill, warm summer evening light, seamless indoor-outdoor, Sony A7R V 35mm f/2 eye level, lived-in not staged",
            },
            {
                "name":   "pergola_shabbat",
                "prompt": "Photorealistic exterior photograph, Israeli private home terrace, modern aluminum pergola with adjustable louvered roof, outdoor dining table set for dinner, warm string lights, Mediterranean garden bougainvillea background, late afternoon golden light, Sony A7R V 28mm f/2.8, architectural photography, no AI look",
            },
            {
                "name":   "commercial_facade",
                "prompt": "Photorealistic exterior architectural photograph, modern Israeli office building, floor-to-ceiling aluminum curtain wall system, dark anodized frames, glass reflecting blue sky and palm trees, sharp geometric lines, street level Canon EOS R5 17mm tilt-shift f/11 verticals corrected, Archdaily magazine style",
            },
            {
                "name":   "corner_window",
                "prompt": "Photorealistic interior photograph, Israeli luxury apartment, frameless corner aluminum window no corner post, seamless panoramic view of Tel Aviv skyline, minimal white interior, single armchair, morning light, wide angle architectural photography, Canon EOS R5 24mm",
            },
            {
                "name":   "shutters_hidden",
                "prompt": "Photorealistic exterior photograph, modern Israeli home facade, aluminum windows with hidden roller shutter boxes fully integrated into wall, clean minimal look, white plaster exterior, green garden, afternoon light, architectural photography style",
            },
            {
                "name":   "glass_wall_commercial",
                "prompt": "Photorealistic interior photograph, Israeli commercial lobby, floor-to-ceiling aluminum glass curtain wall system, large open space, polished stone floor, natural daylight flooding in, clean corporate architecture, wide angle Canon EOS R5 17mm f/8",
            },
            {
                "name":   "balcony_railing",
                "prompt": "Photorealistic exterior photograph, Israeli apartment building balcony, modern aluminum and glass railing system, Mediterranean sea view in background, clear blue sky, afternoon light, architectural detail photography, Canon EOS R5 50mm f/4",
            },
        ]


seo_engine = SEOEngine()

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
            base.append(_biz())
            return base

    # Generic fallback
    return [
        f"{topic} {_domain()}",
        f"{topic} לבית פרטי",
        f"{topic} ישראל",
        _domain(),
        _biz(),
    ]


# ── Private builders ──────────────────────────────────────────────────────────

def _build_title(topic: str, primary_kw: str) -> str:
    title = f"{primary_kw} — {_biz()} | מומחים ב{_domain()}"
    return title[:60] if len(title) > 60 else title


def _build_meta_desc(topic: str, primary_kw: str) -> str:
    desc = (f"{_biz()} מתמחה ב{primary_kw}. "
            f"{_edge()}. "
            f"קבלו הצעת מחיר ללא התחייבות.")
    return desc[:155] if len(desc) > 155 else desc


def _build_h1(topic: str) -> str:
    return f"{topic} — {_biz()}"


def _build_outline(topic: str) -> list:
    return [
        f"מהו {topic} ולמה זה חשוב?",
        f"סוגי {topic} — מה ההבדלים?",
        f"יתרונות {_domain()} על פני חומרים אחרים",
        f"כיצד בוחרים {topic} מקצועי?",
        f"{_biz()} — הניסיון שלנו ב{topic}",
    ]


def _build_intro(topic: str, primary_kw: str, kw_str: str) -> str:
    return (
        f"בחירת {primary_kw} היא החלטה חשובה שמשפיעה על המראה, "
        f"האיכות והערך של הנכס שלכם. "
        f"ב-{_biz()}, אנחנו מתמחים ב{kw_str} ומביאים ניסיון רב שנים "
        f"בביצוע פרויקטים מכל הסוגים — מבתים פרטיים ועד מבני מסחר. "
        f"במאמר זה נעזור לכם להבין מה חשוב לדעת לפני שמתחילים."
    )
