"""
revenue_engine.py — Revenue Intelligence Layer (Batch 4)

Pure functions that analyse CRM state and return actionable insights.
No side effects. No DB writes. No event emission.

Functions:
    revenue_snapshot()          -> RevenueSnapshot
    opportunity_score(lead)     -> float
    detect_opportunities(leads) -> List[Opportunity]
    detect_bottlenecks(leads)   -> List[Bottleneck]
    next_best_actions(leads, n) -> List[Action]
    build_revenue_report(snap)  -> str
"""

import logging
import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

log = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Opportunity:
    lead_id:     str
    lead_name:   str
    reason:      str
    urgency:     str        # high | medium | low
    action:      str
    score:       int

@dataclass
class Bottleneck:
    category:    str
    count:       int
    description: str
    suggestion:  str

@dataclass
class RevenueAction:
    priority:    int
    lead_name:   str
    action:      str
    reason:      str
    channel:     str        # whatsapp | call | email | visit
    urgency:     str        # today | this_week | this_month

@dataclass
class RevenueSnapshot:
    generated_at:   str
    total_leads:    int
    hot_leads:      int
    warm_leads:     int
    cold_leads:     int
    stuck_leads:    int
    avg_score:      float
    conversion_est: float   # estimated conversion rate %
    pipeline_value: int     # estimated pipeline in ₪
    opportunities:  List[Opportunity]  = field(default_factory=list)
    bottlenecks:    List[Bottleneck]   = field(default_factory=list)
    next_actions:   List[RevenueAction] = field(default_factory=list)
    status_dist:    Dict[str, int]     = field(default_factory=dict)
    source_dist:    Dict[str, int]     = field(default_factory=dict)


# ── Business config (אשבל אלומיניום) ─────────────────────────────────────────

AVG_DEAL_VALUE_ILS   = 15_000   # ממוצע עסקה באלומיניום
CONVERSION_RATE_BASE = 0.15     # 15% base conversion


# ── Main snapshot ─────────────────────────────────────────────────────────────

def revenue_snapshot() -> RevenueSnapshot:
    """Pull full revenue picture from DB."""
    from services.storage.repositories.lead_repo import LeadRepository
    leads = LeadRepository().list_all()
    return build_snapshot(leads)


def build_snapshot(leads: list) -> RevenueSnapshot:
    """Build RevenueSnapshot from lead list. Pure after DB read."""
    now    = datetime.datetime.now(datetime.timezone.utc).isoformat()
    total  = len(leads)

    if not leads:
        return RevenueSnapshot(
            generated_at=now, total_leads=0, hot_leads=0,
            warm_leads=0, cold_leads=0, stuck_leads=0,
            avg_score=0.0, conversion_est=0.0, pipeline_value=0,
        )

    scores = [l.score or 0 for l in leads]
    avg_sc = round(sum(scores) / total, 1)

    hot   = [l for l in leads if (l.score or 0) >= 70]
    warm  = [l for l in leads if 40 <= (l.score or 0) < 70]
    cold  = [l for l in leads if (l.score or 0) < 40]
    stuck = [l for l in leads if l.status == "ניסיון קשר" and (l.attempts or 0) >= 3]

    status_dist: Dict[str, int] = {}
    source_dist: Dict[str, int] = {}
    for l in leads:
        st = l.status or "unknown"
        sr = l.source or "unknown"
        status_dist[st] = status_dist.get(st, 0) + 1
        source_dist[sr] = source_dist.get(sr, 0) + 1

    # Pipeline estimate: hot * avg deal * base conversion
    pipeline = int(len(hot) * AVG_DEAL_VALUE_ILS * CONVERSION_RATE_BASE +
                   len(warm) * AVG_DEAL_VALUE_ILS * (CONVERSION_RATE_BASE / 3))

    conversion_est = round(
        (len(hot) / total) * CONVERSION_RATE_BASE * 100, 1
    ) if total else 0.0

    opportunities = detect_opportunities(leads)
    bottlenecks   = detect_bottlenecks(leads, status_dist)
    next_actions  = next_best_actions(leads)

    return RevenueSnapshot(
        generated_at=now,
        total_leads=total,
        hot_leads=len(hot),
        warm_leads=len(warm),
        cold_leads=len(cold),
        stuck_leads=len(stuck),
        avg_score=avg_sc,
        conversion_est=conversion_est,
        pipeline_value=pipeline,
        opportunities=opportunities,
        bottlenecks=bottlenecks,
        next_actions=next_actions,
        status_dist=status_dist,
        source_dist=source_dist,
    )


# ── Opportunity detection ─────────────────────────────────────────────────────

