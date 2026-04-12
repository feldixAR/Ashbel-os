"""
services/crm/daily_plan.py — Daily Revenue Plan.

build_daily_plan() → DailyPlan
  1. Load all active deals + hot leads
  2. Score and prioritise via priority_engine
  3. Attach today's calendar events
  4. Allocate time budget
  5. Return structured DailyPlan
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import List

log = logging.getLogger(__name__)

try:
    import pytz
    _IL_TZ = pytz.timezone("Asia/Jerusalem")
except ImportError:
    import datetime as _dt
    _IL_TZ = _dt.timezone(_dt.timedelta(hours=3))  # IST fallback


@dataclass
class DailyPlan:
    date_il:          str
    total_deals:      int
    total_leads:      int
    pipeline_value:   int        # sum of weighted deal values (ILS)
    priority_items:   list        # List[PriorityItem.to_dict()]
    time_blocks:      list        # List[TimeBlock.to_dict()]
    todays_events:    list        # List[CalendarEvent.to_dict()] for today
    top_action:       str         # single most important action

    def to_dict(self) -> dict:
        return {
            "date_il":        self.date_il,
            "total_deals":    self.total_deals,
            "total_leads":    self.total_leads,
            "pipeline_value": self.pipeline_value,
            "priority_items": self.priority_items,
            "time_blocks":    self.time_blocks,
            "todays_events":  self.todays_events,
            "top_action":     self.top_action,
        }


def build_daily_plan(budget_minutes: int = 240) -> DailyPlan:
    """Build today's revenue plan. All errors return a safe empty plan."""
    now_il    = datetime.datetime.now(_IL_TZ)
    date_str  = now_il.date().isoformat()

    deals  = _load_active_deals()
    leads  = _load_hot_leads()
    events = _load_todays_events(date_str)

    from services.crm.priority_engine import build_priority_list, allocate_time
    priority = build_priority_list(deals, leads)
    blocks   = allocate_time(priority, budget_minutes)

    pipeline_value = sum(
        int(d.value_ils * d.probability)
        for d in deals if d.stage not in ("won", "lost")
    )

    top_action = (
        priority[0].reason if priority
        else "אין פריטים לטיפול היום"
    )

    log.info(
        f"[DailyPlan] date={date_str} deals={len(deals)} leads={len(leads)} "
        f"pipeline=₪{pipeline_value:,} blocks={len(blocks)}"
    )

    return DailyPlan(
        date_il=date_str,
        total_deals=len(deals),
        total_leads=len(leads),
        pipeline_value=pipeline_value,
        priority_items=[p.to_dict() for p in priority[:10]],
        time_blocks=[b.to_dict() for b in blocks],
        todays_events=[e.to_dict() for e in events],
        top_action=top_action,
    )


# ── Loaders ────────────────────────────────────────────────────────────────────

def _load_active_deals() -> list:
    try:
        from services.storage.db import get_session
        from services.storage.models.deal import DealModel
        with get_session() as s:
            return (s.query(DealModel)
                    .filter(DealModel.stage.notin_(["won", "lost"]))
                    .order_by(DealModel.value_ils.desc())
                    .limit(50).all())
    except Exception as e:
        log.warning(f"[DailyPlan] _load_active_deals: {e}")
        return []


def _load_hot_leads() -> list:
    try:
        from services.storage.repositories.lead_repo import LeadRepository
        return LeadRepository().get_hot_leads()
    except Exception as e:
        log.warning(f"[DailyPlan] _load_hot_leads: {e}")
        return []


def _load_todays_events(date_str: str) -> list:
    try:
        from services.storage.db import get_session
        from services.storage.models.calendar_event import CalendarEventModel
        with get_session() as s:
            rows = (s.query(CalendarEventModel)
                    .filter(
                        CalendarEventModel.starts_at_il >= date_str,
                        CalendarEventModel.starts_at_il < date_str + "T23:59:59",
                        CalendarEventModel.status != "cancelled",
                    )
                    .order_by(CalendarEventModel.starts_at_il)
                    .all())
            return rows
    except Exception as e:
        log.warning(f"[DailyPlan] _load_todays_events: {e}")
        return []
