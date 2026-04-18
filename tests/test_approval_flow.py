"""
tests/test_approval_flow.py — Approval flow integration tests.

Proves the critical path: create → resolve → event → activity log.
SQLite in-memory; no external services.
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


_AUTH = {"X-API-Key": "test"}


def _create_approval_http(client, **kw):
    body = {"action": "send_outreach", "risk_level": 2,
            "lead_id": "", "lead_name": "", **kw}
    r = client.post("/api/approvals/create", json=body, headers=_AUTH)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d.get("success"), d
    return d["data"]["id"]


class TestApprovalHTTPEndpoints(unittest.TestCase):
    """HTTP approval endpoints: create / resolve / list / history."""

    def setUp(self):
        self.c = _client()

    def test_create_returns_pending_id(self):
        aid = _create_approval_http(self.c, lead_id="l-c1", lead_name="Create Test")
        self.assertTrue(aid)

    def test_resolve_approve_sets_approved(self):
        aid = _create_approval_http(self.c, lead_id="l-a1")
        r = self.c.post(f"/api/approvals/{aid}",
                        json={"action": "approve"}, headers=_AUTH)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("success"), d)
        self.assertEqual(d["data"]["approval"]["status"], "approved")

    def test_resolve_deny_sets_denied(self):
        aid = _create_approval_http(self.c, lead_id="l-d1")
        r = self.c.post(f"/api/approvals/{aid}",
                        json={"action": "deny"}, headers=_AUTH)
        d = r.get_json()
        self.assertTrue(d.get("success"), d)
        self.assertEqual(d["data"]["approval"]["status"], "denied")

    def test_double_resolve_returns_404(self):
        aid = _create_approval_http(self.c)
        self.c.post(f"/api/approvals/{aid}",
                    json={"action": "approve"}, headers=_AUTH)
        r2 = self.c.post(f"/api/approvals/{aid}",
                         json={"action": "approve"}, headers=_AUTH)
        self.assertEqual(r2.status_code, 404)

    def test_invalid_action_returns_400(self):
        aid = _create_approval_http(self.c)
        r = self.c.post(f"/api/approvals/{aid}",
                        json={"action": "maybe"}, headers=_AUTH)
        self.assertEqual(r.status_code, 400)

    def test_list_pending_contains_created(self):
        aid = _create_approval_http(self.c, lead_id="l-list1")
        r = self.c.get("/api/approvals", headers=_AUTH)
        d = r.get_json()
        ids = [a["id"] for a in d["data"]["approvals"]]
        self.assertIn(aid, ids)

    def test_resolved_appears_in_history(self):
        aid = _create_approval_http(self.c)
        self.c.post(f"/api/approvals/{aid}",
                    json={"action": "approve"}, headers=_AUTH)
        r = self.c.get("/api/approvals/history", headers=_AUTH)
        d = r.get_json()
        ids = [a["id"] for a in d["data"]["history"]]
        self.assertIn(aid, ids)

    def test_resolved_not_in_pending(self):
        aid = _create_approval_http(self.c)
        self.c.post(f"/api/approvals/{aid}",
                    json={"action": "deny"}, headers=_AUTH)
        r = self.c.get("/api/approvals", headers=_AUTH)
        d = r.get_json()
        ids = [a["id"] for a in d["data"]["approvals"]]
        self.assertNotIn(aid, ids)

    def test_approve_emits_approval_granted_event(self):
        from events.event_bus import event_bus
        import events.event_types as ET
        seen = []
        original = event_bus.publish

        def capture(event_type, **kw):
            seen.append(event_type)
            return original(event_type, **kw)

        event_bus.publish = capture
        try:
            aid = _create_approval_http(self.c)
            self.c.post(f"/api/approvals/{aid}",
                        json={"action": "approve"}, headers=_AUTH)
            self.assertIn(ET.APPROVAL_GRANTED, seen,
                          f"APPROVAL_GRANTED not emitted; saw: {seen}")
        finally:
            event_bus.publish = original

    def test_deny_emits_approval_denied_event(self):
        from events.event_bus import event_bus
        import events.event_types as ET
        seen = []
        original = event_bus.publish

        def capture(event_type, **kw):
            seen.append(event_type)
            return original(event_type, **kw)

        event_bus.publish = capture
        try:
            aid = _create_approval_http(self.c)
            self.c.post(f"/api/approvals/{aid}",
                        json={"action": "deny"}, headers=_AUTH)
            self.assertIn(ET.APPROVAL_DENIED, seen,
                          f"APPROVAL_DENIED not emitted; saw: {seen}")
        finally:
            event_bus.publish = original


class TestResolveApprovalSharedFunction(unittest.TestCase):
    """_resolve_approval() shared function — called by both HTTP and Telegram."""

    def _make_approval(self, details: dict, action: str = "send_outreach"):
        from services.storage.repositories.approval_repo import ApprovalRepository
        a = ApprovalRepository().create(
            action=action, details=details,
            risk_level=2, requested_by="test",
        )
        return a.id

    def test_unknown_id_returns_hebrew_error(self):
        from api.routes.approvals import _resolve_approval
        result = _resolve_approval("nonexistent-id-xxxxxxxx", "approve", "test")
        self.assertIn("לא נמצא", result)

    def test_approve_with_lead_body_logs_activity(self):
        from api.routes.approvals import _resolve_approval
        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel

        aid = self._make_approval({
            "lead_id": "la-act-1",
            "lead_name": "Activity Test Lead",
            "body": "Hello test outreach message",
            "channel": "whatsapp",
        })
        result = _resolve_approval(aid, "approve", source="test")
        self.assertIn("✅", result)

        with get_session() as s:
            acts = s.query(ActivityModel).filter_by(lead_id="la-act-1").all()
        self.assertGreater(len(acts), 0,
                           "ActivityModel not written after lead-ops approval")

    def test_approve_with_lead_body_emits_outreach_sent(self):
        from api.routes.approvals import _resolve_approval
        from events.event_bus import event_bus
        import events.event_types as ET
        seen = []
        original = event_bus.publish

        def capture(event_type, **kw):
            seen.append(event_type)
            return original(event_type, **kw)

        event_bus.publish = capture
        try:
            aid = self._make_approval({
                "lead_id": "la-ev-2",
                "lead_name": "Event Test",
                "body": "test",
                "channel": "whatsapp",
            })
            _resolve_approval(aid, "approve", source="test")
            self.assertIn(ET.LEAD_OUTREACH_SENT, seen,
                          f"LEAD_OUTREACH_SENT not emitted; saw: {seen}")
        finally:
            event_bus.publish = original

    def test_deny_returns_denied_string(self):
        from api.routes.approvals import _resolve_approval
        aid = self._make_approval({"lead_id": "la-deny-1"})
        result = _resolve_approval(aid, "deny", source="test")
        self.assertIn("נדחה", result)

    def test_already_resolved_returns_not_found(self):
        from api.routes.approvals import _resolve_approval
        aid = self._make_approval({"lead_id": "la-dup-1"})
        _resolve_approval(aid, "approve", source="test")
        result2 = _resolve_approval(aid, "approve", source="test")
        self.assertIn("לא נמצא", result2)


class TestLeadOpsExecuteEndpoint(unittest.TestCase):
    """lead_ops/execute endpoint — proves approval_granted event + learning hook."""

    def setUp(self):
        self.c = _client()

    def _make_approval(self, details=None):
        from services.storage.repositories.approval_repo import ApprovalRepository
        a = ApprovalRepository().create(
            action="send_outreach",
            details=details or {"lead_id": "lx-1", "lead_name": "Execute Test",
                                "body": "test body", "channel": "whatsapp"},
            risk_level=2, requested_by="test_lead_ops",
        )
        return a.id

    def test_execute_approve_returns_approved(self):
        aid = self._make_approval()
        r = self.c.post(f"/api/lead_ops/execute/{aid}",
                        json={"action": "approve"}, headers=_AUTH)
        d = r.get_json()
        self.assertTrue(d.get("success"), d)
        self.assertEqual(d.get("status"), "approved")

    def test_execute_deny_returns_denied(self):
        aid = self._make_approval({"lead_id": "lx-deny-1"})
        r = self.c.post(f"/api/lead_ops/execute/{aid}",
                        json={"action": "deny"}, headers=_AUTH)
        d = r.get_json()
        self.assertTrue(d.get("success"), d)
        self.assertEqual(d.get("status"), "denied")

    def test_execute_approve_emits_approval_granted(self):
        from events.event_bus import event_bus
        import events.event_types as ET
        seen = []
        original = event_bus.publish

        def capture(event_type, **kw):
            seen.append(event_type)
            return original(event_type, **kw)

        event_bus.publish = capture
        try:
            aid = self._make_approval({"lead_id": "lx-ev-1"})
            self.c.post(f"/api/lead_ops/execute/{aid}",
                        json={"action": "approve"}, headers=_AUTH)
            self.assertIn(ET.APPROVAL_GRANTED, seen,
                          f"APPROVAL_GRANTED not emitted by lead_ops/execute; saw: {seen}")
        finally:
            event_bus.publish = original

    def test_execute_approve_emits_outreach_sent_for_lead(self):
        from events.event_bus import event_bus
        import events.event_types as ET
        seen = []
        original = event_bus.publish

        def capture(event_type, **kw):
            seen.append(event_type)
            return original(event_type, **kw)

        event_bus.publish = capture
        try:
            aid = self._make_approval({
                "lead_id": "lx-os-1", "lead_name": "OS Lead",
                "body": "hello", "channel": "whatsapp",
            })
            self.c.post(f"/api/lead_ops/execute/{aid}",
                        json={"action": "approve"}, headers=_AUTH)
            self.assertIn(ET.LEAD_OUTREACH_SENT, seen,
                          f"LEAD_OUTREACH_SENT not emitted; saw: {seen}")
        finally:
            event_bus.publish = original

    def test_execute_approve_logs_activity(self):
        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel
        aid = self._make_approval({
            "lead_id": "lx-act-2", "lead_name": "Act Lead",
            "body": "activity test", "channel": "whatsapp",
        })
        self.c.post(f"/api/lead_ops/execute/{aid}",
                    json={"action": "approve"}, headers=_AUTH)
        with get_session() as s:
            acts = s.query(ActivityModel).filter_by(lead_id="lx-act-2").all()
        self.assertGreater(len(acts), 0,
                           "No ActivityModel logged after lead_ops/execute approve")

    def test_execute_not_found_returns_404(self):
        r = self.c.post("/api/lead_ops/execute/nonexistent-id-xyz",
                        json={"action": "approve"}, headers=_AUTH)
        self.assertIn(r.status_code, (404, 409))

    def test_execute_invalid_action_returns_400(self):
        aid = self._make_approval()
        r = self.c.post(f"/api/lead_ops/execute/{aid}",
                        json={"action": "maybe"}, headers=_AUTH)
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
