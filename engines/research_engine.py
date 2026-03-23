"""
research_engine.py — Research & Asset Engine (Batch 7)
Pure functions — no DB writes, no side effects.
"""
import datetime, logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

log = logging.getLogger(__name__)

@dataclass
class ClientProfile:
    audience: str; title: str; description: str
    pain_points: List[str]; motivations: List[str]; objections: List[str]
    best_channels: List[str]; best_times: List[str]; message_tone: str
    decision_maker: str; avg_deal_size: str; buying_cycle: str

@dataclass
class MarketPlayer:
    name: str; strength: str; weakness: str; our_edge: str

@dataclass
class MarketMap:
    domain: str; market_size: str; growth_trend: str
    players: List[MarketPlayer]; opportunities: List[str]
    threats: List[str]; our_position: str

@dataclass
class CollaborationProposal:
    audience: str; subject: str; opening: str
    value_prop: str; call_to_action: str; full_text: str

@dataclass
class SalesScript:
    audience: str; stage: str; opener: str
    questions: List[str]; objections: Dict[str, str]
    closer: str; full_script: str

@dataclass
class LandingPageCopy:
    audience: str; headline: str; subheadline: str
    benefits: List[str]; social_proof: str; cta: str; full_copy: str

@dataclass
class NichePortfolio:
    audience: str; title: str; description: str
    highlights: List[str]; projects: List[Dict]; cta: str

@dataclass
class ResearchPackage:
    goal_id: str; domain: str; audience: str; channel: str; created_at: str
    client_profile: ClientProfile; market_map: MarketMap
    collaboration_proposal: CollaborationProposal; sales_script: SalesScript
    landing_page: LandingPageCopy; portfolio: NichePortfolio

CLIENT_PROFILES_DATA = {
    "architects": {
        "title": "אדריכלים ומעצבי פנים",
        "description": "אנשי מקצוע בתחום התכנון והעיצוב שמחפשים ספקים אמינים לחומרים איכותיים",
        "pain_points": ["ספקים שלא עומדים בזמנים","חומרים שלא תואמים לתכנון","חוסר גמישות בהתאמות","תקשורת לקויה עם ספקים","קושי למצוא ספקים שמבינים עיצוב"],
        "motivations": ["ספק אמין שנותן שקט נפשי","איכות גבוהה","גמישות עיצובית","מחיר הוגן","שיתוף פעולה ארוך טווח"],
        "objections": ["כבר יש לי ספק קבוע","המחיר שלכם גבוה","לא הכרתי אתכם — תראו עבודות","הזמנים שלי דחוקים"],
        "best_channels": ["whatsapp","email","linkedin","instagram"],
        "best_times": ["ראשון-שלישי 09:00-11:00","חמישי 14:00-16:00"],
        "message_tone": "מקצועי, מכבד, ויזואלי — עם דגש על איכות ואסתטיקה",
        "decision_maker": "האדריכל עצמו / מנהל המשרד",
        "avg_deal_size": "₪15,000-₪80,000 לפרויקט",
        "buying_cycle": "2-6 שבועות",
    },
    "contractors": {
        "title": "קבלנים ויזמים",
        "description": "קבלני בנייה ויזמי נדל"ן שצריכים ספק אלומיניום לכמויות גדולות",
        "pain_points": ["מחירים גבוהים","עיכובים באספקה","איכות לא אחידה","ספקים שלא נותנים אשראי","שירות לקוחות איטי"],
        "motivations": ["מחיר תחרותי לכמויות","אספקה בזמן","אחריות על איכות","תנאי אשראי נוחים","ספק שמכיר את הענף"],
        "objections": ["יש לי ספק זול יותר","מה תנאי האשראי?","אספקה תוך כמה ימים?","האם אתם יכולים לספק בכמויות קטנות?"],
        "best_channels": ["whatsapp","phone","email"],
        "best_times": ["ראשון 07:00-09:00","שלישי-חמישי 17:00-19:00"],
        "message_tone": "ישיר, עסקי, מספרים — מחיר, זמן, כמות",
        "decision_maker": "הקבלן הראשי / מנהל רכש",
        "avg_deal_size": "₪30,000-₪200,000 לפרויקט",
        "buying_cycle": "1-3 שבועות",
    },
    "private": {
        "title": "לקוחות פרטיים — שיפוצים",
        "description": "בעלי בתים ודירות שמתכננים שיפוץ או בנייה חדשה",
        "pain_points": ["לא יודעים כמה יעלה","פחד מקבלנים לא אמינים","לא מבינים בחומרים","חוויות רעות מהעבר","לוח זמנים לא ברור"],
        "motivations": ["מחיר שקוף","ביטחון ומוניטין","תוצאה יפה","ליווי מקצועי","ערבות על העבודה"],
        "objections": ["יקר לי","קיבלתי הצעה זולה יותר","כמה זמן זה ייקח?","אפשר לראות עבודות באזור?"],
        "best_channels": ["whatsapp","facebook","instagram","phone"],
        "best_times": ["ערב 20:00-22:00","שישי 10:00-12:00"],
        "message_tone": "חם, אישי, סיפורי — עם תמונות לפני/אחרי",
        "decision_maker": "בעל הבית + בן/בת זוג — החלטה משותפת",
        "avg_deal_size": "₪8,000-₪40,000 לפרויקט",
        "buying_cycle": "3-8 שבועות",
    },
    "general": {
        "title": "לקוח כללי",
        "description": "לקוח פוטנציאלי בתחום האלומיניום",
        "pain_points": ["עלות גבוהה","אמינות הספק"],
        "motivations": ["איכות","מחיר","שירות"],
        "objections": ["יקר מדי","לא מכיר אתכם"],
        "best_channels": ["whatsapp"],
        "best_times": ["בוקר 09:00-11:00"],
        "message_tone": "מקצועי וידידותי",
        "decision_maker": "הלקוח עצמו",
        "avg_deal_size": "₪10,000-₪50,000",
        "buying_cycle": "2-6 שבועות",
    },
}

