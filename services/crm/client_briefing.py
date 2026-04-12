"""
services/crm/client_briefing.py — Live Client Briefing Engine.

Provides instant context before and during customer interactions:

  identify_caller(phone) → CallerIdentity
    Phone number → Lead + Deal lookup. Returns unknown if no match.

  get_customer_summary(lead_id) → CustomerSummary
    Name, status, open deals, last interaction, key notes.

  retrieve_context(lead_id, limit=5) → List[TimelineEvent]
    Last N touchpoints from the unified timeline.

  start_call_session(lead_id, call_id) → CallSession
    Opens a transcription session stub (real STT requires external API).

  end_call_session(call_id, notes, outcome, duration_sec) → Activity
    Closes session, persists ActivityModel, updates Lead last_contact.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import pytz
    _IL_TZ = pytz.timezone("Asia/Jerusalem")
except ImportError:
    import datetime as _dt_
    _IL_TZ = _dt_.timezone(_dt_.timedelta(hours=3))
log = logging.getLogger(__name__)


# In-memory call sessions (process-local, acceptable for pilot)
_active_sessions: dict[str, dict] = {}


# ── Contracts ──────────────────────────────────────────────────────────────────

@dataclass
class CallerIdentity:
    identified:  bool
    lead_id:     str = ""
    name:        str = ""
    phone:       str = ""
    status:      str = ""
    open_deals:  int = 0
    last_contact: str = ""

    def to_dict(self) -> dict:
        return {
            "identified":  self.identified,
            "lead_id":     self.lead_id,
            "name":        self.name,
            "phone":       self.phone,
            "status":      self.status,
            "open_deals":  self.open_deals,
            "last_contact": self.last_contact,
        }


@dataclass
class CustomerSummary:
    lead_id:         str
    name:            str
    phone:           str
    status:          str
    sector:          str
    open_deals:      list = field(default_factory=list)
    last_interaction: str = ""
    key_notes:       str = ""
    recent_messages: int = 0

    def to_dict(self) -> dict:
        return {
            "lead_id":         self.lead_id,
            "name":            self.name,
            "phone":           self.phone,
            "status":          self.status,
            "sector":          self.sector,
            "open_deals":      self.open_deals,
            "last_interaction": self.last_interaction,
            "key_notes":       self.key_notes,
            "recent_messages": self.recent_messages,
        }


@dataclass
class CallSession:
    call_id:    str
    lead_id:    str
    started_at: str
    status:     str = "active"    # active | ended
    transcript: str = ""          # populated by STT integration

    def to_dict(self) -> dict:
        return {
            "call_id":    self.call_id,
            "lead_id":    self.lead_id,
            "started_at": self.started_at,
            "status":     self.status,
            "transcript": self.transcript,
        }


# ── Public API ─────────────────────────────────────────────────────────────────

def identify_caller(phone: str) -> CallerIdentity:
    """Lookup lead by phone. Returns identified=False if not found."""
    phone_clean = phone.strip().lstrip("+")
    try:
        from services.storage.repositories.lead_repo import LeadRepository
        from services.storage.db import get_session
        from services.storage.models.deal import DealModel

        repo  = LeadRepository()
        leads = repo.list_all()
        lead  = next(
            (l for l in leads
             if l.phone and l.phone.strip().lstrip("+").endswith(phone_clean[-9:])),
            None,
        )
        if not lead:
            log.info(f"[Briefing] identify_caller: unknown phone={phone}")
            return CallerIdentity(identified=False, phone=phone)

        with get_session() as s:
            open_deals = (s.query(DealModel)
                          .filter_by(lead_id=lead.id)
                          .filter(DealModel.stage.notin_(["won", "lost"]))
                          .count())

        log.info(f"[Briefing] identified: {lead.name} id={lead.id} deals={open_deals}")
        return CallerIdentity(
            identified=True,
            lead_id=lead.id,
            name=lead.name,
            phone=lead.phone or phone,
            status=lead.status or "",
            open_deals=open_deals,
            last_contact=lead.last_contact or "",
        )
    except Exception as e:
        log.error(f"[Briefing] identify_caller failed: {e}", exc_info=True)
        return CallerIdentity(identified=False, phone=phone)


def get_customer_summary(lead_id: str) -> CustomerSummary:
    """Return a rich customer summary card for the given lead."""
    try:
        from services.storage.repositories.lead_repo import LeadRepository
        from services.storage.db import get_session
        from services.storage.models.deal import DealModel
        from services.storage.models.message import MessageModel

        repo = LeadRepository()
        lead = next((l for l in repo.list_all() if l.id == lead_id), None)
        if not lead:
            return CustomerSummary(
                lead_id=lead_id, name="לא נמצא", phone="", status="", sector=""
            )

        with get_session() as s:
            open_deals = (s.query(DealModel)
                          .filter_by(lead_id=lead_id)
                          .filter(DealModel.stage.notin_(["won", "lost"]))
                          .all())
            recent_msg_count = (s.query(MessageModel)
                                .filter_by(lead_id=lead_id)
                                .count())

        # Build context from timeline
        from services.crm.timeline import build_timeline
        events = build_timeline(lead_id, limit=3)
        last_ts = events[0].occurred_at if events else lead.last_contact or ""

        key_notes = lead.notes or ""
        if lead.response:
            key_notes = f"{lead.response} | {key_notes}".strip(" |")

        return CustomerSummary(
            lead_id=lead_id,
            name=lead.name,
            phone=lead.phone or "",
            status=lead.status or "",
            sector=lead.sector or "",
            open_deals=[
                {"id": d.id, "title": d.title, "stage": d.stage,
                 "value_ils": d.value_ils}
                for d in open_deals
            ],
            last_interaction=last_ts,
            key_notes=key_notes[:300],
            recent_messages=recent_msg_count,
        )
    except Exception as e:
        log.error(f"[Briefing] get_customer_summary failed: {e}", exc_info=True)
        return CustomerSummary(lead_id=lead_id, name="שגיאה", phone="", status="", sector="")


def retrieve_context(lead_id: str, limit: int = 5):
    """Return last N timeline events for quick context."""
    from services.crm.timeline import build_timeline
    return build_timeline(lead_id, limit=limit)


def start_call_session(lead_id: str, call_id: str = "") -> CallSession:
    """
    Open a call session. Transcript is a stub — real STT requires
    integration with e.g. Google Speech-to-Text or Amazon Transcribe.
    """
    if not call_id:
        call_id = str(uuid.uuid4())
    now_il = datetime.datetime.now(_IL_TZ).isoformat()

    session = CallSession(
        call_id=call_id,
        lead_id=lead_id,
        started_at=now_il,
        status="active",
    )
    _active_sessions[call_id] = {
        "lead_id":    lead_id,
        "started_at": now_il,
        "status":     "active",
    }
    log.info(f"[Briefing] call session started: call_id={call_id} lead={lead_id}")
    return session


def end_call_session(
    call_id:          str,
    notes:            str,
    outcome:          str,
    duration_sec:     int = 0,
    performed_by:     str = "operator",
    lead_id_fallback: str = "",
) -> Optional[dict]:
    """
    Close a call session, persist an ActivityModel, update Lead last_contact.
    Returns the persisted Activity.to_dict() or None on failure.

    lead_id_fallback: used when call_id is not found in _active_sessions
    (Gunicorn multi-worker: start and end may hit different workers).
    If provided, the session is treated as valid even if not in memory.
    """
    session_data = _active_sessions.pop(call_id, {})
    lead_id      = session_data.get("lead_id", "") or lead_id_fallback.strip()

    if not lead_id:
        log.warning(
            f"[Briefing] end_call_session: unknown call_id={call_id} "
            f"and no lead_id_fallback provided"
        )
        return None

    if not session_data and lead_id_fallback:
        log.info(
            f"[Briefing] end_call_session: session not in memory — "
            f"using lead_id_fallback={lead_id} (multi-worker fallback)"
        )

    now_il = datetime.datetime.now(_IL_TZ).isoformat()

    try:
        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel
        from services.storage.models.base import new_uuid

        activity_id = new_uuid()
        with get_session() as s:
            s.add(ActivityModel(
                id=activity_id,
                lead_id=lead_id,
                activity_type="call",
                direction="inbound",
                subject=f"שיחה נכנסת — {call_id[:8]}",
                notes=notes,
                outcome=outcome,
                duration_sec=duration_sec,
                performed_by=performed_by,
                performed_at_il=now_il,
            ))

        # Update Lead.last_contact
        _update_lead_last_contact(lead_id, now_il[:10])

        log.info(
            f"[Briefing] call ended call_id={call_id} lead={lead_id} "
            f"outcome={outcome} dur={duration_sec}s"
        )
        return {
            "activity_id": activity_id,
            "lead_id":     lead_id,
            "call_id":     call_id,
            "outcome":     outcome,
            "duration_sec": duration_sec,
            "performed_at_il": now_il,
        }
    except Exception as e:
        log.error(f"[Briefing] end_call_session persist failed: {e}", exc_info=True)
        return None


def _update_lead_last_contact(lead_id: str, date_str: str) -> None:
    try:
        from services.storage.db import get_session
        from services.storage.models.lead import LeadModel
        with get_session() as s:
            lead = s.query(LeadModel).filter_by(id=lead_id).first()
            if lead:
                lead.last_contact = date_str
    except Exception as e:
        log.warning(f"[Briefing] _update_lead_last_contact: {e}")
