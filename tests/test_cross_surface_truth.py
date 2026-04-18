"""
tests/test_cross_surface_truth.py — Cross-surface integration proof.

Proves system truth across surfaces:
  lead/state change → CRM → pipeline → revenue queue → approval/next action → briefing/activity

No component-only proof. Each test traverses at least two system surfaces.
"""
import os
import sys
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OS_API_KEY", "test")
os.environ.setdefault("ENV", "test")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_APP = None


def _app():
    global _APP
    if _APP is None:
        from api.app import create_app
        _APP = create_app()
        _APP.config["TESTING"] = True
    return _APP


def _client():
    return _app().test_client()


def _headers():
    return {"X-API-Key": "test"}


def _create_lead_in_db(name="CrossLead", phone="0501234500", status="new"):
    from services.storage.repositories.lead_repo import LeadRepository
    repo = LeadRepository()
    lead = repo.create(name=name, phone=phone, city="תל אביב",
                       source="google_maps", sector="aluminum")
    if status != "new":
        repo.update_status(lead.id, status)
    repo.update_score(lead.id, 75)
    return lead.id


class TestLeadToCRMSurface(unittest.TestCase):
    """Lead created in DB → appears correctly in CRM API."""

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def test_lead_appears_in_crm_list(self):
        lead_id = _create_lead_in_db(name="CRMSurface Lead", phone="0501100001")
        r = _client().get("/api/leads", headers=_headers())
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        leads = data.get("data", {}).get("leads") or data.get("leads", [])
        ids = [l.get("id") for l in leads]
        self.assertIn(lead_id, ids, "Lead created in DB must appear in /api/leads CRM list")

    def test_lead_status_update_persists(self):
        from services.storage.repositories.lead_repo import LeadRepository
        lead_id = _create_lead_in_db(name="StatusChange Lead", phone="0501100002", status="new")
        LeadRepository().update_status(lead_id, "hot")

        r = _client().get("/api/leads", headers=_headers())
        data = r.get_json()
        leads = data.get("data", {}).get("leads") or data.get("leads", [])
        match = next((l for l in leads if l.get("id") == lead_id), None)
        self.assertIsNotNone(match, "Updated lead must appear in CRM list")
        self.assertEqual(match.get("status"), "hot", "Status update must persist and be readable via CRM API")


class TestLeadToRevenueQueueSurface(unittest.TestCase):
    """Lead in DB → appears in revenue queue with priority score and next_best_action."""

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def test_hot_lead_in_revenue_queue(self):
        _create_lead_in_db(name="QueueHot Lead", phone="0501200001", status="hot")
        r = _client().get("/api/daily_revenue_queue", headers=_headers())
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        # Revenue queue uses jsonify directly (no ok() wrapper), so queue at top level
        queue = data.get("queue") or data.get("data", {}).get("queue") or []
        self.assertGreater(len(queue), 0, "Revenue queue must not be empty when hot leads exist")
        for item in queue:
            self.assertIn("priority_score", item,
                          "Every revenue queue item must have a priority_score")
            self.assertIn("next_best_action", item,
                          "Every revenue queue item must have a next_best_action")

    def test_queue_sorted_by_priority(self):
        r = _client().get("/api/daily_revenue_queue", headers=_headers())
        data = r.get_json()
        queue = data.get("queue") or data.get("data", {}).get("queue") or []
        if len(queue) >= 2:
            scores = [item.get("priority_score", 0) for item in queue]
            self.assertEqual(scores, sorted(scores, reverse=True),
                             "Revenue queue must be sorted descending by priority_score")


