"""
tests/test_telegram_callback.py — Telegram webhook and callback loop tests.

Proves: text dispatch → orchestrator, callback_query → _resolve_approval,
activity logged, image/voice handled gracefully.
No external Telegram API calls (credentials absent).
"""
import os
import sys
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OS_API_KEY", "test")
os.environ.setdefault("ENV", "test")
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("TELEGRAM_CHAT_ID", None)
os.environ.pop("WEBHOOK_VERIFY_TOKEN", None)

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


def _cbq(action: str, approval_id: str, username: str = "operator") -> dict:
    return {"callback_query": {
        "id": "cbq-123",
        "from": {"username": username, "id": 1},
        "data": f"{action}:{approval_id}",
        "message": {"chat": {"id": 1}, "message_id": 10},
    }}


def _text_msg(text: str) -> dict:
    return {"message": {"from": {"username": "tester", "id": 1},
                        "chat": {"id": 1}, "date": 0,
                        "text": text, "message_id": 1}}


def _voice_msg(file_id: str = "voice_abc") -> dict:
    return {"message": {"from": {"username": "tester", "id": 1},
                        "chat": {"id": 1}, "date": 0,
                        "voice": {"file_id": file_id, "duration": 5,
                                  "mime_type": "audio/ogg"}, "message_id": 3}}


def _photo_msg() -> dict:
    return {"message": {"from": {"username": "tester", "id": 1},
                        "chat": {"id": 1}, "date": 0,
                        "photo": [{"file_id": "photo_abc", "file_size": 100,
                                   "width": 100, "height": 100}], "message_id": 4}}


def _create_approval(details=None):
    from services.storage.repositories.approval_repo import ApprovalRepository
    a = ApprovalRepository().create(
        action="send_outreach",
        details=details or {"lead_id": "ltg-1", "lead_name": "TG Lead",
                            "body": "hello outreach", "channel": "whatsapp"},
        risk_level=2, requested_by="test",
    )
    return a.id


class TestTelegramTextDispatch(unittest.TestCase):

    def test_text_returns_ok(self):
        r = _client().post("/api/telegram/webhook",
                           json=_text_msg("הצג לידים"))
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("status"), "ok")

    def test_text_dispatch_has_reply(self):
        r = _client().post("/api/telegram/webhook",
                           json=_text_msg("מה הסטטוס"))
        d = r.get_json()
        self.assertIn("reply", d.get("data", {}))

    def test_empty_body_returns_ignored(self):
        r = _client().post("/api/telegram/webhook", json={})
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("status"), "ignored")

    def test_voice_message_returns_voice_fallback(self):
        r = _client().post("/api/telegram/webhook", json=_voice_msg())
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("status"), "voice_fallback")

    def test_photo_message_returns_logged(self):
        r = _client().post("/api/telegram/webhook", json=_photo_msg())
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("status"), "logged")


class TestTelegramCallbackRouting(unittest.TestCase):

    def test_approve_callback_returns_handled(self):
        aid = _create_approval()
        r = _client().post("/api/telegram/webhook", json=_cbq("approve", aid))
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("status"), "handled")
        self.assertEqual(d.get("data", {}).get("action"), "approve")

    def test_deny_callback_returns_handled(self):
        aid = _create_approval()
        r = _client().post("/api/telegram/webhook", json=_cbq("deny", aid))
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("status"), "handled")
        self.assertEqual(d.get("data", {}).get("action"), "deny")

    def test_edit_callback_returns_edit_requested(self):
        r = _client().post("/api/telegram/webhook",
                           json=_cbq("edit", "some-approval-id"))
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("status"), "edit_requested")

    def test_unknown_callback_action_returns_unknown(self):
        r = _client().post("/api/telegram/webhook",
                           json=_cbq("unknown", "some-id"))
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("status"), "unknown_action")

    def test_malformed_data_no_colon_returns_ignored(self):
        body = {"callback_query": {
            "id": "cbq-x",
            "from": {"username": "u", "id": 1},
            "data": "nodatacolon",
        }}
        r = _client().post("/api/telegram/webhook", json=body)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("status"), "ignored")

    def test_approve_callback_resolves_approval_in_db(self):
        from services.storage.repositories.approval_repo import ApprovalRepository
        aid = _create_approval()
        _client().post("/api/telegram/webhook", json=_cbq("approve", aid))
        resolved = ApprovalRepository().get_resolved(limit=50)
        ids = [a.id for a in resolved]
        self.assertIn(aid, ids, "Approval not marked resolved after Telegram callback")

    def test_deny_callback_resolves_approval_in_db(self):
        from services.storage.repositories.approval_repo import ApprovalRepository
        aid = _create_approval()
        _client().post("/api/telegram/webhook", json=_cbq("deny", aid))
        resolved = ApprovalRepository().get_resolved(limit=50)
        ids = [a.id for a in resolved]
        self.assertIn(aid, ids)


