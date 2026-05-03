"""
skills/lead_intelligence.py — Lead Intelligence Skill
Phase 12: Lead Acquisition OS

Normalize, deduplicate, enrich, score, rank, and explain lead fit.
Stateless — all inputs explicit, returns plain dicts.

CONTRACT:
  normalize(raw: dict) -> NormalizedLead
  deduplicate(leads: list[NormalizedLead], existing: list[dict]) -> DedupeResult
  enrich(lead: NormalizedLead, context: dict) -> EnrichedLead
  score_lead(lead: EnrichedLead, weights: dict) -> ScoredLead
  rank_leads(leads: list[ScoredLead]) -> list[ScoredLead]
  explain_fit(lead: ScoredLead, goal: str) -> str
  extract_candidates(raw_signals: list[dict]) -> list[NormalizedLead]
"""

from __future__ import annotations
import re
import hashlib
from dataclasses import dataclass, field
from typing import Any


# ── Data contracts ────────────────────────────────────────────────────────────

@dataclass
class NormalizedLead:
    name:             str
    phone:            str  = ""
    email:            str  = ""
    city:             str  = ""
    company:          str  = ""
    role:             str  = ""
    source_type:      str  = ""
    source_url:       str  = ""
    segment:          str  = ""
    is_inbound:       bool = False
    work_type:        str  = ""
    project_stage:    str  = ""
    estimated_value:  int  = 0
    address:          str  = ""
    decision_maker:   str  = ""
    raw:              dict = field(default_factory=dict)
    fingerprint:      str  = ""   # dedup key


@dataclass
class DedupeResult:
    new_leads:     list[NormalizedLead]
    duplicates:    list[NormalizedLead]
    duplicate_of:  dict[str, str] = field(default_factory=dict)  # fingerprint -> existing_id


@dataclass
class EnrichedLead:
    lead:          NormalizedLead
    geo_fit:       float = 0.0    # 0-1
    role_fit:      float = 0.0
    signal_strength: float = 0.0  # detected buying signal
    enrichment_notes: list[str] = field(default_factory=list)


@dataclass
class ScoredLead:
    lead:          NormalizedLead
    score:         int    = 0     # 0-100
    priority:      str    = "low" # high | medium | low
    fit_reasons:   list[str] = field(default_factory=list)
    next_action:   str    = ""
    geo_fit_score: float  = 0.0


# ── Normalization ─────────────────────────────────────────────────────────────

_IL_PHONE_RE = re.compile(r"(?:\+?972|0)[-\s]?(?:5[0-9]|7[2-9]|[2-9])[-\s]?\d{3}[-\s]?\d{4}")
_EMAIL_RE    = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_CITY_VARIANTS: dict[str, str] = {
    "תל אביב": "תל אביב", "tel aviv": "תל אביב", "ta": "תל אביב",
    "ירושלים": "ירושלים", "jerusalem": "ירושלים",
    "חיפה": "חיפה", "haifa": "חיפה",
    "ראשון לציון": "ראשון לציון", "rishon": "ראשון לציון",
    "פתח תקווה": "פתח תקווה", "petah tikva": "פתח תקווה",
    "נתניה": "נתניה", "netanya": "נתניה",
    "באר שבע": "באר שבע", "beer sheva": "באר שבע",
    "אשדוד": "אשדוד", "ashdod": "אשדוד",
    "רמת גן": "רמת גן", "ramat gan": "רמת גן",
    "הרצליה": "הרצליה", "herzliya": "הרצליה",
}

_ROLE_KEYWORDS: dict[str, str] = {
    "אדריכל": "architects", "architect": "architects",
    "מעצב פנים": "interior_design", "interior designer": "interior_design",
    "קבלן": "contractors", "contractor": "contractors",
    "יזם": "developers", "developer": "developers",
    "מנהל פרויקט": "project_manager",
    "הנדסאי": "engineers",
}


