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

log = logging.getLogger(__name__)

# Supported content types
LINKEDIN_POST    = "linkedin_post"
INSTAGRAM_POST   = "instagram_post"
BLOG_INTRO       = "blog_intro"
WEBSITE_CONTENT  = "website_content"
PRODUCT_DESC     = "product_description"
EMAIL_NEWSLETTER = "email_newsletter"


def _profile():
    try:
        from config.business_registry import get_active_business
        return get_active_business()
    except Exception:
        return None

def _biz() -> str:
    p = _profile()
    return p.name if p else "החברה שלנו"

def _domain() -> str:
    p = _profile()
    return p.domain if p else "עסק"

def _products() -> str:
    p = _profile()
    return p.products if p else "מוצרים ושירותים"

def _edge() -> str:
    p = _profile()
    return p.competitive_edge if p else "איכות, מקצועיות, שירות"


def build_post(content_type: str, topic: str,
                audience: str = "") -> str:
    """
    Build a marketing post for the given content_type and topic.
    Returns formatted string ready for use.
    """
    if not audience:
        p = _profile()
        audience = p.target_clients if p else "לקוחות"
    builder = _CONTENT_BUILDERS.get(content_type, _generic_content)
    return builder(topic, audience)


def _linkedin_post(topic: str, audience: str) -> str:
    biz = _biz()
    return (
        f"🏗️ {topic} — {biz}\n\n"
        f"בשנים האחרונות ראינו עלייה משמעותית בביקוש ל{topic}.\n\n"
        f"ב-{biz} אנחנו מביאים:\n"
        f"✅ {_edge()}\n"
        f"✅ ביצוע מקצועי ועמידה בלוחות זמנים\n"
        f"✅ ייעוץ מותאם אישית לכל פרויקט\n\n"
        f"רוצים לדעת יותר? השאירו פרטים בתגובות 👇\n\n"
        f"#{_domain().replace(' ', '')} #{topic.replace(' ', '')}"
    )


def _instagram_post(topic: str, audience: str) -> str:
    biz = _biz()
    products = _products()
    return (
        f"✨ {topic} ✨\n\n"
        f"{biz} — איכות שנראית 💎\n\n"
        f"{products}\n"
        f"הכל בהתאמה אישית עבורכם 🏠\n\n"
        f"📞 השאירו הודעה לקבלת הצעת מחיר\n\n"
        f"#{_domain().replace(' ', '')} #עיצוב #בית"
    )


def _blog_intro(topic: str, audience: str) -> str:
    biz = _biz()
    domain = _domain()
    return (
        f"# {topic}\n\n"
        f"בחירת ספק ל{domain} היא אחת ההחלטות החשובות ביותר שתעשו. "
        f"כשמדובר ב{topic}, {domain} איכותי הוא הפתרון שמאזן בין "
        f"עמידות, אסתטיקה וחיסכון לאורך זמן.\n\n"
        f"במאמר זה נסביר מה חשוב לדעת לפני שמתחילים, "
        f"ומדוע {biz} היא הבחירה המובילה."
    )


def _website_content(topic: str, audience: str) -> str:
    biz = _biz()
    domain = _domain()
    edge = _edge()
    return (
        f"## {topic}\n\n"
        f"{biz} מתמחה ב{topic} עבור {audience}. "
        f"אנחנו מציעים פתרונות מותאמים אישית עם חומרים מהשורה הראשונה.\n\n"
        f"**למה לבחור בנו?**\n"
        f"- {edge}\n"
        f"- אחריות מלאה על כל עבודה\n"
        f"- מחירים תחרותיים ושקיפות מלאה"
    )


def _product_description(topic: str, audience: str) -> str:
    biz = _biz()
    domain = _domain()
    return (
        f"**{topic} — {biz}**\n\n"
        f"מוצרי {domain} שלנו מיוצרים מחומרים איכותיים "
        f"העומדים בסטנדרטים הגבוהים ביותר.\n\n"
        f"מאפיינים עיקריים:\n"
        f"• עמידות גבוהה לתנאי שימוש ישראליים\n"
        f"• התאמה אישית לכל מידה ועיצוב\n"
        f"• אחריות יצרן מלאה"
    )


def _email_newsletter(topic: str, audience: str) -> str:
    biz = _biz()
    return (
        f"שלום,\n\n"
        f"בחודש האחרון ב{biz} עסקנו רבות ב{topic}.\n\n"
        f"הנה מה שחדש:\n"
        f"• פרויקטים חדשים שהשלמנו בהצלחה\n"
        f"• טיפים ועדכונים מקצועיים\n"
        f"• מבצעים מיוחדים לחודש הקרוב\n\n"
        f"לפרטים נוספים — השיבו לאימייל זה או צרו קשר ישירות.\n\n"
        f"בברכה,\nצוות {biz}"
    )


def _generic_content(topic: str, audience: str) -> str:
    return (
        f"תוכן שיווקי: {topic}\n\n"
        f"קהל יעד: {audience}\n"
        f"חברה: {_biz()}\n\n"
        f"[תוכן מותאם יתווסף עם model_router]"
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
            "• טיפים ועדכונים מקצועיים\n"
            "• מבצעים מיוחדים לחודש הקרוב",
            items
        )
    return base