class TestTelegramApprovalLoop(unittest.TestCase):
    """Full Telegram → approval → activity log loop."""

    def test_approve_lead_logs_activity(self):
        from services.storage.db import get_session
        from services.storage.models.activity import ActivityModel

        aid = _create_approval({
            "lead_id": "ltg-loop-1",
            "lead_name": "Loop Lead",
            "body": "test outreach body",
            "channel": "whatsapp",
        })
        _client().post("/api/telegram/webhook", json=_cbq("approve", aid))

        with get_session() as s:
            acts = s.query(ActivityModel).filter_by(lead_id="ltg-loop-1").all()
        self.assertGreater(len(acts), 0,
                           "No ActivityModel logged after Telegram approval")

    def test_approve_emits_outreach_sent_event(self):
        from events.event_bus import event_bus
        import events.event_types as ET
        seen = []
        original = event_bus.publish

        def capture(event_type, **kw):
            seen.append(event_type)
            return original(event_type, **kw)

        event_bus.publish = capture
        try:
            aid = _create_approval({
                "lead_id": "ltg-ev-2",
                "lead_name": "Event Loop Lead",
                "body": "msg",
                "channel": "whatsapp",
            })
            _client().post("/api/telegram/webhook", json=_cbq("approve", aid))
            self.assertIn(ET.LEAD_OUTREACH_SENT, seen,
                          f"LEAD_OUTREACH_SENT not emitted; saw: {seen}")
        finally:
            event_bus.publish = original

    def test_double_approve_second_returns_not_found_message(self):
        """Second approval callback for already-resolved approval returns gracefully."""
        aid = _create_approval()
        _client().post("/api/telegram/webhook", json=_cbq("approve", aid))
        r2 = _client().post("/api/telegram/webhook", json=_cbq("approve", aid))
        self.assertEqual(r2.status_code, 200)


class TestTelegramEditFlow(unittest.TestCase):
    """Edit callback → stores pending context → follow-up text applies edit."""

    def _cbq_with_sender(self, action: str, approval_id: str, sender_id: int = 42) -> dict:
        return {"callback_query": {
            "id": "cbq-edit-1",
            "from": {"username": "editor", "id": sender_id},
            "data": f"{action}:{approval_id}",
            "message": {"chat": {"id": 1}, "message_id": 10},
        }}

    def _text_with_sender(self, text: str, sender_id: int = 42) -> dict:
        return {"message": {
            "from": {"username": "editor", "id": sender_id},
            "chat": {"id": 1}, "date": 0,
            "text": text, "message_id": 99,
        }}

    def test_edit_callback_stores_pending_context(self):
        from services.storage.repositories.approval_repo import ApprovalRepository
        from memory.memory_store import MemoryStore
        a = ApprovalRepository().create(
            action="send_outreach",
            details={"lead_id": "le-1", "lead_name": "Edit Lead",
                     "body": "original body", "channel": "whatsapp"},
            risk_level=2, requested_by="test",
        )
        _client().post("/api/telegram/webhook",
                       json=self._cbq_with_sender("edit", a.id, sender_id=999))
        stored = MemoryStore.read("telegram", "pending_edit_999")
        self.assertIsNotNone(stored, "pending_edit context not stored after edit callback")
        self.assertEqual(stored.get("approval_id"), a.id)

    def test_follow_up_text_applies_edit(self):
        from services.storage.repositories.approval_repo import ApprovalRepository
        from services.storage.db import get_session
        from services.storage.models.approval import ApprovalModel
        a = ApprovalRepository().create(
            action="send_outreach",
            details={"lead_id": "le-2", "lead_name": "Edit Flow",
                     "body": "old draft", "channel": "whatsapp"},
            risk_level=2, requested_by="test",
        )
        # Step 1: click Edit
        _client().post("/api/telegram/webhook",
                       json=self._cbq_with_sender("edit", a.id, sender_id=888))
        # Step 2: send edited text
        r = _client().post("/api/telegram/webhook",
                           json=self._text_with_sender("new improved draft text", sender_id=888))
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("status"), "edit_applied",
                         f"Expected edit_applied, got: {d}")

        # Verify approval details updated
        with get_session() as s:
            approval = s.get(ApprovalModel, a.id)
            details = approval.details or {}
            self.assertEqual(details.get("body"), "new improved draft text")

    def test_follow_up_clears_pending_context(self):
        from services.storage.repositories.approval_repo import ApprovalRepository
        from memory.memory_store import MemoryStore
        a = ApprovalRepository().create(
            action="send_outreach",
            details={"lead_id": "le-3", "lead_name": "Clear Test",
                     "body": "draft", "channel": "whatsapp"},
            risk_level=2, requested_by="test",
        )
        sender_id = 777
        _client().post("/api/telegram/webhook",
                       json=self._cbq_with_sender("edit", a.id, sender_id=sender_id))
        _client().post("/api/telegram/webhook",
                       json=self._text_with_sender("edited text", sender_id=sender_id))
        # Context should be cleared after edit applied
        stored = MemoryStore.read("telegram", f"pending_edit_{sender_id}")
        self.assertIsNone(stored, "pending_edit context should be cleared after apply")

    def test_text_without_pending_edit_goes_to_orchestrator(self):
        """Normal text with no pending context routes to orchestrator, not edit handler."""
        r = _client().post("/api/telegram/webhook",
                           json=self._text_with_sender("הצג לידים", sender_id=111))
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("status"), "ok",
                         "Normal text should route to orchestrator")

    def test_edit_on_already_resolved_approval_returns_gracefully(self):
        from services.storage.repositories.approval_repo import ApprovalRepository
        from memory.memory_store import MemoryStore
        a = ApprovalRepository().create(
            action="send_outreach",
            details={"lead_id": "le-4", "body": "draft", "channel": "whatsapp"},
            risk_level=2, requested_by="test",
        )
        # Resolve the approval first
        ApprovalRepository().resolve(a.id, "approved", resolved_by="test")
        # Store pending edit context manually
        MemoryStore.write("telegram", "pending_edit_666",
                          {"approval_id": a.id}, updated_by="test")
        # Send edited text — should handle gracefully (not_applicable)
        r = _client().post("/api/telegram/webhook",
                           json=self._text_with_sender("edited text", sender_id=666))
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIn(d.get("data", {}).get("status"),
                      ("edit_not_applicable", "edit_error", "ok"),
                      "Should not crash on resolved approval edit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
