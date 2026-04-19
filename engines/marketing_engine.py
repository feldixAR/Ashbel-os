"""
marketing_engine.py — Profile-driven marketing recommendations engine.

Generates weekly/monthly marketing recommendations, campaign ideas,
content calendars, seasonal offers, and social post drafts.
All output is business-profile-aware.
"""
import logging
import datetime
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class MarketingRecommendation:
    category:   str
    title:      str
    body:       str
    channel:    str
    priority:   int = 1
    cta:        str = ""
    hashtags:   List[str] = field(default_factory=list)


@dataclass
class MarketingPlan:
    week_start:       str
    business_name:    str
    recommendations:  List[MarketingRecommendation] = field(default_factory=list)
    post_drafts:      List[dict] = field(default_factory=list)
    campaign_ideas:   List[str]  = field(default_factory=list)
    seasonal_notes:   List[str]  = field(default_factory=list)


def generate_weekly_plan(profile=None) -> MarketingPlan:
    """Generate this week's marketing plan from active business profile."""
    if profile is None:
        from config.business_registry import get_active_business
        profile = get_active_business()

    now   = datetime.datetime.now()
    month = now.month
    week  = now.strftime("%Y-%m-%d")

    recs  = _build_recommendations(profile, month)
    posts = _build_post_drafts(profile, month)
    ideas = _campaign_ideas(profile, month)
    seasonal = _seasonal_notes(profile, month)

    return MarketingPlan(
        week_start=week,
        business_name=profile.name,
        recommendations=recs,
        post_drafts=posts,
        campaign_ideas=ideas,
        seasonal_notes=seasonal,
    )


def _build_recommendations(profile, month: int) -> List[MarketingRecommendation]:
    recs = []
    name = profile.name

    # WhatsApp / messaging campaign
    recs.append(MarketingRecommendation(
        category="messaging",
        title="קמפיין הודעות שבועי",
        body=f"שלח הודעה ל-5 לידים חמים שלא ענו השבוע. הצע: {profile.top_offers[0] if profile.top_offers else 'ייעוץ חינם'}.",
        channel="whatsapp",
        priority=1,
        cta="שלח הודעה עכשיו",
    ))

    # Social content
    recs.append(MarketingRecommendation(
        category="social",
        title="פוסט שבועי ברשתות החברתיות",
        body=f"פרסם תמונת פרויקט אחרונה עם תיאור קצר. הדגש: {profile.competitive_edge}.",
        channel="instagram",
        priority=2,
        cta="צור פוסט",
        hashtags=[profile.domain.split()[0], profile.domain.split()[-1], "בית", "עיצוב"],
    ))

    # Follow-up on hot leads
    recs.append(MarketingRecommendation(
        category="crm",
        title="מעקב לידים חמים",
        body="עקוב אחרי לידים שפנו לפני 3-7 ימים ולא נסגרו. הצע פגישה קצרה.",
        channel="whatsapp",
        priority=1,
        cta="פתח תור מעקב",
    ))

    # Seasonal peak
    peaks = _active_peaks(profile, month)
    if peaks:
        recs.append(MarketingRecommendation(
            category="seasonal",
            title=f"עונת שיא — {peaks[0]}",
            body=f"זהו עונת ביקוש גבוה. הגבר פנייה ל{profile.target_clients.split(',')[0]}.",
            channel="all",
            priority=1,
            cta="הגבר קמפיין",
        ))

    return recs


def _build_post_drafts(profile, month: int) -> List[dict]:
    peaks = _active_peaks(profile, month)
    posts = []

    posts.append({
        "platform": "instagram",
        "type": "project_showcase",
        "caption": (
            f"✨ פרויקט חדש הסתיים!\n"
            f"{profile.products.split(',')[0]} בסגנון מודרני.\n"
            f"מחפשים {profile.domain}? צרו קשר היום ← 📞\n"
            f"#{profile.domain.replace(' ', '')} #עיצוב #בית"
        ),
    })

    posts.append({
        "platform": "facebook",
        "type": "offer",
        "caption": (
            f"🎯 {profile.top_offers[0] if profile.top_offers else 'מבצע מיוחד'} ל{profile.target_clients.split(',')[0]}!\n"
            f"{profile.competitive_edge}.\n"
            f"השאירו פרטים או שלחו הודעה ← 💬"
        ),
    })

    if peaks:
        posts.append({
            "platform": "instagram",
            "type": "seasonal",
            "caption": (
                f"🌸 {peaks[0]} — הזמן הנכון לשדרג!\n"
                f"{profile.name} כאן לכל שאלה."
            ),
        })

    return posts


def _campaign_ideas(profile, month: int) -> List[str]:
    ideas = [
        f"קמפיין הפניות: הצע {profile.top_offers[1] if len(profile.top_offers) > 1 else 'מתנה'} לכל לקוח שמפנה חבר",
        f"סרטון תהליך: הראה שלבי ייצור + התקנה של {profile.products.split(',')[0]}",
        f"מדריך: '5 דברים לדעת לפני בחירת {profile.domain}'",
        f"לפני-ואחרי: פרויקט {profile.target_clients.split(',')[0]}",
        f"שאלות ותשובות: שאלות נפוצות על {profile.domain}",
    ]
    return ideas


def _seasonal_notes(profile, month: int) -> List[str]:
    peaks = _active_peaks(profile, month)
    notes = []
    if peaks:
        notes.append(f"עונת שיא פעילה: {', '.join(peaks)}")
    if month in (12, 1, 2):
        notes.append(f"חורף: עונת ביקוש — הדגש חיסכון ופתרונות {profile.domain}")
    if month in (3, 4, 5):
        notes.append("אביב: עונת שיפוצים — הגבר פרסום")
    if month in (9, 10):
        notes.append("לאחר החגים: חזרה לשגרה — הצע הצעות מחיר מהירות")
    return notes or ["ללא עונת שיא פעילה כעת — שמור על נוכחות רגילה"]


def _active_peaks(profile, month: int) -> List[str]:
    active = []
    for peak in (profile.seasonal_peaks or []):
        months_str = peak.split("-")
        month_map = {
            "ינואר":1,"פברואר":2,"מרץ":3,"אפריל":4,"מאי":5,"יוני":6,
            "יולי":7,"אוגוסט":8,"ספטמבר":9,"אוקטובר":10,"נובמבר":11,"דצמבר":12,
        }
        for ms in months_str:
            for heb, num in month_map.items():
                if heb in ms and num == month:
                    active.append(peak)
    return active


def generate_marketing_report(profile=None) -> str:
    plan = generate_weekly_plan(profile)
    lines = [
        f"=== דוח שיווק שבועי — {plan.business_name} ===",
        f"שבוע: {plan.week_start}",
        "",
        "המלצות עיקריות:",
    ]
    for i, rec in enumerate(plan.recommendations, 1):
        lines.append(f"  {i}. [{rec.category}] {rec.title}")
        lines.append(f"     {rec.body}")
        lines.append(f"     ערוץ: {rec.channel} | פעולה: {rec.cta}")
    lines += ["", "רעיונות קמפיין:"]
    for idea in plan.campaign_ideas:
        lines.append(f"  • {idea}")
    if plan.seasonal_notes:
        lines += ["", "הערות עונתיות:"]
        for note in plan.seasonal_notes:
            lines.append(f"  → {note}")
    return "\n".join(lines)
