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
from typing import List
from config.settings import COMPANY_NAME

log = logging.getLogger(__name__)


class SEOEngine:

    def generate_meta_descriptions(self) -> dict:
        return {
            "home":     "אשבל אלומיניום – מפעל לייצור והתקנה של חלונות, דלתות ופרגולות. עובדים עם קבלנים ואדריכלים בכל הארץ.",
            "products": "מערכות אלומיניום מקצועיות: חלונות בלגיים, מערכות הזזה, פרגולות וחיפויים. פתרונות לבנייה פרטית ומסחרית.",
            "about":    "אשבל אלומיניום – מפעל בניצני עוז. ניסיון של שנים בביצוע פרויקטים מורכבים עם אדריכלים וקבלנים.",
            "process":  "תהליך העבודה של אשבל אלומיניום: ממדידה ותכנון ועד ייצור, התקנה ומסירה. שירות מקצועי ואמין.",
            "knowledge":"מרכז הידע של אשבל אלומיניום: מדריכים לבחירת חלונות, טיפים לתחזוקה ומידע מקצועי.",
            "contact":  "צרו קשר עם אשבל אלומיניום לייעוץ טכני, הצעת מחיר או תיאום פגישה. זמינים לקבלנים ואדריכלים.",
        }

    def generate_city_pages(self) -> list:
        return [
            {
                "slug":     "aluminium-nes-ziona",
                "title":    "אלומיניום נס ציונה | אשבל אלומיניום",
                "h1":       "חלונות ודלתות אלומיניום בנס ציונה",
                "content":  "אשבל אלומיניום מספק שירותי ייצור והתקנה של מערכות אלומיניום בנס ציונה והסביבה. עובדים עם קבלנים, אדריכלים ובונים פרטיים.",
                "keywords": ["אלומיניום נס ציונה", "חלונות נס ציונה", "קבלן אלומיניום נס ציונה"],
            },
            {
                "slug":     "aluminium-rehovot",
                "title":    "אלומיניום רחובות | אשבל אלומיניום",
                "h1":       "חלונות ודלתות אלומיניום ברחובות",
                "content":  "אשבל אלומיניום – ספק מוביל למערכות אלומיניום באזור רחובות. חלונות בלגיים, מערכות הזזה ופרגולות.",
                "keywords": ["אלומיניום רחובות", "חלונות רחובות", "פרגולה אלומיניום רחובות"],
            },
            {
                "slug":     "aluminium-beer-sheva",
                "title":    "אלומיניום באר שבע | אשבל אלומיניום",
                "h1":       "מערכות אלומיניום בבאר שבע והנגב",
                "content":  "פתרונות אלומיניום מקצועיים לאזור הדרום. אשבל אלומיניום מספק שירות לקבלנים ואדריכלים בבאר שבע וסביבתה.",
                "keywords": ["אלומיניום באר שבע", "חלונות באר שבע", "קבלן אלומיניום דרום"],
            },
            {
                "slug":     "aluminium-tel-aviv",
                "title":    "אלומיניום תל אביב | אשבל אלומיניום",
                "h1":       "חלונות ומערכות אלומיניום בתל אביב",
                "content":  "אשבל אלומיניום מבצע פרויקטי אלומיניום בתל אביב והמרכז. מתמחים בבנייה מסחרית ופרטית.",
                "keywords": ["אלומיניום תל אביב", "חלונות בלגיים תל אביב", "מערכות הזזה תל אביב"],
            },
        ]

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
                    "אשבל אלומיניום מספק הצעות מחיר ללא התחייבות."
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
                    "אשבל אלומיניום ממליץ בהתאם לפתח ולצרכי המשפחה."
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
                    "אשבל אלומיניום: מפעל עצמאי, ניסיון בפרויקטים מורכבים, אחריות מלאה."
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