def opportunity_score(lead) -> float:
    """Score how much of an opportunity this lead represents (0-1)."""
    score = (lead.score or 0) / 100.0
    if lead.status == "מתעניין":
        score += 0.2
    if (lead.attempts or 0) == 0:
        score += 0.1
    if lead.source in ("referral", "המלצה"):
        score += 0.15
    return min(1.0, score)


def detect_opportunities(leads: list) -> List[Opportunity]:
    """Find the top opportunities in the lead list."""
    opps = []
    closed = {"סגור_זכה", "סגור_הפסיד"}

    for lead in leads:
        if lead.status in closed:
            continue

        score  = lead.score or 0
        opp_sc = opportunity_score(lead)

        if score >= 80:
            opps.append(Opportunity(
                lead_id=lead.id, lead_name=lead.name,
                reason=f"ציון גבוה מאוד ({score})",
                urgency="high",
                action="פנה ישירות לסגירת עסקה",
                score=score,
            ))
        elif lead.status == "מתעניין" and (lead.attempts or 0) == 0:
            opps.append(Opportunity(
                lead_id=lead.id, lead_name=lead.name,
                reason="מתעניין ולא נוצר קשר",
                urgency="high",
                action="יצור קשר מיידי — WhatsApp או שיחה",
                score=score,
            ))
        elif lead.source in ("referral", "המלצה") and score >= 40:
            opps.append(Opportunity(
                lead_id=lead.id, lead_name=lead.name,
                reason="ליד המלצה עם פוטנציאל",
                urgency="medium",
                action="פנה בגישה אישית — ציין ממי ההמלצה",
                score=score,
            ))
        elif score >= 60 and lead.status == "חדש":
            opps.append(Opportunity(
                lead_id=lead.id, lead_name=lead.name,
                reason=f"ליד חדש עם ציון טוב ({score})",
                urgency="medium",
                action="שלח הודעת היכרות ראשונית",
                score=score,
            ))

    # Sort by urgency and score
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    opps.sort(key=lambda o: (urgency_order.get(o.urgency, 2), -o.score))
    return opps[:8]


# ── Bottleneck detection ──────────────────────────────────────────────────────

def detect_bottlenecks(leads: list, status_dist: Dict[str, int] = None) -> List[Bottleneck]:
    """Identify where leads are getting stuck."""
    if status_dist is None:
        status_dist = {}
        for l in leads:
            st = l.status or "unknown"
            status_dist[st] = status_dist.get(st, 0) + 1

    bottlenecks = []
    total = len(leads)
    if not total:
        return []

    # Too many new leads untouched
    new_count = status_dist.get("חדש", 0)
    if new_count >= 5:
        bottlenecks.append(Bottleneck(
            category="לידים חדשים לא טופלו",
            count=new_count,
            description=f"{new_count} לידים חדשים לא קיבלו מענה",
            suggestion="הגדר תהליך מענה ראשוני תוך 24 שעות",
        ))

    # Stuck in contact attempt
    stuck_count = status_dist.get("ניסיון קשר", 0)
    if stuck_count >= 3:
        bottlenecks.append(Bottleneck(
            category="ניסיונות קשר ללא מענה",
            count=stuck_count,
            description=f"{stuck_count} לידים תקועים בניסיון קשר",
            suggestion="שנה גישה — נסה WhatsApp במקום שיחה, או שלח הצעת מחיר",
        ))

    # Low average score
    if total >= 5:
        scores = [l.score or 0 for l in leads]
        avg = sum(scores) / len(scores)
        if avg < 35:
            bottlenecks.append(Bottleneck(
                category="איכות לידים נמוכה",
                count=total,
                description=f"ציון ממוצע נמוך ({avg:.0f}/100)",
                suggestion="שפר מקורות לידים — מקד ב-Instagram ו-המלצות",
            ))

    # No hot leads
    hot = [l for l in leads if (l.score or 0) >= 70]
    if total >= 10 and not hot:
        bottlenecks.append(Bottleneck(
            category="אין לידים חמים",
            count=0,
            description="אין לידים עם ציון 70+ בצנרת",
            suggestion="עדכן ציונים ידנית לאחר שיחות, והגדל פעילות שיווקית",
        ))

    return bottlenecks


# ── Next best actions ─────────────────────────────────────────────────────────

