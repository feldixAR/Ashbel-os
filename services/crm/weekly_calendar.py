"""
services/crm/weekly_calendar.py — Weekly Revenue Calendar.

build_weekly_calendar() → WeeklyCalendar
  Returns 7-day view (Mon → Sun, Asia/Jerusalem) with:
  - Calendar events per day
  - Deals with expected_close_date in the window
  - Cumulative pipeline value at risk this week
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Dict, List

import pytz

log = logging.getLogger(__name__)
_IL_TZ = pytz.timezone("Asia/Jerusalem")


@dataclass
class DaySlot:
    date_str:  str
    weekday:   str          # שני / שלישי / ...
    events:    list = field(default_factory=list)
    deals_due: list = field(default_factory=list)
    revenue_at_risk: int = 0

    def to_dict(self) -> dict:
        return {
            "date_str":        self.date_str,
            "weekday":         self.weekday,
            "events":          self.events,
            "deals_due":       self.deals_due,
            "revenue_at_risk": self.revenue_at_risk,
        }


@dataclass
class WeeklyCalendar:
    week_start:      str            # ISO date Monday
    week_end:        str            # ISO date Sunday
    total_events:    int
    total_pipeline:  int
    days:            List[DaySlot] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "week_start":     self.week_start,
            "week_end":       self.week_end,
            "total_events":   self.total_events,
            "total_pipeline": self.total_pipeline,
            "days":           [d.to_dict() for d in self.days],
        }


_HEB_DAYS = {0:"שני", 1:"שלישי", 2:"רביעי", 3:"חמישי", 4:"שישי", 5:"שבת", 6:"ראשון"}


def build_weekly_calendar() -> WeeklyCalendar:
    today  = datetime.datetime.now(_IL_TZ).date()
    monday = today - datetime.timedelta(days=today.weekday())
    days   = [monday + datetime.timedelta(days=i) for i in range(7)]

    week_start = days[0].isoformat()
    week_end   = days[-1].isoformat()

    events = _load_events_in_range(week_start, week_end + "T23:59:59")
    deals  = _load_deals_closing_this_week(week_start, week_end)

    # Build per-day slots
    events_by_day: Dict[str, list] = {d.isoformat(): [] for d in days}
    for ev in events:
        ds = (ev.starts_at_il or "")[:10]
        if ds in events_by_day:
            events_by_day[ds].append(ev.to_dict())

    deals_by_day: Dict[str, list] = {d.isoformat(): [] for d in days}
    revenue_by_day: Dict[str, int] = {d.isoformat(): 0 for d in days}
    for deal in deals:
        ds = (deal.expected_close_date or "")[:10]
        if ds in deals_by_day:
            deals_by_day[ds].append({
                "id": deal.id, "title": deal.title,
                "stage": deal.stage, "value_ils": deal.value_ils,
                "weighted_value": deal.weighted_value(),
            })
            revenue_by_day[ds] += deal.weighted_value()

    day_slots = []
    for d in days:
        ds = d.isoformat()
        day_slots.append(DaySlot(
            date_str=ds,
            weekday=_HEB_DAYS.get(d.weekday(), ""),
            events=events_by_day.get(ds, []),
            deals_due=deals_by_day.get(ds, []),
            revenue_at_risk=revenue_by_day.get(ds, 0),
        ))

    total_pipeline = sum(d.weighted_value() for d in deals)
    log.info(
        f"[WeeklyCalendar] {week_start}→{week_end} "
        f"events={len(events)} deals_due={len(deals)} pipeline=₪{total_pipeline:,}"
    )

    return WeeklyCalendar(
        week_start=week_start,
        week_end=week_end,
        total_events=len(events),
        total_pipeline=total_pipeline,
        days=day_slots,
    )


def _load_events_in_range(start: str, end: str) -> list:
    try:
        from services.storage.db import get_session
        from services.storage.models.calendar_event import CalendarEventModel
        with get_session() as s:
            return (s.query(CalendarEventModel)
                    .filter(
                        CalendarEventModel.starts_at_il >= start,
                        CalendarEventModel.starts_at_il <= end,
                        CalendarEventModel.status != "cancelled",
                    )
                    .order_by(CalendarEventModel.starts_at_il)
                    .all())
    except Exception as e:
        log.warning(f"[WeeklyCalendar] _load_events: {e}")
        return []


def _load_deals_closing_this_week(start: str, end: str) -> list:
    try:
        from services.storage.db import get_session
        from services.storage.models.deal import DealModel
        with get_session() as s:
            return (s.query(DealModel)
                    .filter(
                        DealModel.expected_close_date >= start,
                        DealModel.expected_close_date <= end,
                        DealModel.stage.notin_(["won", "lost"]),
                    )
                    .order_by(DealModel.value_ils.desc())
                    .all())
    except Exception as e:
        log.warning(f"[WeeklyCalendar] _load_deals: {e}")
        return []
