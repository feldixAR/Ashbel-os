"""
Phase 11 — local runtime verification (no DB required).
Run: python -m pytest tests/test_phase11_engine.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone, timedelta
from engines.phase11_engine import (
    score_lead, build_revenue_queue,
    _value_score, _geo_score, _work_score, _urgency_score,
    Phase11Result, BUSINESS_STATES,
)


class FakeLead:
    def __init__(self, **kw):
        self.id              = kw.get("id", "lead-1")
        self.name            = kw.get("name", "Test Lead")
        self.status          = kw.get("status", "חדש")
        self.city            = kw.get("city", "")
        self.phone           = kw.get("phone", "050-0000000")
        self.notes           = kw.get("notes", "")
        self.response        = kw.get("response", "")
        self.domain          = kw.get("domain", "")
        self.potential_value = kw.get("potential_value", 0)
        self.last_activity_at = kw.get("last_activity_at", None)
        self.next_action     = kw.get("next_action", "")
        self.next_action_due = kw.get("next_action_due", "")
        self.attempts        = kw.get("attempts", 0)


class FakeDeal:
    def __init__(self, **kw):
        self.lead_id         = kw.get("lead_id", "lead-1")
        self.stage           = kw.get("stage", "new")
        self.value_ils       = kw.get("value_ils", 0)
        self.commercial_stage = kw.get("commercial_stage", "")
        self.title           = kw.get("title", "")
        self.next_action     = kw.get("next_action", "")
        self.next_action_at  = kw.get("next_action_at", "")


# ── sub-formula tests ─────────────────────────────────────────────────────────

def test_value_score():
    assert _value_score(0)       == 5
    assert _value_score(19999)   == 5
    assert _value_score(20000)   == 12
    assert _value_score(49999)   == 12
    assert _value_score(50000)   == 25
    assert _value_score(99999)   == 25
    assert _value_score(100000)  == 35
    assert _value_score(200000)  == 35


def test_geo_score():
    assert _geo_score("אריאל") == 20       # Samaria
    assert _geo_score("ariel") == 20       # case-insensitive
    assert _geo_score("תל אביב") == 8     # non-Samaria but known city
    assert _geo_score("") == 0            # unknown


def test_work_score():
    assert _work_score("וילה פרטית") == 20
    assert _work_score("מרפסת מורכבת") == 15
    assert _work_score("תיקון חלון") == 0
    assert _work_score("חלון רגיל") == 8


def test_urgency_score():
    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=50)).isoformat()
    mid = (now - timedelta(hours=30)).isoformat()
    new = (now - timedelta(hours=10)).isoformat()
    assert _urgency_score(50) == 20
    assert _urgency_score(30) == 10
    assert _urgency_score(10) == 0


# ── state mapping tests ───────────────────────────────────────────────────────

def test_new_lead_state():
    lead = FakeLead(status="חדש", potential_value=25000, city="אריאל")
    r = score_lead(lead)
    assert r.business_state == "NEW_LEAD"
    assert r.priority_score == (12 + 20 + 8 + 20 + 8)   # value+geo+work+urgency+state
    assert not r.blocked_state


def test_awaiting_deposit():
    lead = FakeLead(status="מתעניין", potential_value=60000, city="קדומים")
    deal = FakeDeal(lead_id=lead.id, stage="negotiation", value_ils=60000)
    r = score_lead(lead, deal)
    assert r.business_state == "AWAITING_DEPOSIT"
    assert r.priority_score == (25 + 20 + 8 + 20 + 25)


def test_awaiting_approval():
    lead = FakeLead(status="מתעניין", potential_value=30000)
    deal = FakeDeal(lead_id=lead.id, stage="proposal", value_ils=30000)
    r = score_lead(lead, deal)
    assert r.business_state == "AWAITING_APPROVAL"


def test_awaiting_measurements():
    lead = FakeLead(status="מתעניין", potential_value=25000)
    deal = FakeDeal(lead_id=lead.id, stage="qualified", value_ils=25000)
    r = score_lead(lead, deal)
    assert r.business_state == "AWAITING_MEASUREMENTS"


def test_quote_sent_no_deal():
    lead = FakeLead(status="מתעניין", notes="שלחנו הצעת מחיר", potential_value=30000)
    r = score_lead(lead)
    assert r.business_state == "QUOTE_SENT"


def test_blocked_critical():
    lead = FakeLead(status="חדש", phone="", next_action="")
    r = score_lead(lead)
    assert r.business_state == "BLOCKED_CRITICAL"
    assert r.blocked_state
    # BLOCKED_CRITICAL contributes -10 to total; total may still be positive
    # due to other components, but it must rank below an equivalent non-blocked lead
    r_normal = score_lead(FakeLead(status="חדש", potential_value=0, city=""))
    assert r.priority_score < r_normal.priority_score


# ── queue build ───────────────────────────────────────────────────────────────

def test_build_revenue_queue_sorted():
    high = FakeLead(id="h", status="מתעניין", potential_value=120000, city="אריאל",
                    notes="וילה", last_activity_at=None)
    low  = FakeLead(id="l", status="חדש",    potential_value=5000,   city="")
    closed = FakeLead(id="c", status="סגור_זכה", potential_value=50000)

    queue = build_revenue_queue([high, low, closed], {})
    ids = [r.lead_id for r in queue]
    assert "c" not in ids           # closed filtered out
    assert ids[0] == "h"            # highest score first
    assert ids[1] == "l"


def test_next_best_action_from_deal():
    lead = FakeLead(status="מתעניין")
    deal = FakeDeal(stage="proposal", next_action="לשלוח חוזה", next_action_at="2026-04-01T09:00:00")
    r = score_lead(lead, deal)
    assert r.next_best_action == "לשלוח חוזה"
    assert r.next_action_at == "2026-04-01T09:00:00"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