def next_best_actions(leads: list, n: int = 5) -> List[RevenueAction]:
    """Return the n most impactful actions to take right now."""
    actions = []
    closed  = {"סגור_זכה", "סגור_הפסיד"}
    priority = 1

    # Sort by score desc, then by attempts asc
    eligible = [l for l in leads if (l.status or "") not in closed]
    eligible.sort(key=lambda l: (-(l.score or 0), l.attempts or 0))

    for lead in eligible[:n]:
        score    = lead.score or 0
        attempts = lead.attempts or 0
        status   = lead.status or "חדש"

        if score >= 70 and attempts == 0:
            actions.append(RevenueAction(
                priority=priority,
                lead_name=lead.name,
                action=f"פנה ל{lead.name} — ליד חם ללא קשר",
                reason=f"ציון {score}, לא נוצר קשר",
                channel="whatsapp",
                urgency="today",
            ))
        elif status == "מתעניין":
            actions.append(RevenueAction(
                priority=priority,
                lead_name=lead.name,
                action=f"שלח הצעת מחיר ל{lead.name}",
                reason="מתעניין — יש לקדם לשלב הצעה",
                channel="whatsapp",
                urgency="today",
            ))
        elif attempts >= 3 and status == "ניסיון קשר":
            actions.append(RevenueAction(
                priority=priority,
                lead_name=lead.name,
                action=f"שנה גישה עם {lead.name} — נסה שעה אחרת",
                reason=f"{attempts} ניסיונות ללא מענה",
                channel="call",
                urgency="this_week",
            ))
        elif status == "חדש" and score >= 50:
            actions.append(RevenueAction(
                priority=priority,
                lead_name=lead.name,
                action=f"צור קשר ראשוני עם {lead.name}",
                reason=f"ליד חדש עם ציון {score}",
                channel="whatsapp",
                urgency="this_week",
            ))
        else:
            continue

        priority += 1

    return actions


# ── Text report ───────────────────────────────────────────────────────────────

def build_revenue_report(snap: RevenueSnapshot) -> str:
    """Format RevenueSnapshot into readable Hebrew report."""
    from config.settings import COMPANY_NAME

    lines = [
        f"דוח הכנסות — {COMPANY_NAME}",
        f"{'─' * 45}",
        f"תאריך: {snap.generated_at[:19].replace('T', ' ')}",
        f"{'─' * 45}",
        f"📊 סיכום צנרת",
        f"  סה\"כ לידים     : {snap.total_leads}",
        f"  🔥 חמים (70+)  : {snap.hot_leads}",
        f"  🟡 חמימים      : {snap.warm_leads}",
        f"  🔵 קרים        : {snap.cold_leads}",
        f"  🔴 תקועים      : {snap.stuck_leads}",
        f"  ציון ממוצע     : {snap.avg_score}",
        f"  המרה משוערת    : {snap.conversion_est}%",
        f"  שווי צנרת      : ₪{snap.pipeline_value:,}",
        f"{'─' * 45}",
    ]

    if snap.opportunities:
        lines.append("🎯 הזדמנויות")
        for opp in snap.opportunities[:5]:
            urgency_icon = "🔴" if opp.urgency == "high" else "🟡"
            lines.append(f"  {urgency_icon} {opp.lead_name}: {opp.reason}")
            lines.append(f"     → {opp.action}")
        lines.append(f"{'─' * 45}")

    if snap.bottlenecks:
        lines.append("🚧 חסמים")
        for b in snap.bottlenecks:
            lines.append(f"  • {b.category} ({b.count})")
            lines.append(f"    → {b.suggestion}")
        lines.append(f"{'─' * 45}")

    if snap.next_actions:
        lines.append("✅ פעולות מיידיות")
        for a in snap.next_actions:
            urgency_map = {"today": "היום", "this_week": "השבוע", "this_month": "החודש"}
            lines.append(f"  {a.priority}. {a.action} [{urgency_map.get(a.urgency, a.urgency)}]")
        lines.append(f"{'─' * 45}")

    if snap.source_dist:
        lines.append("📥 מקורות לידים")
        for src, cnt in sorted(snap.source_dist.items(), key=lambda x: -x[1]):
            lines.append(f"  {src:<20}: {cnt}")
        lines.append(f"{'─' * 45}")

    return "\n".join(lines)


# ── Wrappers (orchestrator.py imports these names) ────────────────────────────
def revenue_insights() -> dict:
    """Returns revenue snapshot as dict with 'summary' key for orchestrator."""
    snap = revenue_snapshot()
    return {
        "summary":       build_revenue_report(snap),
        "total_leads":   snap.total_leads,
        "hot_leads":     snap.hot_leads,
        "warm_leads":    snap.warm_leads,
        "pipeline_value": snap.pipeline_value,
        "conversion_est": snap.conversion_est,
        "avg_score":     snap.avg_score,
        "generated_at":  snap.generated_at,
    }


def identify_bottlenecks() -> list:
    """Returns bottleneck list for orchestrator (fetches leads internally)."""
    from services.storage.repositories.lead_repo import LeadRepository
    leads = LeadRepository().list_all()
    bottlenecks = detect_bottlenecks(leads)
    return [b.description for b in bottlenecks]
