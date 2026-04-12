"""
services/growth/learning_engine.py — Batch 10: Learning & Revenue Feedback Loop.

compute_lifecycle_metrics():
  Reads outreach_records grouped by channel / audience / opp_type.
  Aggregates KPIs over the last WINDOW_DAYS days.
  Upserts results into PerformanceMetric table.
  Returns LearningReport (summary of all computed dimensions).

Design:
  - Portable: no DB-specific SQL (pure SQLAlchemy ORM)
  - Timezone: all windowing uses Asia/Jerusalem
  - Safe: errors per dimension are logged and skipped, not raised
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    import pytz as _pytz
except ImportError:
    _pytz = None

log = logging.getLogger(__name__)
_IL_TZ        = (_pytz.timezone("Asia/Jerusalem") if _pytz else __import__("datetime").timezone(__import__("datetime").timedelta(hours=3)))
WINDOW_DAYS   = 30
AVG_DEAL_ILS  = 15_000   # Ashbal Aluminum average deal size
BASE_CONV_RATE = 0.20    # baseline conversion assumed before learning data exists


# ── Output contract ────────────────────────────────────────────────────────────

@dataclass
class DimensionMetric:
    dim_type:         str
    dim_value:        str
    total_sent:       int
    total_replied:    int
    total_won:        int
    total_lost:       int
    total_revenue_ils: int
    conversion_rate:  float
    reply_rate:       float
    sample_size:      int

    def to_dict(self) -> dict:
        return {
            "dim_type":          self.dim_type,
            "dim_value":         self.dim_value,
            "total_sent":        self.total_sent,
            "total_replied":     self.total_replied,
            "total_won":         self.total_won,
            "total_lost":        self.total_lost,
            "total_revenue_ils": self.total_revenue_ils,
            "conversion_rate":   round(self.conversion_rate, 4),
            "reply_rate":        round(self.reply_rate, 4),
            "sample_size":       self.sample_size,
        }


@dataclass
class LearningReport:
    computed_at:   str
    window_days:   int
    dimensions:    List[DimensionMetric] = field(default_factory=list)
    top_channel:   Optional[DimensionMetric] = None
    top_audience:  Optional[DimensionMetric] = None
    total_revenue: int = 0
    errors:        List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "computed_at":   self.computed_at,
            "window_days":   self.window_days,
            "total_revenue": self.total_revenue,
            "top_channel":   self.top_channel.to_dict() if self.top_channel else None,
            "top_audience":  self.top_audience.to_dict() if self.top_audience else None,
            "dimensions":    [d.to_dict() for d in self.dimensions],
            "errors":        self.errors,
        }


# ── Main entry point ───────────────────────────────────────────────────────────

def compute_lifecycle_metrics(window_days: int = WINDOW_DAYS) -> LearningReport:
    """
    Aggregate outreach_records KPIs and upsert into PerformanceMetric.
    Returns a LearningReport with top-performing channel and audience.
    """
    now_il      = datetime.datetime.now(_IL_TZ)
    cutoff_il   = (now_il - datetime.timedelta(days=window_days)).isoformat()
    computed_at = now_il.isoformat()

    log.info(
        f"[LearningEngine] Computing metrics window={window_days}d "
        f"cutoff={cutoff_il[:10]}"
    )

    # ── 1. Load records in window ─────────────────────────────────────────────
    records = _load_records(cutoff_il)
    log.info(f"[LearningEngine] Loaded {len(records)} outreach records")

    # ── 2. Aggregate by dimension ─────────────────────────────────────────────
    channel_agg:  Dict[str, dict] = {}
    audience_agg: Dict[str, dict] = {}
    opp_agg:      Dict[str, dict] = {}

    for r in records:
        ch  = r.get("channel")  or "unknown"
        aud = r.get("audience") or "general"
        opp = r.get("opp_type") or "unknown"
        lc  = r.get("lifecycle_status") or "sent"

        _tally(channel_agg,  ch,  lc)
        _tally(audience_agg, aud, lc)
        _tally(opp_agg,      opp, lc)

    # ── 3. Build DimensionMetric list ─────────────────────────────────────────
    errors: List[str] = []
    all_dims: List[DimensionMetric] = []

    for dim_type, agg in [
        ("channel",  channel_agg),
        ("audience", audience_agg),
        ("opp_type", opp_agg),
    ]:
        for dim_value, counts in agg.items():
            try:
                dm = _build_metric(dim_type, dim_value, counts)
                all_dims.append(dm)
                _upsert_metric(dm, window_days, computed_at)
            except Exception as e:
                msg = f"dim={dim_type}/{dim_value}: {e}"
                log.error(f"[LearningEngine] {msg}", exc_info=True)
                errors.append(msg)

    # ── 4. Compute report summary ─────────────────────────────────────────────
    channels  = [d for d in all_dims if d.dim_type == "channel"  and d.sample_size >= 3]
    audiences = [d for d in all_dims if d.dim_type == "audience" and d.sample_size >= 3]

    top_channel  = max(channels,  key=lambda d: d.conversion_rate, default=None)
    top_audience = max(audiences, key=lambda d: d.conversion_rate, default=None)
    total_rev    = sum(d.total_revenue_ils for d in all_dims if d.dim_type == "channel")

    log.info(
        f"[LearningEngine] Done — dims={len(all_dims)} "
        f"top_channel={top_channel.dim_value if top_channel else 'n/a'} "
        f"top_audience={top_audience.dim_value if top_audience else 'n/a'} "
        f"total_revenue=₪{total_rev:,}"
    )

    return LearningReport(
        computed_at=computed_at,
        window_days=window_days,
        dimensions=all_dims,
        top_channel=top_channel,
        top_audience=top_audience,
        total_revenue=total_rev,
        errors=errors,
    )


# ── Time-windowed report (for daily endpoint) ──────────────────────────────────

def revenue_window(hours: int) -> dict:
    """
    Query outreach_records closed_won within the last `hours` hours.
    Returns count + estimated revenue ILS.
    """
    now_il   = datetime.datetime.now(_IL_TZ)
    cutoff   = (now_il - datetime.timedelta(hours=hours)).isoformat()
    records  = _load_records(cutoff, lifecycle_filter=["closed_won"])
    won      = len(records)
    revenue  = won * AVG_DEAL_ILS
    return {"hours": hours, "closed_won": won, "revenue_ils": revenue}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_records(
    cutoff_iso: str,
    lifecycle_filter: Optional[List[str]] = None,
) -> List[dict]:
    """Load outreach records created after cutoff_iso, optionally filtered by lifecycle_status."""
    try:
        from services.storage.db import get_session
        from services.storage.models.outreach import OutreachModel

        target_statuses = lifecycle_filter or [
            "sent", "awaiting_response", "followup_due",
            "followup_sent", "closed_won", "closed_lost",
        ]

        with get_session() as session:
            rows = (
                session.query(OutreachModel)
                .filter(
                    OutreachModel.lifecycle_status.in_(target_statuses),
                    OutreachModel.created_at >= cutoff_iso,
                )
                .all()
            )
            return [_row_snapshot(r) for r in rows]
    except Exception as e:
        log.error(f"[LearningEngine] _load_records failed: {e}", exc_info=True)
        return []


def _row_snapshot(r) -> dict:
    """Extract relevant fields from an OutreachModel before session closes."""
    # Derive audience from contact_name prefix: "[whatsapp] title" → derive opp_type
    contact = r.contact_name or ""
    opp_type = contact.split("] ", 1)[0].lstrip("[") if "] " in contact else "unknown"
    return {
        "id":               r.id,
        "channel":          r.channel or "unknown",
        "audience":         _extract_audience(contact),
        "opp_type":         opp_type,
        "lifecycle_status": r.lifecycle_status or "sent",
        "goal_id":          r.goal_id,
    }


def _extract_audience(contact_name: str) -> str:
    """Best-effort audience extraction from contact_name field."""
    lower = contact_name.lower()
    if "contractor" in lower or "קבלן" in lower:
        return "contractors"
    if "architect" in lower or "אדריכל" in lower:
        return "architects"
    if "designer" in lower or "מעצב" in lower:
        return "interior_designers"
    return "general"


def _tally(agg: dict, key: str, lifecycle_status: str) -> None:
    """Increment counters for a dimension slice."""
    if key not in agg:
        agg[key] = {"sent": 0, "replied": 0, "won": 0, "lost": 0}
    agg[key]["sent"] += 1
    if lifecycle_status in ("awaiting_response", "followup_sent"):
        agg[key]["replied"] += 1
    if lifecycle_status == "closed_won":
        agg[key]["replied"] += 1
        agg[key]["won"]     += 1
    if lifecycle_status == "closed_lost":
        agg[key]["lost"]    += 1


def _build_metric(dim_type: str, dim_value: str, counts: dict) -> DimensionMetric:
    sent    = max(counts["sent"], 1)   # avoid div/0
    replied = counts["replied"]
    won     = counts["won"]
    lost    = counts["lost"]
    revenue = won * AVG_DEAL_ILS

    return DimensionMetric(
        dim_type=dim_type,
        dim_value=dim_value,
        total_sent=sent,
        total_replied=replied,
        total_won=won,
        total_lost=lost,
        total_revenue_ils=revenue,
        conversion_rate=round(won / sent, 4),
        reply_rate=round(replied / sent, 4),
        sample_size=sent,
    )


def _upsert_metric(dm: DimensionMetric, window_days: int, computed_at: str) -> None:
    """Portable upsert: update if exists, insert if not."""
    from services.storage.db import get_session
    from services.storage.models.analytics import PerformanceMetric
    from services.storage.models.base import new_uuid

    with get_session() as session:
        existing = (
            session.query(PerformanceMetric)
            .filter_by(dim_type=dm.dim_type, dim_value=dm.dim_value)
            .first()
        )
        if existing:
            existing.total_sent       = dm.total_sent
            existing.total_replied    = dm.total_replied
            existing.total_won        = dm.total_won
            existing.total_lost       = dm.total_lost
            existing.total_revenue_ils = dm.total_revenue_ils
            existing.conversion_rate  = dm.conversion_rate
            existing.reply_rate       = dm.reply_rate
            existing.window_days      = window_days
            existing.computed_at      = computed_at
            existing.sample_size      = dm.sample_size
        else:
            session.add(PerformanceMetric(
                id=new_uuid(),
                dim_type=dm.dim_type,
                dim_value=dm.dim_value,
                window_days=window_days,
                total_sent=dm.total_sent,
                total_replied=dm.total_replied,
                total_won=dm.total_won,
                total_lost=dm.total_lost,
                total_revenue_ils=dm.total_revenue_ils,
                avg_deal_ils=AVG_DEAL_ILS,
                conversion_rate=dm.conversion_rate,
                reply_rate=dm.reply_rate,
                computed_at=computed_at,
                sample_size=dm.sample_size,
            ))
