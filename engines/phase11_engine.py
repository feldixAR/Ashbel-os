"""
Phase 11 — Revenue Queue Scoring Engine
Pure functions. No I/O. No side effects.

Business states (with base score contribution):
  AWAITING_DEPOSIT      +25
  AWAITING_APPROVAL     +18
  AWAITING_MEASUREMENTS +15
  QUOTE_SENT            +12
  NEW_LEAD              +8
  BLOCKED_CRITICAL      -10  (only when essential data missing + no actionable next step)

Priority formula:
  value_score + geo_score + work_score + urgency_score + state_base_score
"""
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

# ── Samaria geo set ──────────────────────────────────────────────────────────
_SAMARIA_CITIES = {
    "אריאל", "אלפי מנשה", "קדומים", "קרני שומרון", "עמנואל",
    "בית אריה", "אורנית", "עץ אפרים", "חרמש", "מעלה שומרון",
    "כוכב יאיר", "צור יגאל", "מודיעין עילית", "ביתר עילית",
    "ariel", "alfei menashe", "kedumim", "karnei shomron", "immanuel",
}

# ── Work-type keyword sets ────────────────────────────────────────────────────
_PREMIUM_WORK_KW = {
    "וילה", "פרטי", "בלגי", "הזזה גדולה", "מינימליסט",
    "villa", "private", "belgian", "minimalist", "large sliding",
}
_COMPLEX_BALCONY_KW = {"מרפסת", "מרפסת מורכבת", "balcony", "complex balcony"}
_REPAIR_KW = {"תיקון", "תיקונים", "repair", "fix"}


# ── Phase 11 Business States ─────────────────────────────────────────────────
BUSINESS_STATES = {
    "AWAITING_DEPOSIT":      25,
    "AWAITING_APPROVAL":     18,
    "AWAITING_MEASUREMENTS": 15,
    "QUOTE_SENT":            12,
    "NEW_LEAD":               8,
    "BLOCKED_CRITICAL":     -10,
}


@dataclass
class Phase11Result:
    lead_id:         str
    lead_name:       str
    priority_score:  int
    priority_reason: str
    business_state:  str
    blocked_state:   bool
    blocked_reason:  Optional[str]
    next_best_action: str
    next_action_at:  str  # ISO-8601


# ── helpers ───────────────────────────────────────────────────────────────────

def _hours_since(iso_str: Optional[str]) -> float:
    """Return hours elapsed since iso_str (IL tz). Returns 9999 if None."""
    if not iso_str:
        return 9999.0
    try:
        # Accept naive or aware strings
        s = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0.0, (now - dt).total_seconds() / 3600)
    except Exception:
        return 9999.0


def _value_score(amount: int) -> int:
    if amount >= 100_000:
        return 35
    if amount >= 50_000:
        return 25
    if amount >= 20_000:
        return 12
    return 5


def _geo_score(city: Optional[str]) -> int:
    c = (city or "").strip().lower()
    if not c:
        return 0
    if c in {x.lower() for x in _SAMARIA_CITIES}:
        return 20
    # Acceptable non-core (any Israeli city that is not Samaria but not far)
    # "far" = not in typical Ashbal service area. We treat any city as acceptable
    # unless it's empty (unknown = 0 already handled above).
    return 8


def _work_score(text: str) -> int:
    t = text.lower()
    if any(kw in t for kw in _REPAIR_KW):
        return 0
    if any(kw in t for kw in _PREMIUM_WORK_KW):
        return 20
    if any(kw in t for kw in _COMPLEX_BALCONY_KW):
        return 15
    return 8  # regular


def _urgency_score(hours: float) -> int:
    if hours >= 48:
        return 20
    if hours >= 24:
        return 10
    return 0


def _map_business_state(lead, deal) -> str:
    """Map existing lead/deal status to Phase 11 business state."""
    if deal is not None:
        stage = (deal.stage or "").lower()
        cs    = (deal.commercial_stage or "").lower()
        if stage == "negotiation" or "מקדמה" in cs or "deposit" in cs or "פיקדון" in cs:
            return "AWAITING_DEPOSIT"
        if stage == "proposal":
            return "AWAITING_APPROVAL"
        if stage == "qualified":
            return "AWAITING_MEASUREMENTS"
        if stage in ("new", "won", "lost"):
            return "NEW_LEAD"

    # No deal — use lead status
    status = (lead.status or "").strip()
    notes  = (lead.notes or "").lower()
    resp   = (lead.response or "").lower()

    if status == "מתעניין":
        # Check if quote was sent (notes/response mention הצעה/מחיר/quote)
        if any(k in notes + resp for k in ("הצעה", "מחיר", "quote", "offer")):
            return "QUOTE_SENT"
        # Check if measurements mentioned
        if any(k in notes + resp for k in ("מידות", "מדידה", "measurements")):
            return "AWAITING_MEASUREMENTS"
        return "AWAITING_MEASUREMENTS"  # default next step for interested lead

    if status in ("חדש", "ניסיון קשר"):
        return "NEW_LEAD"

    # Closed leads shouldn't appear in queue — caller should filter
    return "NEW_LEAD"


