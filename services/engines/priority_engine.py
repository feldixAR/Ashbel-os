"""
Priority scoring engine — Revenue CRM (Batch 7).

Computes a 0-100 score per lead based on:
  - Potential value       (max +30)
  - Deal close probability(max +25)
  - Recency of activity   (max -20 penalty)
  - Upcoming meeting      (+15)
  - Next action urgency   (+10)
  - Hot status            (+8)
  - Missing next_action   (-10 penalty)
"""
import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)


def compute_lead_score(
    lead: dict,
    deals: list = None,
    activities: list = None,
    events: list = None,
) -> float:
    """
    Return priority score 0.0–100.0 for the given lead dict.
    All arguments are plain dicts (safe to call outside a DB session).
    """
    score   = 0.0
    deals   = deals or []
    events  = events or []
    now     = datetime.now(timezone.utc)

    # 1. Potential value weight (max +30)
    value = int(lead.get("potential_value", 0) or 0)
    score += min(value / 1000, 30)

    # 2. Top deal close probability (max +25)
    if deals:
        top = max(deals, key=lambda d: int(d.get("value_ils", 0) or 0))
        prob = float(top.get("probability", 0.2) or 0.2)
        score += prob * 25

    # 3. Activity recency penalty (max -20)
    last_raw = lead.get("last_activity_at") or lead.get("last_contact")
    if last_raw:
        try:
            last_dt = _parse_dt(str(last_raw))
            days_silent = max((now - last_dt).days, 0)
            score -= min(days_silent * 2, 20)
        except Exception:
            score -= 8
    else:
        score -= 15  # no contact recorded

    # 4. Upcoming meeting within 7 days (+15)
    for ev in events:
        start_raw = ev.get("starts_at_il") or ev.get("start_at", "")
        if start_raw:
            try:
                start_dt = _parse_dt(str(start_raw))
                if now < start_dt <= now + timedelta(days=7):
                    score += 15
                    break
            except Exception:
                pass

    # 5. Next action due within 24 h (+10)
    nad = lead.get("next_action_due")
    if nad:
        try:
            due_dt = _parse_dt(str(nad))
            if due_dt <= now + timedelta(hours=24):
                score += 10
        except Exception:
            pass

    # 6. Hot status bonus (+8)
    if lead.get("status") == "חם":
        score += 8

    # 7. Missing next_action penalty (-10)
    if not lead.get("next_action"):
        score -= 10

    return round(max(0.0, min(score, 100.0)), 1)


def _parse_dt(raw: str) -> datetime:
    """Parse ISO-8601 string → UTC-aware datetime."""
    raw = raw.replace("Z", "+00:00")
    dt  = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
