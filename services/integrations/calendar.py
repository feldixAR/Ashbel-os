"""
calendar.py — Google Calendar Integration Layer (Batch 5)

Two modes:
    1. Google Calendar deep link — opens calendar with pre-filled event (no API)
    2. Google Calendar API — real event creation (requires GOOGLE_CALENDAR_TOKEN)
"""

import logging
import urllib.parse
import os
from dataclasses import dataclass, field
from typing import Optional
import datetime

log = logging.getLogger(__name__)

GOOGLE_CALENDAR_TOKEN = os.getenv("GOOGLE_CALENDAR_TOKEN", "")
GOOGLE_CALENDAR_ID    = os.getenv("GOOGLE_CALENDAR_ID", "primary")


@dataclass
class CalendarEvent:
    title:       str
    date:        str                    # ISO: 2026-03-25
    time:        str         = "10:00"  # HH:MM
    duration_min: int        = 60
    attendee_name: str       = ""
    attendee_phone: str      = ""
    notes:       str         = ""
    lead_id:     Optional[str] = None


@dataclass
class EventResult:
    success:    bool
    mode:       str             # "api" | "deeplink" | "draft"
    event_id:   Optional[str]  = None
    event_url:  Optional[str]  = None
    deep_link:  Optional[str]  = None
    error:      Optional[str]  = None


class CalendarService:

    def create_event(self, event: CalendarEvent) -> EventResult:
        if GOOGLE_CALENDAR_TOKEN:
            return self._create_via_api(event)
        return self._create_via_deeplink(event)

    def build_deep_link(self, event: CalendarEvent) -> str:
        """Google Calendar deep link — opens browser with pre-filled event."""
        try:
            date     = datetime.date.fromisoformat(event.date)
            h, m     = map(int, event.time.split(":"))
            start_dt = datetime.datetime(date.year, date.month, date.day, h, m)
            end_dt   = start_dt + datetime.timedelta(minutes=event.duration_min)
            fmt      = "%Y%m%dT%H%M%S"
            dates    = f"{start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}"
        except Exception:
            dates = ""

        details = event.notes or ""
        if event.attendee_phone:
            details += f"\nטלפון: {event.attendee_phone}"

        params = {
            "action":  "TEMPLATE",
            "text":    event.title,
            "details": details.strip(),
            "dates":   dates,
        }
        qs = urllib.parse.urlencode(params)
        return f"https://calendar.google.com/calendar/render?{qs}"

    def prepare_draft(self, event: CalendarEvent) -> dict:
        deep_link = self.build_deep_link(event)
        return {
            "action_type":     "calendar_draft",
            "meeting_title":   event.title,
            "contact_name":    event.attendee_name,
            "meeting_date":    event.date,
            "meeting_time":    event.time,
            "duration_min":    event.duration_min,
            "notes":           event.notes,
            "deep_link":       deep_link,
            "lead_id":         event.lead_id,
            "channel":         "calendar",
            "needs_approval":  True,
            "next_step":       "approve_and_open",
            "api_ready":       bool(GOOGLE_CALENDAR_TOKEN),
        }

    def _create_via_api(self, event: CalendarEvent) -> EventResult:
        """Create event via Google Calendar API."""
        import json, urllib.request, urllib.error
        try:
            date     = datetime.date.fromisoformat(event.date)
            h, m     = map(int, event.time.split(":"))
            start_dt = datetime.datetime(date.year, date.month, date.day, h, m)
            end_dt   = start_dt + datetime.timedelta(minutes=event.duration_min)
        except Exception as e:
            return EventResult(success=False, mode="api", error=str(e))

        body = {
            "summary":     event.title,
            "description": event.notes,
            "start":  {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Jerusalem"},
            "end":    {"dateTime": end_dt.isoformat(),   "timeZone": "Asia/Jerusalem"},
        }
        if event.attendee_phone:
            body["description"] += f"\nטלפון: {event.attendee_phone}"

        url = (f"https://www.googleapis.com/calendar/v3/calendars/"
               f"{GOOGLE_CALENDAR_ID}/events")
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": f"Bearer {GOOGLE_CALENDAR_TOKEN}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                data = json.loads(r.read())
                log.info(f"[Calendar] event created id={data.get('id')}")
                return EventResult(
                    success=True, mode="api",
                    event_id=data.get("id"),
                    event_url=data.get("htmlLink"),
                )
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            log.error(f"[Calendar] API error: {err}")
            return EventResult(success=False, mode="api", error=err)

    def _create_via_deeplink(self, event: CalendarEvent) -> EventResult:
        link = self.build_deep_link(event)
        return EventResult(success=True, mode="deeplink", deep_link=link)


calendar_service = CalendarService()
