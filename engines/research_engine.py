"""
research_engine.py — Research & Asset Engine
Pure functions, no DB, no external deps.
"""
import datetime, logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

log = logging.getLogger(__name__)

@dataclass
class ClientProfile:
    audience: str
    title: str
    description: str
    pain_points: List[str]
    motivations: List[str]
    objections: List[str]
    best_channels: List[str]
    best_times: List[str]
    message_tone: str
    decision_maker: str
    avg_deal_size: str
    buying_cycle: str

@dataclass
class MarketPlayer:
    name: str
    strength: str
    weakness: str
    our_edge: str

@dataclass
class MarketMap:
    domain: str
    market_size: str
    growth_trend: str
    players: List[MarketPlayer]
    opportunities: List[str]
    threats: List[str]
    our_position: str

@dataclass
class CollaborationProposal:
    audience: str
    subject: str
    opening: str
    value_prop: str
    call_to_action: str
    full_text: str

@dataclass
class SalesScript:
    audience: str
    stage: str
    opener: str
    questions: List[str]
    objections: Dict[str, str]
    closer: str
    full_script: str

@dataclass
class LandingPageCopy:
    audience: str
    headline: str
    subheadline: str
    benefits: List[str]
    social_proof: str
    cta: str
    full_copy: str

@dataclass
class NichePortfolio:
    audience: str
    title: str
    description: str
    highlights: List[str]
    projects: List[Dict]
    cta: str

@dataclass
class ResearchPackage:
    goal_id: str
    domain: str
    audience: str
    channel: str
    profile: Optional[ClientProfile] = None
    market: Optional[MarketMap] = None
    proposal: Optional[CollaborationProposal] = None
    script: Optional[SalesScript] = None
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.datetime.utcnow().isoformat()