class TestLeadToApprovalSurface(unittest.TestCase):
    """Lead exists → approval created for outreach → approval visible → resolve updates activity."""

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def test_approval_created_for_lead_is_visible(self):
        lead_id = _create_lead_in_db(name="Approval Surface Lead", phone="0501300001")
        from services.storage.repositories.approval_repo import ApprovalRepository
        approval = ApprovalRepository().create(
            action="send_outreach",
            details={"lead_id": lead_id, "lead_name": "Approval Surface Lead",
                     "body": "test body", "channel": "whatsapp"},
            risk_level=2, requested_by="test",
        )

        r = _client().get("/api/approvals", headers=_headers())
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        approvals = data.get("data", {}).get("approvals") or []
        ids = [a.get("id") for a in approvals]
        self.assertIn(approval.id, ids,
                      "Approval created for a lead must appear in /api/approvals list")

    def test_approval_resolve_logs_activity_for_lead(self):
        lead_id = _create_lead_in_db(name="ActivityProof Lead", phone="0501300002")
        from services.storage.repositories.approval_repo import ApprovalRepository
        approval = ApprovalRepository().create(
            action="send_outreach",
            details={"lead_id": lead_id, "lead_name": "ActivityProof Lead",
                     "body": "outreach body", "channel": "whatsapp"},
            risk_level=2, requested_by="test",
        )

        r = _client().post(f"/api/approvals/{approval.id}",
                           json={"action": "approve"},
                           headers=_headers())
        self.assertEqual(r.status_code, 200)

        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel
        with get_session() as s:
            acts = s.query(ActivityModel).filter_by(lead_id=lead_id).all()
        self.assertGreater(len(acts), 0,
                           "Approving an outreach approval must create ActivityModel for the lead")


class TestLeadToBriefingSurface(unittest.TestCase):
    """Lead in DB → briefing summary and context are accessible."""

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def test_briefing_summary_returns_lead_data(self):
        lead_id = _create_lead_in_db(name="Briefing Lead", phone="0501400001")
        r = _client().get(f"/api/briefing/summary/{lead_id}", headers=_headers())
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data.get("success"), f"Briefing summary must succeed: {data}")

    def test_briefing_context_accessible(self):
        lead_id = _create_lead_in_db(name="Context Lead", phone="0501400002")
        r = _client().get(f"/api/briefing/context/{lead_id}", headers=_headers())
        self.assertEqual(r.status_code, 200)

    def test_call_start_end_logs_activity(self):
        lead_id = _create_lead_in_db(name="Call Lead", phone="0501400003")
        r_start = _client().post("/api/briefing/call/start",
                                 json={"lead_id": lead_id},
                                 headers=_headers())
        self.assertIn(r_start.status_code, (200, 201))

        call_data = r_start.get_json().get("data", {})
        call_id = call_data.get("call_id") or call_data.get("id")

        r_end = _client().post("/api/briefing/call/end",
                               json={"lead_id": lead_id, "call_id": call_id,
                                     "duration_seconds": 120, "outcome": "positive",
                                     "notes": "great call"},
                               headers=_headers())
        self.assertEqual(r_end.status_code, 200)

        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel
        with get_session() as s:
            acts = s.query(ActivityModel).filter_by(lead_id=lead_id).all()
        self.assertGreater(len(acts), 0,
                           "call/end must persist an ActivityModel for the lead")


class TestFullOperatorLoop(unittest.TestCase):
    """Full operator loop: create lead → revenue queue → approve outreach → activity logged."""

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def test_full_operator_loop(self):
        lead_id = _create_lead_in_db(name="Full Loop Lead", phone="0501500001", status="hot")

        # Revenue queue shows the lead (jsonify response, no ok() wrapper)
        r_q = _client().get("/api/daily_revenue_queue", headers=_headers())
        queue = r_q.get_json().get("queue") or r_q.get_json().get("data", {}).get("queue") or []
        self.assertGreater(len(queue), 0, "Hot lead must appear in revenue queue")

        # Create approval for the lead
        from services.storage.repositories.approval_repo import ApprovalRepository
        approval = ApprovalRepository().create(
            action="send_outreach",
            details={"lead_id": lead_id, "lead_name": "Full Loop Lead",
                     "body": "full loop outreach", "channel": "whatsapp"},
            risk_level=2, requested_by="operator",
        )

        # Approve it
        r_approve = _client().post(f"/api/approvals/{approval.id}",
                                   json={"action": "approve"},
                                   headers=_headers())
        self.assertEqual(r_approve.status_code, 200)

        # Verify activity logged for lead
        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel
        with get_session() as s:
            acts = s.query(ActivityModel).filter_by(lead_id=lead_id).all()
        self.assertGreater(len(acts), 0, "Full loop must end with activity logged")

        # Verify approval no longer in pending list
        r_pending = _client().get("/api/approvals", headers=_headers())
        pending = r_pending.get_json().get("data", {}).get("approvals") or []
        pending_ids = [a.get("id") for a in pending]
        self.assertNotIn(approval.id, pending_ids,
                         "Resolved approval must no longer appear in pending list")


if __name__ == "__main__":
    unittest.main(verbosity=2)
