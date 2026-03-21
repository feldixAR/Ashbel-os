"""
Ashbal Aluminium — company-specific constants used in agent prompts,
lead scoring, content generation, and routing decisions.
"""
from config.settings import (
    COMPANY_NAME, COMPANY_DOMAIN, COMPANY_PROFILE, TARGET_CLIENTS
)

COMPANY_CONTEXT = f"""
חברה: {COMPANY_NAME}
תחום: {COMPANY_DOMAIN}
מוצרים ושירותים: {COMPANY_PROFILE}
לקוחות יעד: {TARGET_CLIENTS}
שוק: ישראל — בתים פרטיים, פרויקטים, בניינים מסחריים
ספקים מרכזיים: קליל ואחרים
יתרון תחרותי: איכות גבוהה, מקצועיות, עמידה בלוחות זמנים
"""

# Lead scoring weights
LEAD_SCORE_WEIGHTS = {
    "source": {
        "referral":   30,
        "instagram":  20,
        "facebook":   15,
        "website":    20,
        "whatsapp":   25,
        "manual":     10,
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
}

# Outreach channels priority
OUTREACH_CHANNELS = ["whatsapp", "sms", "email"]

# Business hours (Israel)
BUSINESS_HOURS_START = 8    # 08:00
BUSINESS_HOURS_END   = 18   # 18:00
BUSINESS_DAYS        = [0, 1, 2, 3, 4]  # Mon–Fri (0=Mon in Python)