MARKET_DATA = {
    "aluminum": {
        "market_size": "שוק האלומיניום בישראל — כ-₪2.5 מיליארד שנתי",
        "growth_trend": "צמיחה של ~12% בשנה — מונע ע"י בנייה ושיפוצים",
        "players": [
            {"name": "חברות גדולות (ורטיקל, אלקו)", "strength": "מוכרות, תשתית גדולה", "weakness": "שירות אישי נמוך", "our_edge": "שירות אישי, גמישות, מחיר תחרותי"},
            {"name": "קבלני אלומיניום מקומיים", "strength": "מחיר זול", "weakness": "חוסר מקצועיות", "our_edge": "מקצועיות + מחיר הוגן"},
            {"name": "יבואנים ישירים", "strength": "מחיר סיטונאי", "weakness": "זמני אספקה ארוכים", "our_edge": "זמינות מיידית, שירות מקומי"},
        ],
        "opportunities": [
            "ביקוש גובר מאדריכלים לפתרונות מותאמים",
            "פרויקטי התחדשות עירונית — TAMA38",
            "צמיחה בשוק הוילות והבתים הפרטיים",
            "ביקוש לפרגולות ואלומיניום לחוץ",
        ],
        "threats": [
            "תחרות מחיר מקבלנים לא מורשים",
            "עליות במחיר חומרי גלם",
            "האטה אפשרית בשוק הנדל"ן",
        ],
        "our_position": "ספק בוטיק — איכות גבוהה, שירות אישי, מחיר תחרותי",
    },
}