def _is_blocked(lead, deal) -> tuple[bool, Optional[str]]:
    """Return (blocked, reason). BLOCKED_CRITICAL only when no next step possible."""
    reasons = []
    if not (lead.phone or "").strip():
        reasons.append("חסר מספר טלפון")
    if not (lead.name or "").strip():
        reasons.append("חסר שם")
    # No next step
    has_next = bool((lead.next_action or "").strip()) or (
        deal is not None and bool((deal.next_action or "").strip())
    )
    if reasons and not has_next:
        return True, " | ".join(reasons)
    return False, None


def _next_action(lead, deal, business_state: str) -> tuple[str, str]:
    """Return (action_text, next_action_at ISO-8601)."""
    now_il = datetime.now(timezone(timedelta(hours=3)))  # Israel (UTC+3)

    # Use stored next_action if available
    if deal is not None and (deal.next_action or "").strip():
        at = deal.next_action_at or (now_il + timedelta(hours=4)).isoformat()
        return deal.next_action, at

    if (lead.next_action or "").strip():
        at = lead.next_action_due or (now_il + timedelta(hours=4)).isoformat()
        return lead.next_action, at

    # Generate based on state
    actions = {
        "AWAITING_DEPOSIT":      ("לעקוב אחר תשלום מקדמה — לשלוח תזכורת ל{name}",  2),
        "AWAITING_APPROVAL":     ("לברר אישור הצעת מחיר עם {name}",                  4),
        "AWAITING_MEASUREMENTS": ("לתאם מדידות עם {name}",                           24),
        "QUOTE_SENT":            ("לבצע פולואפ על הצעת המחיר ל{name}",               6),
        "NEW_LEAD":              ("ליצור קשר ראשוני עם {name}",                       1),
        "BLOCKED_CRITICAL":      ("להשלים פרטי קשר עבור {name}",                     0),
    }
    template, hours_offset = actions.get(business_state, ("לטפל ב{name}", 4))
    action = template.format(name=lead.name or "לקוח")
    at = (now_il + timedelta(hours=hours_offset)).isoformat()
    return action, at


# ── Public API ────────────────────────────────────────────────────────────────

def score_lead(lead, deal=None) -> Phase11Result:
    """
    Compute Phase 11 priority score for a single lead (+ optional deal).
    Returns Phase11Result.
    """
    # Value: prefer deal value, fall back to lead potential_value
    value_ils = 0
    if deal is not None:
        value_ils = int(deal.value_ils or 0)
    if value_ils == 0:
        value_ils = int(lead.potential_value or 0)

    business_state = _map_business_state(lead, deal)
    blocked, blocked_reason = _is_blocked(lead, deal)
    if blocked:
        business_state = "BLOCKED_CRITICAL"

    hours = _hours_since(lead.last_activity_at)
    text_blob = " ".join(filter(None, [lead.notes, lead.response,
                                       lead.domain,
                                       getattr(deal, "title", None),
                                       getattr(deal, "commercial_stage", None)]))

    v_score = _value_score(value_ils)
    g_score = _geo_score(lead.city)
    w_score = _work_score(text_blob)
    u_score = _urgency_score(hours)
    s_base  = BUSINESS_STATES[business_state]

    total = v_score + g_score + w_score + u_score + s_base

    reason_parts = [
        f"state={business_state}({s_base:+d})",
        f"value={value_ils}({v_score:+d})",
        f"geo={lead.city or '?'}({g_score:+d})",
        f"work({w_score:+d})",
        f"urgency={hours:.0f}h({u_score:+d})",
    ]
    reason = " | ".join(reason_parts)

    action, action_at = _next_action(lead, deal, business_state)

    return Phase11Result(
        lead_id=lead.id,
        lead_name=lead.name,
        priority_score=total,
        priority_reason=reason,
        business_state=business_state,
        blocked_state=blocked,
        blocked_reason=blocked_reason,
        next_best_action=action,
        next_action_at=action_at,
    )


def build_revenue_queue(leads: list, deals_by_lead: dict) -> list[Phase11Result]:
    """
    Score all active leads and return sorted list (highest priority first).
    leads: list of LeadModel
    deals_by_lead: dict {lead_id: DealModel | None}
    """
    active_statuses = {"חדש", "ניסיון קשר", "מתעניין"}
    results = []
    for lead in leads:
        if lead.status in ("סגור_זכה", "סגור_הפסיד"):
            continue
        deal = deals_by_lead.get(lead.id)
        try:
            r = score_lead(lead, deal)
            results.append(r)
        except Exception as exc:
            log.warning("[Phase11] scoring error for lead %s: %s", lead.id, exc)

    results.sort(key=lambda r: r.priority_score, reverse=True)
    return results
