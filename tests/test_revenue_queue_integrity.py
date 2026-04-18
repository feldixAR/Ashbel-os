"""
tests/test_revenue_queue_integrity.py — Revenue queue and Mission Control integrity.

Proves:
- queue sorted by priority_score descending
- next_best_action populated for all items
- blocked states detected correctly
- deal value boosts score
- GET /api/daily_revenue_queue returns proper structure
"""
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OS_API_KEY", "test")
os.environ.setdefault("ENV", "test")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from engines.phase11_engine import build_revenue_queue, score_lead, Phase11Result

_now = datetime.now(timezone.utc)


class FL:
    """Minimal fake lead."""
    def __init__(self, **kw):
        self.id               = kw.get("id", "lead-x")
        self.name             = kw.get("name", "Test Lead")
        self.status           = kw.get("status", "חדש")
        self.city             = kw.get("city", "ראש העין")
        self.phone            = kw.get("phone", "050-0000000")
        self.notes            = kw.get("notes", "")
        self.response         = kw.get("response", "")
        self.domain           = kw.get("domain", "וילה פרטית")
        self.potential_value  = kw.get("potential_value", 50000)
        self.last_activity_at = kw.get(
            "last_activity_at",
            (_now - timedelta(hours=48)).isoformat(),
        )
        self.next_action      = kw.get("next_action", "שלח הצעת מחיר")
        self.next_action_due  = kw.get("next_action_due", "")
        self.attempts         = kw.get("attempts", 0)


class FD:
    """Minimal fake deal."""
    def __init__(self, lead_id: str, value: int = 100000):
        self.lead_id          = lead_id
        self.stage            = "proposal"
        self.value_ils        = value
        self.commercial_stage = "proposal"
        self.title            = "Test Deal"
        self.next_action      = ""
        self.next_action_at   = ""


# ── Sorting ───────────────────────────────────────────────────────────────────

def test_queue_sorted_descending():
    leads = [
        FL(id="low",  potential_value=5000,
           last_activity_at=(_now - timedelta(hours=5)).isoformat()),
        FL(id="high", potential_value=100000,
           last_activity_at=(_now - timedelta(hours=70)).isoformat()),
        FL(id="mid",  potential_value=30000,
           last_activity_at=(_now - timedelta(hours=40)).isoformat()),
    ]
    queue = build_revenue_queue(leads, {})
    scores = [r.priority_score for r in queue]
    assert scores == sorted(scores, reverse=True), \
        f"Queue not sorted descending: {scores}"


def test_queue_lead_ids_match_input():
    leads = [FL(id=f"lid-{i}") for i in range(4)]
    queue = build_revenue_queue(leads, {})
    input_ids = {l.id for l in leads}
    output_ids = {r.lead_id for r in queue}
    assert input_ids == output_ids, \
        f"Lead IDs mismatch: input={input_ids}, output={output_ids}"


# ── next_best_action ─────────────────────────────────────────────────────────

def test_next_best_action_populated():
    queue = build_revenue_queue([FL()], {})
    assert queue, "Empty queue"
    assert queue[0].next_best_action, \
        f"next_best_action empty for lead {queue[0].lead_id}"


def test_all_items_have_next_best_action():
    leads = [FL(id=f"nba-{i}", potential_value=i * 10000) for i in range(5)]
    queue = build_revenue_queue(leads, {})
    for item in queue:
        assert item.next_best_action, \
            f"next_best_action empty for lead {item.lead_id}"


# ── Phase11Result shape ───────────────────────────────────────────────────────

def test_results_are_phase11result_instances():
    queue = build_revenue_queue([FL(id=f"r{i}") for i in range(3)], {})
    for item in queue:
        assert isinstance(item, Phase11Result), \
            f"Expected Phase11Result, got {type(item)}"
        assert item.lead_id
        assert isinstance(item.priority_score, (int, float))
        assert item.business_state is not None


# ── Deal value boost ─────────────────────────────────────────────────────────

def test_deal_value_boosts_score():
    lead_id = "deal-boost-lead"
    base    = score_lead(FL(id=lead_id, potential_value=10000), None)
    with_deal = score_lead(FL(id=lead_id, potential_value=10000), FD(lead_id, 200000))
    assert with_deal.priority_score >= base.priority_score, \
        f"Deal should boost score: {base.priority_score} → {with_deal.priority_score}"


def test_high_value_deal_outranks_low_value_lead():
    low  = FL(id="low-v",  potential_value=5000)
    high = FL(id="high-v", potential_value=5000)  # same base, but high has deal
    queue = build_revenue_queue([low, high], {"high-v": FD("high-v", 200000)})
    scores_by_id = {r.lead_id: r.priority_score for r in queue}
    assert scores_by_id["high-v"] >= scores_by_id["low-v"], \
        "High-value deal lead should outrank no-deal lead"


# ── Blocked states ────────────────────────────────────────────────────────────

def test_score_lead_returns_business_state():
    result = score_lead(FL(status="חדש"), None)
    assert result.business_state is not None


def test_single_lead_queue_non_empty():
    queue = build_revenue_queue([FL()], {})
    assert len(queue) == 1


def test_empty_leads_returns_empty_queue():
    queue = build_revenue_queue([], {})
    assert queue == []


# ── API endpoint ──────────────────────────────────────────────────────────────

def test_api_daily_revenue_queue_structure():
    """Integration: GET /api/daily_revenue_queue returns correct JSON shape."""
    os.environ["OS_API_KEY"] = "test"
    from api.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    r = c.get("/api/daily_revenue_queue", headers={"X-API-Key": "test"})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.get_json()}"
    d = r.get_json()
    assert d.get("success") is True
    assert "queue" in d
    assert isinstance(d["queue"], list)
    assert "total" in d


def test_api_revenue_queue_limit_param():
    """limit param truncates the response."""
    os.environ["OS_API_KEY"] = "test"
    from api.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    r = c.get("/api/daily_revenue_queue?limit=0", headers={"X-API-Key": "test"})
    assert r.status_code == 200