COLLABORATION_DATA = {
    "architects": {
        "subject": "שיתוף פעולה בתחום האלומיניום — הצעה לאדריכלים",
        "opening": "שלום {name},\n\nראיתי את הפרויקטים שלך והעבודה מרשימה מאוד.",
        "value_prop": "אנחנו מתמחים באלומיניום איכותי מותאם לדרישות אדריכליות.\n\n✅ התאמה לכל מידה ועיצוב\n✅ חומרים מאושרים עם אחריות\n✅ עמידה בלוחות זמנים\n✅ ליווי טכני מלא",
        "cta": "האם תרצה לקבל תיק עבודות מותאם לסגנון שלך?\nנשמח להיפגש לשיחת היכרות קצרה.",
    },
    "contractors": {
        "subject": "הצעת שיתוף פעולה — ספק אלומיניום לקבלנים",
        "opening": "שלום {name},\n\nאנחנו ספק אלומיניום מנוסה שעובד עם קבלנים פעילים.",
        "value_prop": "💰 מחירים תחרותיים לכמויות\n🚚 אספקה תוך 48-72 שעות\n📋 תנאי אשראי גמישים\n🔧 תמיכה טכנית זמינה",
        "cta": "האם תרצה הצעת מחיר לפרויקט הנוכחי?\nנשלח תוך 24 שעות.",
    },
    "private": {
        "subject": "פתרון אלומיניום לבית שלך — ייעוץ חינם",
        "opening": "שלום {name},\n\nשמענו שאתה מתכנן שיפוץ.",
        "value_prop": "✅ הצעת מחיר שקופה — ללא הפתעות\n✅ ביצוע מדויק לפי תוכנית\n✅ ערבות מלאה על העבודה\n✅ לקוחות מרוצים — עשרות המלצות",
        "cta": "רוצה ייעוץ ראשוני חינם?\nנבוא לראות את הנכס ולתת הצעת מחיר.",
    },
    "general": {
        "subject": "פנייה ראשונית — אשבל אלומיניום",
        "opening": "שלום {name},\n\nנשמח להכיר.",
        "value_prop": "אנחנו מתמחים באלומיניום איכותי עם שירות מקצועי ומחיר הוגן.",
        "cta": "האם תרצה לשמוע עוד?",
    },
}

SALES_SCRIPTS = {
    "architects": {
        "first_contact": {
            "opener": "היי {name}, אני מאשבל אלומיניום. ראיתי את הפרויקטים שלך — עבודה יפה מאוד. יש לי כמה שניות?",
            "questions": ["על איזה סוג פרויקטים אתה עובד בדרך כלל?","מה הכי חשוב לך בספק אלומיניום?","האם יש לך ספק קבוע עכשיו?"],
            "objections": {"יש לי ספק קבוע": "מבין. לא מבקש להחליף — רק להכיר לפרויקטים עתידיים.", "המחיר גבוה": "תרשה לי להראות מה כלול במחיר — לעתים ההבדל הוא באחריות.", "אין לי זמן": "אשלח תיק עבודות ב-WhatsApp — תסתכל כשנוח."},
            "closer": "אשלח לך תיק עבודות עם פרויקטים דומים לסגנון שלך. מתי נוח לשיחת המשך?",
        },
    },
    "contractors": {
        "first_contact": {
            "opener": "היי {name}, מאשבל אלומיניום. יש לי הצעה שיכולה לחסוך לך כסף על פרויקטים הבאים. דקה?",
            "questions": ["כמה פרויקטים אתה מנהל במקביל?","מה הנפח החודשי שלך באלומיניום?","עם מי אתה עובד עכשיו?"],
            "objections": {"יש לי ספק זול יותר": "מעניין. לפעמים ספק זול יותר עולה יותר — באחריות ובזמנים.", "אין לי זמן": "תן לי מידות לפרויקט ואחזיר הצעת מחיר תוך 24 שעות."},
            "closer": "שלח לי את המידות לפרויקט הנוכחי ואחזיר הצעה תוך 24 שעות.",
        },
    },
    "private": {
        "first_contact": {
            "opener": "היי {name}, מאשבל. ספר לי מה אתה מתכנן.",
            "questions": ["מה אתה מחפש בדיוק?","מה לוח הזמנים שלך?","יש כבר הצעות אחרות?"],
            "objections": {"יקר לי": "אנסח את ההצעה פריט פריט כדי שתראה בדיוק מה אתה משלם.", "קיבלתי הצעה זולה": "לפעמים ההבדל הוא בחומרים או בערבות. אפשר שתראה לי?"},
            "closer": "אבוא לראות את הנכס ביום {day} — מה מתאים לך?",
        },
    },
}