def normalize(raw: dict[str, Any]) -> NormalizedLead:
    """Normalize a raw signal dict to a NormalizedLead."""
    text = str(raw.get("text") or raw.get("bio") or raw.get("description") or "")
    name  = _clean(raw.get("name") or _extract_name(text))
    phone = _clean(raw.get("phone") or _extract_phone(text))
    email = _clean(raw.get("email") or _extract_email(text))
    city  = _normalize_city(raw.get("city") or raw.get("location") or _extract_city(text))
    company = _clean(raw.get("company") or raw.get("organization") or "")
    role    = _normalize_role(raw.get("role") or raw.get("title") or _extract_role(text))
    segment = _infer_segment(role, raw.get("segment") or "")
    work_type = _clean(raw.get("work_type") or _extract_work_type(text))
    project_stage = _clean(raw.get("project_stage") or _extract_project_stage(text))
    estimated_value = _amount(raw.get("estimated_value") or raw.get("budget") or _extract_budget(text))
    address = _clean(raw.get("address") or "")
    decision_maker = _clean(raw.get("decision_maker") or raw.get("contact_person") or "")
    fp = _fingerprint(name, phone, email, company)

    return NormalizedLead(
        name=name or "לא ידוע",
        phone=phone,
        email=email,
        city=city,
        company=company,
        role=role,
        source_type=raw.get("source_type") or "",
        source_url=raw.get("source_url") or raw.get("url") or "",
        segment=segment,
        is_inbound=bool(raw.get("is_inbound")),
        work_type=work_type,
        project_stage=project_stage,
        estimated_value=estimated_value,
        address=address,
        decision_maker=decision_maker,
        raw=raw,
        fingerprint=fp,
    )


def extract_candidates(raw_signals: list[dict[str, Any]]) -> list[NormalizedLead]:
    """Normalize a batch of raw signals."""
    return [normalize(s) for s in raw_signals if s]


# ── Deduplication ──────────────────────────────────────────────────────────────

def deduplicate(
    leads: list[NormalizedLead],
    existing: list[dict[str, Any]] | None = None,
) -> DedupeResult:
    """
    Remove duplicates within the batch and against existing leads.
    existing = list of dicts with keys: phone, email, name (from DB).
    """
    existing = existing or []
    existing_fps = {
        _fingerprint(
            e.get("name", ""),
            e.get("phone", ""),
            e.get("email", ""),
            e.get("company", ""),
        ): e.get("id", "")
        for e in existing
    }

    seen: dict[str, NormalizedLead] = {}
    new_leads: list[NormalizedLead] = []
    dupes: list[NormalizedLead] = []
    dupe_of: dict[str, str] = {}

    for lead in leads:
        fp = lead.fingerprint
        if fp in existing_fps:
            dupes.append(lead)
            dupe_of[fp] = existing_fps[fp]
        elif fp in seen:
            dupes.append(lead)
        else:
            seen[fp] = lead
            new_leads.append(lead)

    return DedupeResult(new_leads=new_leads, duplicates=dupes, duplicate_of=dupe_of)


# ── Enrichment ────────────────────────────────────────────────────────────────

_HIGH_VALUE_CITIES = {"תל אביב", "ירושלים", "חיפה", "הרצליה", "רמת גן", "רעננה", "כפר סבא",
                       "גבעתיים", "פתח תקווה", "ראשון לציון", "נתניה", "מודיעין"}

_BUYING_SIGNAL_KEYWORDS = [
    "בונה", "מתכנן", "פרויקט חדש", "שיפוץ", "הרחבה", "בנייה",
    "מחפש", "צריך", "רוצה", "building", "renovation", "project", "new build",
]

_PROJECT_STAGE_WEIGHTS = {
    "ready": 1.0, "quote": 0.9, "proposal": 0.9, "measurements": 0.8,
    "planning": 0.65, "early": 0.45,
    "מוכן": 1.0, "הצעת מחיר": 0.9, "מדידה": 0.8, "תכנון": 0.65,
}

_WORK_TYPE_WEIGHTS = {
    "window": 0.7, "windows": 0.7, "door": 0.65, "balcony": 0.8,
    "villa": 0.95, "belgian": 0.9, "פרגולה": 0.7, "חלון": 0.7,
    "חלונות": 0.7, "דלת": 0.65, "מרפסת": 0.8, "וילה": 0.95,
    "בלגי": 0.9,
}


def enrich(lead: NormalizedLead, context: dict[str, Any] | None = None) -> EnrichedLead:
    """Add geo fit, role fit, signal strength, and notes."""
    ctx = context or {}
    geo_fit    = _compute_geo_fit(lead.city)
    role_fit   = _compute_role_fit(lead.segment)
    signal_str = _compute_signal(lead.raw)
    if lead.project_stage:
        signal_str = max(signal_str, _stage_fit(lead.project_stage))
    if lead.work_type:
        role_fit = max(role_fit, _work_type_fit(lead.work_type))
    notes: list[str] = []
    if geo_fit >= 0.8:
        notes.append(f"גאוגרפיה מעולה: {lead.city}")
    if role_fit >= 0.8:
        notes.append(f"תפקיד רלוונטי מאוד: {lead.role}")
    if signal_str >= 0.6:
        notes.append("אות קנייה חזק זוהה בטקסט")
    return EnrichedLead(
        lead=lead,
        geo_fit=geo_fit,
        role_fit=role_fit,
        signal_strength=signal_str,
        enrichment_notes=notes,
    )


