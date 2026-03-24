"""
research_engine.py - Research and Asset Engine
Pure functions, no DB, no external deps.
"""
import datetime
import logging
from dataclasses import dataclass
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
        "title": "General Client",
        "description": "Potential client in construction and renovation",
        "pain_points": ["High costs", "Unreliable contractors", "Schedule delays"],
        "motivations": ["Dream home", "Property value", "Quality of life"],
        "objections": ["Too expensive", "Do not know the company", "Already have a contractor"],
        "best_channels": ["WhatsApp", "Email", "Referrals"],
        "best_times": ["Morning 9-11", "Evening 19-21"],
        "message_tone": "Professional and warm",
        "decision_maker": "Homeowner",
        "avg_deal_size": "15000-80000 NIS",
        "buying_cycle": "2-8 weeks"
    },
    "small_business": {
        "title": "Small Business Owner",
        "description": "Small business needing aluminum solutions for premises",
        "pain_points": ["Budget constraints", "Fast delivery needed", "Reliability"],
        "motivations": ["Professional image", "Durability", "Cost efficiency"],
        "objections": ["Price too high", "Timeline too long", "Unsure of quality"],
        "best_channels": ["WhatsApp", "Phone", "Email"],
        "best_times": ["Morning 8-10", "Afternoon 14-16"],
        "message_tone": "Direct and professional",
        "decision_maker": "Business owner",
        "avg_deal_size": "10000-50000 NIS",
        "buying_cycle": "1-4 weeks"
    },
    "contractor": {
        "title": "Building Contractor",
        "description": "Contractor looking for reliable aluminum supplier",
        "pain_points": ["Supplier reliability", "On-time delivery", "Consistent quality"],
        "motivations": ["Project completion", "Client satisfaction", "Profit margin"],
        "objections": ["Already have supplier", "Price", "Minimum order"],
        "best_channels": ["Phone", "WhatsApp", "In-person"],
        "best_times": ["Early morning 7-9", "Lunch 12-13"],
        "message_tone": "Practical and direct",
        "decision_maker": "Project manager or owner",
        "avg_deal_size": "30000-200000 NIS",
        "buying_cycle": "1-2 weeks"
    },
    "architect": {
        "title": "Architect",
        "description": "Architect specifying aluminum products for projects",
        "pain_points": ["Product specs accuracy", "Lead times", "Custom solutions"],
        "motivations": ["Design integrity", "Client satisfaction", "Project success"],
        "objections": ["Not familiar with brand", "Samples needed", "Certification"],
        "best_channels": ["Email", "In-person meeting", "LinkedIn"],
        "best_times": ["Weekday mornings", "After lunch 13-15"],
        "message_tone": "Technical and precise",
        "decision_maker": "Principal architect",
        "avg_deal_size": "50000-500000 NIS",
        "buying_cycle": "4-12 weeks"
    },
    "photography": {
        "title": "Photography Studio",
        "description": "Photography business needing aluminum frames and structures",
        "pain_points": ["Custom sizing", "Aesthetic finish", "Budget"],
        "motivations": ["Studio aesthetics", "Durability", "Professional look"],
        "objections": ["Price", "Lead time", "Not standard size"],
        "best_channels": ["Instagram", "WhatsApp", "Email"],
        "best_times": ["Afternoon 14-18", "Weekends"],
        "message_tone": "Creative and visual",
        "decision_maker": "Studio owner",
        "avg_deal_size": "5000-30000 NIS",
        "buying_cycle": "2-6 weeks"
    }
}

