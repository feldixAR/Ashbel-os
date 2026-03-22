"""
action_dispatcher.py — Integration Action Dispatcher (Batch 5)

Central point that executes approved actions:
    dispatch_whatsapp(draft)   → sends via WhatsApp service
    dispatch_calendar(draft)   → creates via Calendar service
    dispatch_reminder(draft)   → stores reminder in DB

Called AFTER user approves a draft in the UI.
"""

import logging
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)


class ActionDispatcher:

    def dispatch(self, action_type: str, payload: Dict[str, Any],
                 lead_id: str = "") -> Dict[str, Any]:
        """
        Route an approved draft to the correct integration.
        Returns result dict with success, mode, link, etc.
        """
        if action_type == "whatsapp_draft":
            return self._dispatch_whatsapp(payload, lead_id)
        if action_type == "calendar_draft":
            return self._dispatch_calendar(payload, lead_id)
        if action_type == "reminder":
            return self._dispatch_reminder(payload, lead_id)
        return {"success": False, "error": f"unknown action_type: {action_type}"}

    # ── WhatsApp ──────────────────────────────────────────────────────────────

    def _dispatch_whatsapp(self, payload: Dict, lead_id: str) -> Dict:
        from services.integrations.whatsapp import whatsapp_service, WhatsAppMessage
        from services.integrations.contacts import contacts_service

        to_name  = payload.get("contact_name", "")
        to_phone = payload.get("phone", "")
        body     = payload.get("draft_message", "")

        # Resolve phone if missing
        if not to_phone and to_name:
            contact = contacts_service.resolve(to_name)
            if contact and contact.phone:
                to_phone = contact.phone
                lead_id  = lead_id or (contact.lead_id or "")

        if not to_phone:
            # Fallback: return deep link without phone
            deep_link = f"https://wa.me/?text={__import__('urllib.parse', fromlist=['quote']).parse.quote(body)}"
            return {
                "success":   True,
                "mode":      "deeplink_no_phone",
                "deep_link": deep_link,
                "note":      f"לא נמצא טלפון עבור {to_name} — פתח WhatsApp ידנית",
            }

        msg    = WhatsAppMessage(to_phone=to_phone, to_name=to_name,
                                 body=body, lead_id=lead_id)
        result = whatsapp_service.send(msg)

        # Log to lead history if we have lead_id
        if lead_id:
            self._log_to_lead(lead_id, f"WhatsApp נשלח: {body[:60]}")

        return {
            "success":    result.success,
            "mode":       result.mode,
            "message_id": result.message_id,
            "deep_link":  result.deep_link,
            "to_name":    to_name,
            "to_phone":   to_phone,
            "error":      result.error,
        }

    # ── Calendar ──────────────────────────────────────────────────────────────

    def _dispatch_calendar(self, payload: Dict, lead_id: str) -> Dict:
        from services.integrations.calendar import calendar_service, CalendarEvent
        import datetime

        contact = payload.get("contact_name", "")
        date    = payload.get("meeting_date", "")
        time    = payload.get("meeting_time", "10:00")
        title   = payload.get("meeting_title") or f"פגישה עם {contact}"
        notes   = payload.get("notes", "")

        # Resolve date if missing
        if not date:
            date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

        # Get phone from contacts
        phone = ""
        if contact:
            from services.integrations.contacts import contacts_service
            c = contacts_service.resolve(contact)
            if c:
                phone   = c.phone or ""
                lead_id = lead_id or (c.lead_id or "")

        event  = CalendarEvent(
            title=title, date=date, time=time,
            attendee_name=contact, attendee_phone=phone,
            notes=notes, lead_id=lead_id,
        )
        result = calendar_service.create_event(event)

        if lead_id:
            self._log_to_lead(lead_id, f"פגישה נקבעה: {title} ב-{date}")

        return {
            "success":   result.success,
            "mode":      result.mode,
            "event_id":  result.event_id,
            "event_url": result.event_url,
            "deep_link": result.deep_link,
            "title":     title,
            "date":      date,
            "error":     result.error,
        }

    # ── Reminder ──────────────────────────────────────────────────────────────

    def _dispatch_reminder(self, payload: Dict, lead_id: str) -> Dict:
        reminder_text = payload.get("reminder_text", "תזכורת")
        date          = payload.get("date", "")
        notes         = payload.get("notes", "")

        # Store in memory store for now (DB scheduler in future)
        try:
            from memory.memory_store import memory_store
            memory_store.store(
                key=f"reminder:{lead_id or 'general'}",
                value={"text": reminder_text, "date": date, "notes": notes},
                ttl_hours=72,
            )
        except Exception as e:
            log.warning(f"[Dispatcher] reminder store failed: {e}")

        if lead_id:
            self._log_to_lead(lead_id, f"תזכורת נרשמה: {reminder_text} ב-{date}")

        return {
            "success":       True,
            "mode":          "stored",
            "reminder_text": reminder_text,
            "date":          date,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log_to_lead(self, lead_id: str, note: str) -> None:
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            LeadRepository().append_history(
                lead_id=lead_id, action="integration",
                note=note, agent_id="action_dispatcher",
            )
        except Exception as e:
            log.warning(f"[Dispatcher] lead log failed: {e}")


action_dispatcher = ActionDispatcher()