LANDING_PAGE_DATA = {
    "architects": {
        "headline": "אלומיניום שמדבר שפת עיצוב",
        "subheadline": "ספק שמבין אדריכלים — מדויק, אמין, גמיש",
        "benefits": ["התאמה מושלמת לכל תכנון","חומרים מאושרים עם אחריות","עמידה בלוחות זמנים","ליווי טכני מלא","פרויקטים מוצלחים עם אדריכלים מובילים"],
        "social_proof": ""אשבל הם הראשונים שבאמת מבינים מה אדריכל צריך" — אדריכל, תל אביב",
        "cta": "קבל תיק עבודות מותאם לסגנון שלך",
    },
    "contractors": {
        "headline": "אלומיניום לקבלנים — מחיר תחרותי, אספקה בזמן",
        "subheadline": "ספק שמכיר קבלנים ומדבר בשפה שלהם",
        "benefits": ["מחירים לכמויות — הנחות מדורגות","אספקה תוך 48 שעות","תנאי אשראי גמישים","מגוון רחב — כל פרופיל","תמיכה טכנית 6 ימים"],
        "social_proof": ""תמיד בזמן, תמיד איכות" — קבלן, חיפה",
        "cta": "קבל הצעת מחיר תוך 24 שעות",
    },
    "private": {
        "headline": "חלונות ודלתות אלומיניום — ללא הפתעות",
        "subheadline": "מחיר שקוף, ביצוע מדויק, ערבות מלאה",
        "benefits": ["הצעת מחיר מפורטת","ביצוע לפי תוכנית","ערבות 5 שנים","לקוחות מרוצים","תיאום גמיש"],
        "social_proof": ""עבודה מדהימה, מחיר הוגן, ממליץ בחום" — לקוח, ראשון לציון",
        "cta": "ייעוץ ראשוני חינם — נבוא אליך",
    },
    "general": {
        "headline": "אשבל אלומיניום — איכות ואמינות",
        "subheadline": "פתרונות אלומיניום מקצועיים לכל צורך",
        "benefits": ["איכות גבוהה","מחיר הוגן","שירות מקצועי","ניסיון רב"],
        "social_proof": "לקוחות מרוצים ממליצים עלינו",
        "cta": "צור קשר לייעוץ",
    },
}

NICHE_PORTFOLIOS = {
    "architects": {
        "title": "תיק עבודות — פרויקטים אדריכליים",
        "description": "פרויקטים שביצענו עבור אדריכלים — דיוק ועיצוב",
        "highlights": ["חזיתות אלומיניום מינימליסטיות","מערכות הזזה וקיפול","גדרות ומעקות בעיצוב מיוחד","פרגולות בהתאמה אישית","חיפוי קירות"],
        "projects": [{"name": "וילה בהרצליה פיתוח","type": "חלונות + דלתות הזזה","style": "מודרני"},{"name": "משרדים בתל אביב","type": "חזית אלומיניום + חיפוי","style": "מינימליסטי"},{"name": "בית פרטי ברמת השרון","type": "פרגולה + מסתור כביסה","style": "כפרי-מודרני"}],
        "cta": "רוצה לראות עבודות רלוונטיות? נשלח תיק מותאם.",
    },
    "contractors": {
        "title": "תיק עבודות — פרויקטי קבלנות",
        "description": "אספקה לפרויקטי בנייה — עם דגש על אמינות וזמנים",
        "highlights": ["אספקה לפרויקטי TAMA38","סדרת חלונות לבניינים","גדרות ומעקות בכמויות","חזיתות מסחריות"],
        "projects": [{"name": "בניין מגורים בחדרה","type": "40 יח' — חלונות + מרפסות","volume": "גדול"},{"name": "קומפלקס מסחרי בנתניה","type": "חזית + שערים","volume": "בינוני"}],
        "cta": "הצעת מחיר לפרויקט שלך תוך 24 שעות — שלח מידות.",
    },
    "private": {
        "title": "תיק עבודות — בתים ודירות",
        "description": "עבודות אלומיניום לבתים פרטיים — לפני ואחרי",
        "highlights": ["חלונות וויטרינות מודרניות","דלתות כניסה מרשימות","פרגולות לחצר ולמרפסת","סורגים בעיצוב מיוחד","מסתורי כביסה חכמים"],
        "projects": [{"name": "דירה בראשון לציון","type": "חלונות + סורגים","result": "לפני/אחרי מדהים"},{"name": "בית פרטי בכפר סבא","type": "פרגולה + גדר","result": "הפך את הגינה"}],
        "cta": "רוצה לראות עבודות באזור שלך?",
    },
    "general": {
        "title": "תיק עבודות — אשבל אלומיניום",
        "description": "מגוון פרויקטים שביצענו",
        "highlights": ["חלונות","דלתות","פרגולות","גדרות"],
        "projects": [],
        "cta": "צור קשר לפרטים נוספים.",
    },
}