PROFILES = {
    "default": {
        "title": "לקוח כללי",
        "description": "לקוח פוטנציאלי בתחום הבנייה והשיפוצים",
        "pain_points": ["עלויות גבוהות", "קבלנים לא אמינים", "עיכובים בלו"ז"],
        "motivations": ["בית חלומות", "ערך נדל"ן", "איכות חיים"],
        "objections": ["יקר מדי", "לא מכיר את החברה", "כבר יש לי קבלן"],
        "best_channels": ["WhatsApp", "מייל", "המלצות"],
        "best_times": ["בוקר 9-11", "ערב 19-21"],
        "message_tone": "מקצועי וחם",
        "decision_maker": "בעל הבית",
        "avg_deal_size": "15,000-80,000 ש"ח",
        "buying_cycle": "2-8 שבועות"
    }
}

MARKETS = {
    "default": {
        "market_size": "שוק גדול",
        "growth_trend": "צמיחה יציבה",
        "players": [
            {"name": "מתחרה א", "strength": "מחיר", "weakness": "שירות", "our_edge": "איכות ומהירות"},
            {"name": "מתחרה ב", "strength": "מוניטין", "weakness": "זמינות", "our_edge": "שירות אישי"}
        ],
        "opportunities": ["שוק גדל", "ביקוש גבוה", "מעט מתחרים איכותיים"],
        "threats": ["עלות חומרים", "כוח אדם מיומן"],
        "our_position": "ספק איכות עם שירות אישי"
    }
}


def build_client_profile(audience: str, domain: str = "aluminum") -> ClientProfile:
    try:
        data = PROFILES.get(audience, PROFILES["default"])
        return ClientProfile(
            audience=audience,
            title=data["title"],
            description=data["description"],
            pain_points=data["pain_points"],
            motivations=data["motivations"],
            objections=data["objections"],
            best_channels=data["best_channels"],
            best_times=data["best_times"],
            message_tone=data["message_tone"],
            decision_maker=data["decision_maker"],
            avg_deal_size=data["avg_deal_size"],
            buying_cycle=data["buying_cycle"]
        )
    except Exception as e:
        log.error(f"build_client_profile error: {e}")
        raise


def build_market_map(domain: str) -> MarketMap:
    try:
        data = MARKETS.get(domain, MARKETS["default"])
        players = [MarketPlayer(**p) for p in data["players"]]
        return MarketMap(
            domain=domain,
            market_size=data["market_size"],
            growth_trend=data["growth_trend"],
            players=players,
            opportunities=data["opportunities"],
            threats=data["threats"],
            our_position=data["our_position"]
        )
    except Exception as e:
        log.error(f"build_market_map error: {e}")
        raise


def build_collaboration_proposal(audience: str, contact_name: str = "") -> CollaborationProposal:
    try:
        name = contact_name or audience
        full = f"שלום {name},\n\nאנו מציעים שיתוף פעולה בתחום האלומיניום.\n\nנשמח לשוחח."
        return CollaborationProposal(
            audience=audience,
            subject=f"הצעת שיתוף פעולה — {audience}",
            opening=f"שלום {name}",
            value_prop="פתרונות אלומיניום מקצועיים במחיר תחרותי",
            call_to_action="נשמח לקבוע שיחה קצרה",
            full_text=full
        )
    except Exception as e:
        log.error(f"build_collaboration_proposal error: {e}")
        raise


def build_sales_script(audience: str, stage: str = "first_contact") -> SalesScript:
    try:
        return SalesScript(
            audience=audience,
            stage=stage,
            opener=f"שלום, אני פונה בנוגע לפרויקט האלומיניום שלכם",
            questions=["מה השלב הנוכחי בבנייה?", "אילו עבודות אתם מתכננים?", "מה התקציב המשוער?"],
            objections={"יקר": "המחיר כולל אחריות ושירות מלא", "לא מכיר": "יש לנו עשרות פרויקטים באזורכם"},
            closer="אוכל לשלוח הצעת מחיר תוך 24 שעות",
            full_script="תסריט מכירה מלא לשלב " + stage
        )
    except Exception as e:
        log.error(f"build_sales_script error: {e}")
        raise


def build_landing_page_copy(audience: str) -> LandingPageCopy:
    try:
        return LandingPageCopy(
            audience=audience,
            headline="פתרונות אלומיניום מקצועיים לבית שלך",
            subheadline="חלונות, דלתות, פרגולות ומעקות — הכל במקום אחד",
            benefits=["ייצור מותאם אישית", "התקנה מקצועית", "אחריות מלאה", "מחיר הוגן"],
            social_proof="מעל 500 פרויקטים מוצלחים",
            cta="קבל הצעת מחיר חינם",
            full_copy="עמוד נחיתה מלא לקהל " + audience
        )
    except Exception as e:
        log.error(f"build_landing_page_copy error: {e}")
        raise


def build_niche_portfolio(audience: str) -> NichePortfolio:
    try:
        return NichePortfolio(
            audience=audience,
            title=f"תיק עבודות — {audience}",
            description="פרויקטים נבחרים בתחום האלומיניום",
            highlights=["עבודה מדויקת", "חומרים איכותיים", "לוחות זמנים מדויקים"],
            projects=[{"name": "פרויקט לדוגמה", "location": "מרכז", "scope": "פרגולה + מעקות"}],
            cta="צור קשר לפרויקט שלך"
        )
    except Exception as e:
        log.error(f"build_niche_portfolio error: {e}")
        raise


def full_research_package(goal_id: str, domain: str, audience: str, channel: str) -> ResearchPackage:
    try:
        profile = build_client_profile(audience, domain)
        market = build_market_map(domain)
        proposal = build_collaboration_proposal(audience)
        script = build_sales_script(audience)
        return ResearchPackage(
            goal_id=goal_id,
            domain=domain,
            audience=audience,
            channel=channel,
            profile=profile,
            market=market,
            proposal=proposal,
            script=script,
            generated_at=datetime.datetime.utcnow().isoformat()
        )
    except Exception as e:
        log.error(f"full_research_package error: {e}")
        raise