MARKETS = {
    "default": {
        "market_size": "Large market",
        "growth_trend": "Stable growth",
        "players": [
            {"name": "Competitor A", "strength": "Price", "weakness": "Service", "our_edge": "Quality and speed"},
            {"name": "Competitor B", "strength": "Reputation", "weakness": "Availability", "our_edge": "Personal service"}
        ],
        "opportunities": ["Growing market", "High demand", "Few quality competitors"],
        "threats": ["Material costs", "Skilled labor shortage"],
        "our_position": "Quality provider with personal service"
    },
    "photography": {
        "market_size": "Medium niche market",
        "growth_trend": "Growing with content creation boom",
        "players": [
            {"name": "Large studios", "strength": "Brand", "weakness": "Price", "our_edge": "Flexibility and custom work"},
            {"name": "Freelancers", "strength": "Price", "weakness": "Reliability", "our_edge": "Professional setup and warranty"}
        ],
        "opportunities": ["Events market", "Corporate demand", "Social media content creation"],
        "threats": ["Smartphone cameras", "AI image generation"],
        "our_position": "Professional aluminum structures for studios"
    },
    "aluminum": {
        "market_size": "Large construction market",
        "growth_trend": "Strong growth with construction boom",
        "players": [
            {"name": "Large manufacturers", "strength": "Scale", "weakness": "Custom work", "our_edge": "Custom solutions fast"},
            {"name": "Local shops", "strength": "Price", "weakness": "Quality", "our_edge": "Quality plus reliability"}
        ],
        "opportunities": ["New construction projects", "Renovation wave", "Green building trend"],
        "threats": ["Raw material prices", "Import competition"],
        "our_position": "Custom aluminum specialist"
    },
    "construction": {
        "market_size": "Very large market",
        "growth_trend": "Strong consistent growth",
        "players": [
            {"name": "National chains", "strength": "Brand and scale", "weakness": "Personal service", "our_edge": "Local expertise"},
            {"name": "Small local shops", "strength": "Relationships", "weakness": "Capacity", "our_edge": "Quality and capacity"}
        ],
        "opportunities": ["Infrastructure projects", "Private construction boom", "Commercial renovation"],
        "threats": ["Economic slowdown", "Material price volatility"],
        "our_position": "Reliable regional aluminum partner"
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
        log.error("build_client_profile error: %s", e)
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
        log.error("build_market_map error: %s", e)
        raise


def build_collaboration_proposal(audience: str, contact_name: str = "") -> CollaborationProposal:
    try:
        name = contact_name or audience
        full = "Hello " + name + ",\n\nWe offer professional aluminum solutions.\n\nLooking forward to speaking with you."
        return CollaborationProposal(
            audience=audience,
            subject="Collaboration Proposal - " + audience,
            opening="Hello " + name,
            value_prop="Professional aluminum solutions at competitive prices",
            call_to_action="Schedule a quick call",
            full_text=full
        )
    except Exception as e:
        log.error("build_collaboration_proposal error: %s", e)
        raise


def build_sales_script(audience: str, stage: str = "first_contact") -> SalesScript:
    try:
        return SalesScript(
            audience=audience,
            stage=stage,
            opener="Hello, I am reaching out about your aluminum project",
            questions=[
                "What stage is your construction at?",
                "What work are you planning?",
                "What is your approximate budget?"
            ],
            objections={
                "expensive": "Price includes full warranty and service",
                "unknown": "We have dozens of projects in your area"
            },
            closer="I can send a quote within 24 hours",
            full_script="Full sales script for stage " + stage
        )
    except Exception as e:
        log.error("build_sales_script error: %s", e)
        raise


def build_landing_page_copy(audience: str) -> LandingPageCopy:
    try:
        return LandingPageCopy(
            audience=audience,
            headline="Professional Aluminum Solutions for Your Home",
            subheadline="Windows, doors, pergolas and railings - all in one place",
            benefits=[
                "Custom manufacturing",
                "Professional installation",
                "Full warranty",
                "Fair pricing"
            ],
            social_proof="Over 500 successful projects",
            cta="Get a free quote",
            full_copy="Full landing page for audience " + audience
        )
    except Exception as e:
        log.error("build_landing_page_copy error: %s", e)
        raise


def build_niche_portfolio(audience: str) -> NichePortfolio:
    try:
        return NichePortfolio(
            audience=audience,
            title="Portfolio - " + audience,
            description="Selected aluminum projects",
            highlights=["Precise work", "Quality materials", "On-time delivery"],
            projects=[
                {"name": "Sample project", "location": "Center", "scope": "Pergola and railings"}
            ],
            cta="Contact us for your project"
        )
    except Exception as e:
        log.error("build_niche_portfolio error: %s", e)
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
        log.error("full_research_package error: %s", e)
        raise
