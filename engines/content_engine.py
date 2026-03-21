"""
ContentEngine — pure content construction logic.

No side effects. No event emission. No DB writes.
Stage 4: deterministic templates.
Stage 5: AI-generated via model_router.

Functions:
    build_post(content_type, topic, audience) -> str
    build_product_description(product, features) -> str
    build_email_newsletter(topic, highlights)     -> str
"""

import logging
from config.company_profile import COMPANY_CONTEXT
from config.settings        import COMPANY_NAME

log = logging.getLogger(__name__)

# Supported content types
LINKEDIN_POST    = "linkedin_post"
INSTAGRAM_POST   = "instagram_post"
BLOG_INTRO       = "blog_intro"
WEBSITE_CONTENT  = "website_content"
PRODUCT_DESC     = "product_description"
EMAIL_NEWSLETTER = "email_newsletter"


def build_post(content_type: str, topic: str,
                audience: str = "בעלי בתים ואדריכלים") -> str:
    """
    Build a marketing post for the given content_type and topic.
    Returns formatted string ready for use.
    """
    builder = _CONTENT_BUILDERS.get(content_type, _generic_content)
    return builder(topic, audience)


def _linkedin_post(topic: str, audience: str) -> str:
    return (
        f"🏗️ {topic} — אשבל אלומיניום\n\n"
        f"בשנים האחרונות ראינו עלייה משמעותית בביקוש ל{topic}.\n\n"
        f"ב-{COMPANY_NAME} אנחנו מביאים:\n"
        f"✅ חומרים איכותיים מספקים מובילים כמו קליל\n"
        f"✅ ביצוע מקצועי ועמידה בלוחות זמנים\n"
        f"✅ ייעוץ מותאם אישית לכל פרויקט\n\n"
        f"רוצים לדעת יותר? השאירו פרטים בתגובות 👇\n\n"
        f"#אלומיניום #בנייה #עיצובבית #{topic.replace(' ', '')}"
    )


def _instagram_post(topic: str, audience: str) -> str:
    return (
        f"✨ {topic} ✨\n\n"
        f"האלומיניום של אשבל — איכות שנראית 💎\n\n"
        f"חלונות • דלתות • פרגולות • מסתורים\n"
        f"הכל בהתאמה אישית לבית שלכם 🏠\n\n"
        f"📞 השאירו הודעה לקבלת הצעת מחיר\n\n"
        f"#אשבלאלומיניום #אלומיניום #עיצוב #בית #פרגולה"
    )


def _blog_intro(topic: str, audience: str) -> str:
    return (
        f"# {topic}\n\n"
        f"בחירת חומרים לבית היא אחת ההחלטות החשובות ביותר שתעשו. "
        f"כשמדובר ב{topic}, אלומיניום איכותי הוא הפתרון שמאזן בין "
        f"עמידות, אסתטיקה וחיסכון לאורך זמן.\n\n"
        f"במאמר זה נסביר מה חשוב לדעת לפני שמתחילים, "
        f"ומדוע {COMPANY_NAME} היא הבחירה המובילה בישראל."
    )


def _website_content(topic: str, audience: str) -> str:
    return (
        f"## {topic}\n\n"
        f"{COMPANY_NAME} מתמחה ב{topic} עבור בתים פרטיים ובניינים מסחריים. "
        f"אנחנו מציעים פתרונות מותאמים אישית עם חומרים מהשורה הראשונה.\n\n"
        f"**למה לבחור בנו?**\n"
        f"- ניסיון של שנים בתחום האלומיניום\n"
        f"- עבודה עם ספקים מובילים כמו קליל\n"
        f"- אחריות מלאה על כל עבודה\n"
        f"- מחירים תחרותיים ושקיפות מלאה"
    )


def _product_description(topic: str, audience: str) -> str:
    return (
        f"**{topic} — {COMPANY_NAME}**\n\n"
        f"מוצרי האלומיניום שלנו מיוצרים מחומרים איכותיים "
        f"העומדים בסטנדרטים הגבוהים ביותר.\n\n"
        f"מאפיינים עיקריים:\n"
        f"• עמידות גבוהה לתנאי מזג אוויר ישראליים\n"
        f"• פרופילים ממותג קליל ויצרנים מובילים\n"
        f"• התאמה אישית לכל מידה ועיצוב\n"
        f"• אחריות יצרן מלאה"
    )


def _email_newsletter(topic: str, audience: str) -> str:
    return (
        f"שלום,\n\n"
        f"בחודש האחרון ב{COMPANY_NAME} עסקנו רבות ב{topic}.\n\n"
        f"הנה מה שחדש:\n"
        f"• פרויקטים חדשים שהשלמנו בהצלחה\n"
        f"• טיפים לתחזוקת אלומיניום בבית\n"
        f"• מבצעים מיוחדים לחודש הקרוב\n\n"
        f"לפרטים נוספים — השיבו לאימייל זה או צרו קשר ישירות.\n\n"
        f"בברכה,\nצוות {COMPANY_NAME}"
    )


def _generic_content(topic: str, audience: str) -> str:
    return (
        f"תוכן שיווקי: {topic}\n\n"
        f"קהל יעד: {audience}\n"
        f"חברה: {COMPANY_NAME}\n\n"
        f"[תוכן מותאם יתווסף בשלב 5 עם model_router]"
    )


_CONTENT_BUILDERS = {
    LINKEDIN_POST:    _linkedin_post,
    INSTAGRAM_POST:   _instagram_post,
    BLOG_INTRO:       _blog_intro,
    WEBSITE_CONTENT:  _website_content,
    PRODUCT_DESC:     _product_description,
    EMAIL_NEWSLETTER: _email_newsletter,
}


def build_product_description(product: str, features: list = None) -> str:
    """Convenience wrapper for product descriptions."""
    features = features or []
    base = _product_description(product, "")
    if features:
        extras = "\n".join(f"• {f}" for f in features)
        base += f"\n\nמאפיינים נוספים:\n{extras}"
    return base


def build_email_newsletter(topic: str, highlights: list = None) -> str:
    """Convenience wrapper for newsletters with custom highlights."""
    highlights = highlights or []
    base = _email_newsletter(topic, "")
    if highlights:
        items = "\n".join(f"• {h}" for h in highlights)
        base = base.replace(
            "• פרויקטים חדשים שהשלמנו בהצלחה\n"
            "• טיפים לתחזוקת אלומיניום בבית\n"
            "• מבצעים מיוחדים לחודש הקרוב",
            items
        )
    return base