# ── Scoring ───────────────────────────────────────────────────────────────────

_DEFAULT_WEIGHTS = {
    "geo_fit":        25,
    "role_fit":       30,
    "signal_strength": 20,
    "has_phone":      10,
    "has_email":      10,
    "is_inbound":      5,
}


def score_lead(enriched: EnrichedLead, weights: dict[str, int] | None = None) -> ScoredLead:
    """
    Score 0-100. Higher = better prospect.
    Optionally consults learned conversion stats from MemoryStore to bias
    inbound weight upward when historical data supports it.
    """
    w = dict(weights or _DEFAULT_WEIGHTS)  # copy so we can adjust

    # ── Learning-aware weight adjustment ─────────────────────────────────
    try:
        from memory.memory_store import MemoryStore
        seg = (enriched.lead.segment or "").lower()
        seg_stats = MemoryStore.read("leads", f"conversion_seg_{seg}", {})
        total = seg_stats.get("total", 0)
        if total >= 5:
            rate = seg_stats.get("converted", 0) / total
            # Boost or dampen signal_strength weight based on segment conversion history
            if rate >= 0.4:
                w["signal_strength"] = min(30, w.get("signal_strength", 20) + 5)
            elif rate < 0.15:
                w["signal_strength"] = max(10, w.get("signal_strength", 20) - 5)
    except Exception:
        pass

    raw_score = (
        enriched.geo_fit    * w.get("geo_fit", 25)
        + enriched.role_fit * w.get("role_fit", 30)
        + enriched.signal_strength * w.get("signal_strength", 20)
        + (1 if enriched.lead.phone else 0) * w.get("has_phone", 10)
        + (1 if enriched.lead.email else 0) * w.get("has_email", 10)
        + (1 if enriched.lead.is_inbound else 0) * w.get("is_inbound", 5)
    )
    if enriched.lead.estimated_value >= 50000:
        raw_score += 10
    elif enriched.lead.estimated_value >= 20000:
        raw_score += 5
    if enriched.lead.work_type:
        raw_score += int(_work_type_fit(enriched.lead.work_type) * 5)
    if enriched.lead.project_stage:
        raw_score += int(_stage_fit(enriched.lead.project_stage) * 8)
    score = min(100, int(raw_score))
    priority = "high" if score >= 70 else "medium" if score >= 40 else "low"
    reasons = list(enriched.enrichment_notes)
    if not reasons:
        reasons.append(f"ציון בסיס: {score}")
    if enriched.lead.work_type:
        reasons.append(f"סוג עבודה: {enriched.lead.work_type}")
    if enriched.lead.project_stage:
        reasons.append(f"שלב פרויקט: {enriched.lead.project_stage}")
    if enriched.lead.estimated_value:
        reasons.append(f"שווי משוער: ₪{enriched.lead.estimated_value:,}")

    # ── Segment-aware next action ─────────────────────────────────────────
    seg = (enriched.lead.segment or "").lower()
    if score >= 70:
        if enriched.lead.is_inbound:
            action = "ענה מיד — ליד חם שפנה אליך"
        elif "architect" in seg or "אדריכל" in seg:
            action = "שלח פרטי דגמים לאדריכל + הצע ביקור"
        elif "contractor" in seg or "קבלן" in seg:
            action = "שלח מחירון סיטונאי + הצע כינוס פרויקט"
        else:
            action = "שלח הצעת מחיר ראשונה + קבע פגישה"
    elif score >= 40:
        action = "שלח הודעת היכרות + בקש מידע נוסף"
    else:
        action = "שמור לסגמנט עתידי — נמוך עדיפות"

    return ScoredLead(
        lead=enriched.lead,
        score=score,
        priority=priority,
        fit_reasons=reasons,
        next_action=action,
        geo_fit_score=enriched.geo_fit,
    )


def rank_leads(leads: list[ScoredLead]) -> list[ScoredLead]:
    """Sort by score descending, inbound first."""
    return sorted(leads, key=lambda l: (l.lead.is_inbound, l.score), reverse=True)


