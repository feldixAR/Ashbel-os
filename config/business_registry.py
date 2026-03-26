
"""
business_registry.py — Multi-Business Registry (Batch 10)
Supports multiple business profiles — each with its own domain, scoring, and channels.
The active business is set via BUSINESS_ID env var (default: ashbel).
"""
import os, logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

@dataclass
class BusinessProfile:
    business_id:    str
    name:           str
    domain:         str
    products:       str
    target_clients: str
    market:         str
    competitive_edge: str
    primary_channel: str
    lead_score_weights: dict
    outreach_channels: List[str]
    avg_deal_size:  int
    currency:       str = "ILS"
    language:       str = "he"

BUSINESS_PROFILES: Dict[str, BusinessProfile] = {
    "ashbel": BusinessProfile(
        business_id="ashbel",
        name="אשבל אלומיניום",
        domain="עבודות אלומיניום",
        products="חלונות, דלתות, פרגולות, מסתורי כביסה, גדרות, חיפוי קירות, מבטחים",
        target_clients="בעלי בתים פרטיים, קבלנים, אדריכלים, מעצבי פנים, ועדי בתים",
        market="ישראל — בתים פרטיים, פרויקטים, בניינים מסחריים",
        competitive_edge="איכות גבוהה, מקצועיות, עמידה בלוחות זמנים, שירות אישי",
        primary_channel="whatsapp",
        lead_score_weights={
            "source": {"referral":30,"instagram":20,"facebook":15,"website":20,"whatsapp":25,"manual":10},
            "city_tier": {"tier_1":["תל אביב","רמת גן","גבעתיים","הרצליה","רעננה","כפר סבא","נתניה","ירושלים"],"tier_2":["חיפה","ראשון לציון","פתח תקווה","אשדוד","באר שבע","חולון","בת ים"],"tier_1_score":20,"tier_2_score":10,"other_score":5},
            "response_positive":25,"no_attempts_bonus":5,"repeated_no_response_penalty":-10,
        },
        outreach_channels=["whatsapp","email","sms"],
        avg_deal_size=15000,
    ),
    "dj": BusinessProfile(
        business_id="dj",
        name=os.environ.get("COMPANY_NAME", "DJ Business"),
        domain="אירועים ומוזיקה",
        products="הגברה, תאורה, DJ לאירועים, חתונות, בר מצוות, מסיבות, אירועי חברות",
        target_clients="זוגות מתחתנים, ארגוני אירועים, בעלי אולמות, חברות להפקת אירועים",
        market="ישראל — אירועים פרטיים, עסקיים, ציבוריים",
        competitive_edge="ניסיון, ציוד מקצועי, מגוון ז'אנרים, אמינות",
        primary_channel="instagram",
        lead_score_weights={
            "source": {
                "referral":     35,
                "instagram":    30,
                "tiktok":       25,
                "facebook":     20,
                "website":      15,
                "gig_platform": 20,
                "whatsapp":     25,
                "manual":       10,
            },
            "city_tier": {
                "tier_1": ["תל אביב", "רמת גן", "גבעתיים", "הרצליה",
                           "רעננה", "כפר סבא", "נתניה", "ירושלים"],
                "tier_2": ["חיפה", "ראשון לציון", "פתח תקווה",
                           "אשדוד", "באר שבע", "חולון", "בת ים"],
                "tier_1_score": 20,
                "tier_2_score": 10,
                "other_score":   5,
            },
            "response_positive": 25,
            "no_attempts_bonus":  5,
            "repeated_no_response_penalty": -10,
        },
        outreach_channels=["whatsapp", "instagram", "email"],
        avg_deal_size=4000,
    ),
    "demo_real_estate": BusinessProfile(
        business_id="demo_real_estate",
        name="נדל\"ן דמו",
        domain="נדל\"ן",
        products="דירות, בתים, מסחרי",
        target_clients="רוכשי דירות, משקיעים",
        market="ישראל",
        competitive_edge="מחיר, מיקום, שירות",
        primary_channel="whatsapp",
        lead_score_weights={
            "source":{"referral":35,"website":25,"facebook":15,"manual":10},
            "city_tier":{"tier_1":["תל אביב","הרצליה","רמת גן"],"tier_2":["חיפה","ירושלים"],"tier_1_score":25,"tier_2_score":15,"other_score":5},
            "response_positive":20,"no_attempts_bonus":5,"repeated_no_response_penalty":-10,
        },
        outreach_channels=["whatsapp","phone"],
        avg_deal_size=500000,
    ),
}

def get_active_business() -> BusinessProfile:
    """Get active business profile from env var."""
    biz_id = os.environ.get("BUSINESS_ID", "ashbel")
    profile = BUSINESS_PROFILES.get(biz_id)
    if not profile:
        log.warning(f"[BusinessRegistry] unknown BUSINESS_ID={biz_id}, using ashbel")
        profile = BUSINESS_PROFILES["ashbel"]
    return profile

def list_businesses() -> List[BusinessProfile]:
    return list(BUSINESS_PROFILES.values())

def get_business(business_id: str) -> Optional[BusinessProfile]:
    return BUSINESS_PROFILES.get(business_id)

# Active instance
active_business = get_active_business()