def build_client_profile(audience: str, domain: str = "aluminum") -> ClientProfile:
    d = CLIENT_PROFILES_DATA.get(audience, CLIENT_PROFILES_DATA["general"])
    return ClientProfile(audience=audience, title=d["title"], description=d["description"], pain_points=d["pain_points"], motivations=d["motivations"], objections=d["objections"], best_channels=d["best_channels"], best_times=d["best_times"], message_tone=d["message_tone"], decision_maker=d["decision_maker"], avg_deal_size=d["avg_deal_size"], buying_cycle=d["buying_cycle"])

def build_market_map(domain: str) -> MarketMap:
    d = MARKET_DATA.get(domain, MARKET_DATA.get("aluminum", {}))
    if not d: return MarketMap(domain=domain, market_size="לא ידוע", growth_trend="לא ידוע", players=[], opportunities=[], threats=[], our_position="")
    players = [MarketPlayer(name=p["name"], strength=p["strength"], weakness=p["weakness"], our_edge=p["our_edge"]) for p in d.get("players", [])]
    return MarketMap(domain=domain, market_size=d["market_size"], growth_trend=d["growth_trend"], players=players, opportunities=d["opportunities"], threats=d["threats"], our_position=d["our_position"])

def build_collaboration_proposal(audience: str, contact_name: str = "") -> CollaborationProposal:
    d = COLLABORATION_DATA.get(audience, COLLABORATION_DATA["general"])
    name = contact_name or "שלום"
    opening = d["opening"].replace("{name}", name)
    full_text = f"{opening}\n\n{d['value_prop']}\n\n{d['cta']}\n\nבברכה,\nצוות אשבל אלומיניום"
    return CollaborationProposal(audience=audience, subject=d["subject"], opening=opening, value_prop=d["value_prop"], call_to_action=d["cta"], full_text=full_text)

def build_sales_script(audience: str, stage: str = "first_contact") -> SalesScript:
    aud = SALES_SCRIPTS.get(audience, SALES_SCRIPTS.get("private", {}))
    s = aud.get(stage, aud.get("first_contact", {}))
    if not s: return SalesScript(audience=audience, stage=stage, opener="שלום, מאשבל.", questions=[], objections={}, closer="נשמח לעזור.", full_script="")
    lines = [f"פתיחה: {s['opener']}", "", "שאלות:", *[f"  • {q}" for q in s.get("questions", [])], "", "התנגדויות:", *[f"  ❓ {o}\n     ✅ {a}" for o, a in s.get("objections", {}).items()], "", f"סגירה: {s['closer']}"]
    return SalesScript(audience=audience, stage=stage, opener=s["opener"], questions=s.get("questions", []), objections=s.get("objections", {}), closer=s["closer"], full_script="\n".join(lines))

def build_landing_page_copy(audience: str) -> LandingPageCopy:
    d = LANDING_PAGE_DATA.get(audience, LANDING_PAGE_DATA["general"])
    full = f"# {d['headline']}\n\n## {d['subheadline']}\n\n" + "\n".join(f"✅ {b}" for b in d["benefits"]) + f"\n\n{d['social_proof']}\n\n{d['cta']}"
    return LandingPageCopy(audience=audience, headline=d["headline"], subheadline=d["subheadline"], benefits=d["benefits"], social_proof=d["social_proof"], cta=d["cta"], full_copy=full)

def build_niche_portfolio(audience: str) -> NichePortfolio:
    d = NICHE_PORTFOLIOS.get(audience, NICHE_PORTFOLIOS["general"])
    return NichePortfolio(audience=audience, title=d["title"], description=d["description"], highlights=d["highlights"], projects=d["projects"], cta=d["cta"])

def full_research_package(goal_id: str, domain: str, audience: str, channel: str) -> ResearchPackage:
    return ResearchPackage(goal_id=goal_id, domain=domain, audience=audience, channel=channel, created_at=datetime.datetime.utcnow().isoformat(), client_profile=build_client_profile(audience, domain), market_map=build_market_map(domain), collaboration_proposal=build_collaboration_proposal(audience), sales_script=build_sales_script(audience, "first_contact"), landing_page=build_landing_page_copy(audience), portfolio=build_niche_portfolio(audience))