def explain_fit(lead: ScoredLead, goal: str) -> str:
    """Return Hebrew explanation of why this lead fits the goal."""
    reasons = " | ".join(lead.fit_reasons) if lead.fit_reasons else "ניתוח בסיס"
    inbound_note = " (ליד נכנס — כבר יצר קשר)" if lead.lead.is_inbound else ""
    return (
        f"ליד: {lead.lead.name}{inbound_note}\n"
        f"ציון: {lead.score}/100 ({lead.priority})\n"
        f"התאמה למטרה '{goal}': {reasons}\n"
        f"פעולה מומלצת: {lead.next_action}"
    )


# ── Private helpers ────────────────────────────────────────────────────────────

def _clean(v: Any) -> str:
    return str(v).strip() if v else ""


def _fingerprint(name: str, phone: str, email: str, company: str) -> str:
    key = "|".join([
        re.sub(r"\s+", "", name).lower(),
        re.sub(r"[-\s]", "", phone),
        email.lower(),
        re.sub(r"\s+", "", company).lower(),
    ])
    return hashlib.md5(key.encode()).hexdigest()[:16]


def _extract_phone(text: str) -> str:
    m = _IL_PHONE_RE.search(text)
    return m.group(0) if m else ""


def _extract_email(text: str) -> str:
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else ""


def _extract_name(text: str) -> str:
    # Simple heuristic: first capitalized word(s)
    m = re.search(r"^([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", text)
    if m:
        return m.group(1)
    m = re.search(r"([א-ת]{2,8}\s[א-ת]{2,8})", text)
    return m.group(1) if m else ""


def _extract_city(text: str) -> str:
    tl = text.lower()
    for variant, canonical in _CITY_VARIANTS.items():
        if variant in tl:
            return canonical
    return ""


def _extract_role(text: str) -> str:
    tl = text.lower()
    for kw in _ROLE_KEYWORDS:
        if kw in tl:
            return kw
    return ""


def _normalize_city(city: str) -> str:
    if not city:
        return ""
    tl = city.strip().lower()
    return _CITY_VARIANTS.get(tl, city.strip())


def _normalize_role(role: str) -> str:
    if not role:
        return ""
    tl = role.strip().lower()
    for kw in _ROLE_KEYWORDS:
        if kw in tl:
            return kw
    return role.strip()


def _infer_segment(role: str, explicit: str) -> str:
    if explicit:
        return explicit
    return _ROLE_KEYWORDS.get(role.lower(), "")


def _compute_geo_fit(city: str) -> float:
    return 1.0 if city in _HIGH_VALUE_CITIES else 0.5 if city else 0.3


def _compute_role_fit(segment: str) -> float:
    fits = {"architects": 1.0, "interior_design": 0.9, "contractors": 0.85,
            "developers": 0.8, "project_manager": 0.7, "engineers": 0.65}
    return fits.get(segment, 0.4)


def _compute_signal(raw: dict) -> float:
    text = str(raw.get("text") or raw.get("bio") or raw.get("post") or raw.get("notes") or "").lower()
    hits = sum(1 for kw in _BUYING_SIGNAL_KEYWORDS if kw in text)
    return min(1.0, hits * 0.2)


def _extract_work_type(text: str) -> str:
    tl = text.lower()
    for keyword in _WORK_TYPE_WEIGHTS:
        if keyword in tl:
            return keyword
    return ""


def _extract_project_stage(text: str) -> str:
    tl = text.lower()
    for keyword in _PROJECT_STAGE_WEIGHTS:
        if keyword in tl:
            return keyword
    return ""


def _extract_budget(text: str) -> int:
    money = re.search(r"(?:₪|nis|ils)?\s?([\d,]{4,})", text.lower())
    return _amount(money.group(1)) if money else 0


def _amount(value: Any) -> int:
    digits = re.sub(r"[^\d]", "", str(value or ""))
    return int(digits) if digits else 0


def _stage_fit(stage: str) -> float:
    tl = (stage or "").lower()
    for keyword, value in _PROJECT_STAGE_WEIGHTS.items():
        if keyword in tl:
            return value
    return 0.5


def _work_type_fit(work_type: str) -> float:
    tl = (work_type or "").lower()
    for keyword, value in _WORK_TYPE_WEIGHTS.items():
        if keyword in tl:
            return value
    return 0.55
