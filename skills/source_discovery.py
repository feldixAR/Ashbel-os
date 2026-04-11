"""
skills/source_discovery.py — Source Discovery Skill
Phase 12: Lead Acquisition OS

Derives source types, segments, search intents, and community targets
from a business goal. Stateless — all inputs explicit, returns plain dicts.

CONTRACT:
  discover_sources(goal: str, business_profile: dict) -> DiscoveryPlan
  suggest_communities(segment: str, geo: str) -> list[CommunityTarget]
  build_search_intents(goal: str, segment: str) -> list[SearchIntent]
  detect_source_types(goal: str) -> list[str]
  rank_sources(sources: list[dict], segment: str) -> list[dict]
  explain_source_strategy(plan: dict) -> str
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# ── Data contracts ────────────────────────────────────────────────────────────

@dataclass
class SearchIntent:
    query:       str
    source_type: str          # linkedin | instagram | facebook | reddit | blog | directory | web
    language:    str = "he"   # he | en
    priority:    int = 5      # 1-10


@dataclass
class CommunityTarget:
    name:         str
    source_type:  str
    url_hint:     str = ""
    segment:      str = ""
    geo:          str = ""
    signal_type:  str = ""    # group | page | subreddit | forum | directory | blog


@dataclass
class DiscoveryPlan:
    goal:             str
    segments:         list[str]       = field(default_factory=list)
    source_types:     list[str]       = field(default_factory=list)
    communities:      list[CommunityTarget] = field(default_factory=list)
    search_intents:   list[SearchIntent]    = field(default_factory=list)
    outreach_strategy: str            = ""
    notes:            list[str]       = field(default_factory=list)


# ── Segment → source-type mapping ─────────────────────────────────────────────

_SEGMENT_SOURCES: dict[str, list[str]] = {
    "architects":      ["linkedin", "instagram", "professional_blog", "directory", "facebook_group"],
    "contractors":     ["linkedin", "facebook_group", "directory", "forum", "whatsapp_group"],
    "interior_design": ["instagram", "linkedin", "facebook_group", "pinterest", "blog"],
    "developers":      ["linkedin", "facebook_group", "directory", "professional_blog"],
    "homeowners":      ["facebook_group", "instagram", "yad2", "forum"],
    "business":        ["linkedin", "company_site", "directory", "google_maps"],
    "default":         ["linkedin", "facebook_group", "instagram", "directory", "google_maps"],
}

_SEGMENT_KEYWORDS: dict[str, list[str]] = {
    "architects":      ["אדריכל", "אדריכלות", "architect", "architecture", "עיצוב"],
    "contractors":     ["קבלן", "קבלנות", "contractor", "building", "בנייה"],
    "interior_design": ["מעצב פנים", "עיצוב פנים", "interior design", "interior designer"],
    "developers":      ["יזם", "יזמות", "נדל\"ן", "developer", "real estate"],
    "homeowners":      ["בית פרטי", "דירה", "שיפוץ", "renovation", "homeowner"],
    "business":        ["עסק", "חברה", "משרד", "office", "business"],
}

_GOAL_TO_SEGMENTS: dict[str, list[str]] = {
    "אדריכלים":     ["architects"],
    "קבלנים":       ["contractors"],
    "מעצבים":       ["interior_design"],
    "יזמים":        ["developers"],
    "בעלי בתים":    ["homeowners"],
    "עסקים":        ["business"],
    "architect":    ["architects"],
    "contractor":   ["contractors"],
    "developer":    ["developers"],
}

_SOURCE_COMMUNITIES: dict[str, list[tuple[str, str, str]]] = {
    # (name, url_hint, signal_type)
    "linkedin": [
        ("Israeli Architects & Designers", "linkedin.com/groups", "group"),
        ("קבלני בניין ישראל", "linkedin.com/groups", "group"),
        ("Israel Real Estate Professionals", "linkedin.com/groups", "group"),
        ("אדריכלות ועיצוב פנים - ישראל", "linkedin.com/groups", "group"),
    ],
    "facebook_group": [
        ("אדריכלים ומעצבי פנים ישראל", "facebook.com/groups", "group"),
        ("קבלנים ויזמי בנייה - ישראל", "facebook.com/groups", "group"),
        ("שיפוצים ובנייה - ישראל", "facebook.com/groups", "group"),
        ("נדל\"ן ויזמות - פורום ישראלי", "facebook.com/groups", "group"),
        ("מחפשי דירה ובית - ישראל", "facebook.com/groups", "group"),
    ],
    "instagram": [
        ("#אדריכלות", "instagram.com", "page"),
        ("#עיצוב_פנים", "instagram.com", "page"),
        ("#חלונות_ואלומיניום", "instagram.com", "page"),
        ("#בנייה_ישראל", "instagram.com", "page"),
    ],
    "directory": [
        ("דפי זהב — אדריכלים", "b144.co.il", "directory"),
        ("כל בו — קבלנים", "kalboo.co.il", "directory"),
        ("מדריך.קום — בנייה", "madrich.com", "directory"),
        ("ספר הזהב — אלומיניום", "gold-pages.co.il", "directory"),
    ],
    "forum": [
        ("דינמו — פורום בנייה", "dyno.co.il", "forum"),
        ("וואלה! בנייה ושיפוצים", "home.walla.co.il", "forum"),
        ("תפוז בנייה", "forum.tapuz.co.il", "forum"),
    ],
    "professional_blog": [
        ("בלוג אדריכלים ישראל", "", "blog"),
        ("אתרי חברות אדריכלות", "", "blog"),
        ("פורטל עיצוב ובנייה", "", "blog"),
    ],
}


# ── Public functions ───────────────────────────────────────────────────────────

def detect_source_types(goal: str) -> list[str]:
    """Return ordered list of source types relevant to a business goal."""
    tl = goal.lower()
    segments = _infer_segments(tl)
    types: list[str] = []
    for seg in segments:
        for t in _SEGMENT_SOURCES.get(seg, _SEGMENT_SOURCES["default"]):
            if t not in types:
                types.append(t)
    if not types:
        types = list(_SEGMENT_SOURCES["default"])
    return types


def _infer_segments(goal_lower: str) -> list[str]:
    segs: list[str] = []
    for kw, sg in _GOAL_TO_SEGMENTS.items():
        if kw in goal_lower:
            segs.extend(s for s in sg if s not in segs)
    return segs or ["default"]


def suggest_communities(segment: str, geo: str = "ישראל") -> list[CommunityTarget]:
    """Return community targets for a given segment."""
    sources = _SEGMENT_SOURCES.get(segment, _SEGMENT_SOURCES["default"])
    result: list[CommunityTarget] = []
    for src in sources:
        for name, url_hint, signal_type in _SOURCE_COMMUNITIES.get(src, []):
            result.append(CommunityTarget(
                name=name,
                source_type=src,
                url_hint=url_hint,
                segment=segment,
                geo=geo,
                signal_type=signal_type,
            ))
    return result


def build_search_intents(goal: str, segment: str) -> list[SearchIntent]:
    """Build prioritized search intent list for a goal + segment combo."""
    keywords = _SEGMENT_KEYWORDS.get(segment, [goal])
    sources = _SEGMENT_SOURCES.get(segment, _SEGMENT_SOURCES["default"])
    intents: list[SearchIntent] = []
    priority = 10
    for src in sources[:4]:
        for kw in keywords[:3]:
            intents.append(SearchIntent(
                query=f"{kw} {goal}".strip(),
                source_type=src,
                language="he" if any(c > '\u05FF' for c in kw) else "en",
                priority=priority,
            ))
            priority = max(1, priority - 1)
    return intents


def discover_sources(goal: str, business_profile: dict[str, Any] | None = None) -> DiscoveryPlan:
    """
    Top-level entry point. Given a business goal string, return a full DiscoveryPlan
    with segments, source types, communities, search intents, and outreach strategy.
    """
    profile = business_profile or {}
    tl = goal.lower()
    segments = _infer_segments(tl)
    source_types = detect_source_types(goal)
    communities: list[CommunityTarget] = []
    for seg in segments:
        communities.extend(suggest_communities(seg, geo=profile.get("city", "ישראל")))

    search_intents: list[SearchIntent] = []
    for seg in segments:
        search_intents.extend(build_search_intents(goal, seg))

    strategy = _build_outreach_strategy(segments, source_types, profile)

    return DiscoveryPlan(
        goal=goal,
        segments=segments,
        source_types=source_types,
        communities=communities[:12],
        search_intents=search_intents[:15],
        outreach_strategy=strategy,
        notes=_build_notes(source_types),
    )


def rank_sources(sources: list[dict], segment: str) -> list[dict]:
    """Rank source candidates by relevance to segment. Higher score = more relevant."""
    preferred = _SEGMENT_SOURCES.get(segment, _SEGMENT_SOURCES["default"])
    def _score(s: dict) -> int:
        st = s.get("source_type", "")
        try:
            return len(preferred) - preferred.index(st)
        except ValueError:
            return 0
    return sorted(sources, key=_score, reverse=True)


def explain_source_strategy(plan: DiscoveryPlan | dict) -> str:
    """Return a Hebrew explanation of the discovery strategy."""
    if isinstance(plan, dict):
        goal = plan.get("goal", "")
        segments = plan.get("segments", [])
        sources = plan.get("source_types", [])
    else:
        goal = plan.goal
        segments = plan.segments
        sources = plan.source_types

    seg_str = ", ".join(segments) if segments else "כללי"
    src_str = ", ".join(sources[:5]) if sources else "ערוצים שונים"
    return (
        f"עבור המטרה '{goal}', המערכת זיהתה פלחי יעד: {seg_str}. "
        f"מקורות המיקוד המומלצים: {src_str}. "
        f"מומלץ לפנות ל-LinkedIn ופייסבוק כנקודת פתיחה, "
        f"לאחר מכן ספריות מקצועיות ואינסטגרם."
    )


# ── Private helpers ────────────────────────────────────────────────────────────

def _build_outreach_strategy(segments: list[str], sources: list[str], profile: dict) -> str:
    channel = "LinkedIn" if "linkedin" in sources else "Facebook"
    seg = segments[0] if segments else "לקוחות פוטנציאליים"
    return (
        f"1. זיהוי {seg} פעילים ב-{channel} ובקבוצות פייסבוק רלוונטיות.\n"
        f"2. חיפוש פרופילים/פוסטים עם אות קנייה (שיפוץ, בנייה, פרויקט חדש).\n"
        f"3. פנייה ראשונית אישית + ערך מוסף ספציפי לאלומיניום.\n"
        f"4. מעקב תוך 48 שעות ללא מענה.\n"
        f"5. הצעת פגישה / שיחת היכרות קצרה."
    )


def _build_notes(sources: list[str]) -> list[str]:
    notes = [
        "גישה לפרופילים ציבוריים בלבד — ללא bypass של הרשאות.",
        "פנייה ראשונה תעבור אישור לפני שליחה.",
    ]
    if "instagram" in sources:
        notes.append("אינסטגרם: מעקב hashtags רלוונטיים + תגובות על פוסטים ציבוריים.")
    if "linkedin" in sources:
        notes.append("LinkedIn: חיפוש לפי תפקיד/תעשייה בפרופילים ציבוריים.")
    return notes
