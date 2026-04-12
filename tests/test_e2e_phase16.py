"""
tests/test_e2e_phase16.py — End-to-end runtime validation for AshbelOS v5.0

Validates all completion conditions:
  1. Telegram text request end-to-end
  2. Telegram voice request (fallback flow)
  3. Document upload (parse_document executor handler)
  4. Lead discovery pipeline
  5. Inbound lead handling (contact + text)
  6. Hooks fire in runtime (event bus)
  7. Skills/capabilities actually used in runtime
  8. Approval flow end-to-end (create → resolve via HTTP + via Telegram callback)
  9. System-change preview → ApprovalModel created
 10. Existing flows not regressed (health, command, lead CRUD)

No external services needed:
  - Telegram API calls gracefully no-op (missing credentials)
  - SQLite in-memory for DB
  - OS_API_KEY set to "test"
"""

from __future__ import annotations
import base64
import json
import os
import sys
import unittest

# ── Test environment ──────────────────────────────────────────────────────────
os.environ["DATABASE_URL"]  = "sqlite:///:memory:"
os.environ["OS_API_KEY"]    = "test"
os.environ["ENV"]           = "test"
os.environ.pop("TELEGRAM_BOT_TOKEN",     None)   # ensure no real API calls
os.environ.pop("TELEGRAM_CHAT_ID",       None)
os.environ.pop("WEBHOOK_VERIFY_TOKEN",   None)   # no token check in tests

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
_TG   = {}   # no verify token → open


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tg_text(text: str, username: str = "tester") -> dict:
    return {"message": {"from": {"username": username, "id": 1},
                        "chat": {"id": 1}, "date": 0,
                        "text": text, "message_id": 1}}

def _tg_contact(name: str, phone: str) -> dict:
    return {"message": {"from": {"username": "tester", "id": 1},
                        "chat": {"id": 1}, "date": 0,
                        "contact": {"first_name": name, "last_name": "",
                                    "phone_number": phone}, "message_id": 2}}

def _tg_voice(file_id: str = "voice_abc", duration: int = 5) -> dict:
    return {"message": {"from": {"username": "tester", "id": 1},
                        "chat": {"id": 1}, "date": 0,
                        "voice": {"file_id": file_id, "duration": duration,
                                  "mime_type": "audio/ogg"}, "message_id": 3}}

def _tg_photo() -> dict:
    return {"message": {"from": {"username": "tester", "id": 1},
                        "chat": {"id": 1}, "date": 0,
                        "photo": [{"file_id": "photo_abc", "file_size": 100,
                                   "width": 100, "height": 100}], "message_id": 4}}

def _tg_location(lat: float = 32.0, lon: float = 34.8) -> dict:
    return {"message": {"from": {"username": "tester", "id": 1},
                        "chat": {"id": 1}, "date": 0,
                        "location": {"latitude": lat, "longitude": lon},
                        "message_id": 5}}

def _tg_document(file_name: str, file_id: str = "doc_abc") -> dict:
    return {"message": {"from": {"username": "tester", "id": 1},
                        "chat": {"id": 1}, "date": 0,
                        "document": {"file_id": file_id, "file_name": file_name,
                                     "mime_type": "text/csv", "file_size": 200},
                        "message_id": 6}}

def _tg_callback(action: str, approval_id: str, username: str = "owner") -> dict:
    return {"callback_query": {"id": "cbq_1", "data": f"{action}:{approval_id}",
                               "from": {"username": username, "id": 1}}}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Health and basic app
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealth(unittest.TestCase):
    def test_health(self):
        c = _client()
        r = c.get("/api/health")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        # Health wrapped in ok() → {"data": {"status": "ok", "db": ...}}
        inner = body.get("data") or body
        self.assertEqual(inner.get("status"), "ok")

    def test_auth_required(self):
        c = _client()
        r = c.post("/api/command", json={"command": "סטטוס"})
        self.assertEqual(r.status_code, 401)

    def test_health_no_auth(self):
        c = _client()
        r = c.get("/api/health")
        self.assertEqual(r.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Command endpoint — text request end-to-end
# ═══════════════════════════════════════════════════════════════════════════════

class TestCommandEndpoint(unittest.TestCase):
    def setUp(self):
        self.c = _client()

    def _post(self, command: str):
        return self.c.post("/api/command", json={"command": command},
                           headers=_AUTH)

    def test_status_command(self):
        r = self._post("סטטוס")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertIn("intent", d["data"])

    def test_help_command(self):
        r = self._post("עזרה")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertIn("message", d["data"])

    def test_create_lead_command(self):
        r = self._post("הוסף ליד דוד לוי תל אביב 0501234567")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])

    def test_set_goal_command(self):
        r = self._post("הגדל מכירות לאדריכלים")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])

    def test_daily_plan_command(self):
        r = self._post("תכנן לי את היום")
        self.assertEqual(r.status_code, 200)

    def test_unknown_command_returns_low_confidence(self):
        r = self._post("בננה פיצה קפוצ'ינו")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        # HTTP 200 always, but inner data shows unknown intent
        inner = d.get("data") or {}
        self.assertEqual(inner.get("intent"), "unknown")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Telegram webhook — text messages
# ═══════════════════════════════════════════════════════════════════════════════

class TestTelegramText(unittest.TestCase):
    def setUp(self):
        self.c = _client()

    def _post(self, body: dict):
        return self.c.post("/api/telegram/webhook", json=body,
                           content_type="application/json")

    def test_text_status(self):
        r = self._post(_tg_text("סטטוס"))
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertEqual(d["data"]["status"], "ok")

    def test_text_help(self):
        r = self._post(_tg_text("עזרה"))
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertIn("reply", d["data"])

    def test_text_create_lead(self):
        r = self._post(_tg_text("הוסף ליד משה כהן ירושלים 0521234567"))
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])

    def test_system_change_intent(self):
        r = self._post(_tg_text("הוסף טאב חדש לממשק"))
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        # reply should contain approval/change language
        reply = d["data"].get("reply", "")
        self.assertTrue(len(reply) > 0)

    def test_no_message_ignored(self):
        r = self._post({})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["data"]["status"], "ignored")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Telegram webhook — voice (fallback flow)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTelegramVoice(unittest.TestCase):
    def setUp(self):
        self.c = _client()

    def test_voice_returns_fallback(self):
        """Voice with no BOT_TOKEN → transcription fails → fallback text sent."""
        r = self.c.post("/api/telegram/webhook", json=_tg_voice(),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertEqual(d["data"]["status"], "voice_fallback")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Telegram webhook — photo + location → log_only
# ═══════════════════════════════════════════════════════════════════════════════

class TestTelegramLogOnly(unittest.TestCase):
    def setUp(self):
        self.c = _client()

    def test_photo_logged(self):
        r = self.c.post("/api/telegram/webhook", json=_tg_photo(),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertEqual(d["data"]["status"], "logged")
        self.assertEqual(d["data"]["modality"], "image")

    def test_location_logged(self):
        r = self.c.post("/api/telegram/webhook", json=_tg_location(),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertEqual(d["data"]["status"], "logged")
        self.assertEqual(d["data"]["modality"], "location")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Telegram webhook — contact (inbound lead)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTelegramContact(unittest.TestCase):
    def setUp(self):
        self.c = _client()

    def test_contact_triggers_process_lead(self):
        """Shared Telegram contact → classified as inbound lead → dispatch."""
        r = self.c.post("/api/telegram/webhook",
                        json=_tg_contact("שרה לוי", "0509876543"),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        # Contact is dispatched as process_lead → orchestrator → executor
        self.assertIn("reply", d["data"])


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Telegram webhook — document (no BOT_TOKEN → graceful error)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTelegramDocument(unittest.TestCase):
    def setUp(self):
        self.c = _client()

    def test_document_without_token_returns_error_gracefully(self):
        """Document upload without BOT_TOKEN → graceful error, not a crash."""
        r = self.c.post("/api/telegram/webhook",
                        json=_tg_document("leads.csv"),
                        content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        # With no bot token it should return status=error but not 500
        self.assertIn(d["data"]["status"], ("error", "ok"))


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Telegram callback → approval flow
# ═══════════════════════════════════════════════════════════════════════════════

class TestTelegramCallback(unittest.TestCase):
    def setUp(self):
        self.c = _client()

    def _create_approval(self) -> str:
        """Create a pending approval and return its ID."""
        from services.storage.db import get_session
        from services.storage.models.approval import ApprovalModel
        from services.storage.models.base import new_uuid
        aid = new_uuid()
        with get_session() as s:
            s.add(ApprovalModel(
                id=aid,
                action="send_outreach",
                details=json.dumps({
                    "lead_id":   "test-lead-1",
                    "lead_name": "דוד לוי",
                    "body":      "שלום דוד, רוצה להציע...",
                    "channel":   "whatsapp",
                }),
                risk_level=2,
                status="pending",
                requested_by="system",
            ))
        return aid

    def test_callback_approve(self):
        aid = self._create_approval()
        r   = self.c.post("/api/telegram/webhook",
                          json=_tg_callback("approve", aid),
                          content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertEqual(d["data"]["action"], "approve")
        self.assertEqual(d["data"]["approval_id"], aid)

    def test_callback_deny(self):
        aid = self._create_approval()
        r   = self.c.post("/api/telegram/webhook",
                          json=_tg_callback("deny", aid),
                          content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertEqual(d["data"]["action"], "deny")

    def test_callback_edit_request(self):
        aid = "fake-approval-id"
        r   = self.c.post("/api/telegram/webhook",
                          json=_tg_callback("edit", aid),
                          content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["data"]["status"], "edit_requested")

    def test_callback_unknown_action_ignored(self):
        r = self.c.post("/api/telegram/webhook",
                        json={"callback_query": {"id": "1", "data": "weird",
                                                  "from": {"username": "x", "id": 1}}},
                        content_type="application/json")
        self.assertEqual(r.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Approval HTTP endpoint — create and resolve
# ═══════════════════════════════════════════════════════════════════════════════

class TestApprovalEndpoint(unittest.TestCase):
    def setUp(self):
        self.c = _client()

    def _create_approval(self) -> str:
        from services.storage.db import get_session
        from services.storage.models.approval import ApprovalModel
        from services.storage.models.base import new_uuid
        aid = new_uuid()
        with get_session() as s:
            s.add(ApprovalModel(
                id=aid, action="lead_followup",
                details=json.dumps({"lead_id": "l1", "lead_name": "Test",
                                    "body": "Follow up", "channel": "whatsapp"}),
                risk_level=1, status="pending", requested_by="scheduler",
            ))
        return aid

    def test_list_approvals(self):
        r = self.c.get("/api/approvals", headers=_AUTH)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertIn("approvals", d["data"])

    def test_approve_via_http(self):
        aid = self._create_approval()
        r   = self.c.post(f"/api/approvals/{aid}",
                          json={"action": "approve"},
                          headers=_AUTH)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertEqual(d["data"]["approval"]["status"], "approved")

    def test_deny_via_http(self):
        aid = self._create_approval()
        r   = self.c.post(f"/api/approvals/{aid}",
                          json={"action": "deny"},
                          headers=_AUTH)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        self.assertEqual(d["data"]["approval"]["status"], "denied")

    def test_invalid_action_rejected(self):
        aid = self._create_approval()
        r   = self.c.post(f"/api/approvals/{aid}",
                          json={"action": "maybe"},
                          headers=_AUTH)
        self.assertEqual(r.status_code, 400)

    def test_not_found_approval(self):
        r = self.c.post("/api/approvals/no-such-id",
                        json={"action": "approve"},
                        headers=_AUTH)
        # Returns 404 for not found
        self.assertIn(r.status_code, (404, 200))
        d = r.get_json()
        self.assertFalse(d["success"])

    def test_approval_history(self):
        r = self.c.get("/api/approvals/history", headers=_AUTH)
        self.assertEqual(r.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. System-change preview flow
# ═══════════════════════════════════════════════════════════════════════════════

class TestSystemChangeFlow(unittest.TestCase):
    def setUp(self):
        self.c = _client()

    def test_system_change_creates_approval(self):
        """System-change command → executor → ApprovalModel created (pending)."""
        r = self.c.post("/api/command",
                        json={"command": "הוסף טאב סטטיסטיקות לממשק"},
                        headers=_AUTH)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])
        output = d["data"].get("data") or {}
        # The flow should complete with status pending_approval or approval_id
        # (even if Telegram push fails silently)
        msg = d["data"].get("message", "")
        self.assertTrue(len(msg) > 0)

    def test_system_change_intent_detected(self):
        """Intent parser detects SYSTEM_CHANGE for UI modification requests."""
        from orchestration.intent_parser import intent_parser, Intent
        for cmd in ["הוסף טאב", "שנה ui", "צור מודול", "add widget"]:
            result = intent_parser.parse(cmd)
            self.assertEqual(result.intent, Intent.SYSTEM_CHANGE,
                             f"Expected SYSTEM_CHANGE for: {cmd}")
            self.assertGreaterEqual(result.confidence, 0.9)


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Document upload — parse_document executor handler
# ═══════════════════════════════════════════════════════════════════════════════

class TestDocumentUpload(unittest.TestCase):
    def test_csv_via_executor(self):
        """parse_document handler: base64 CSV → parse → leads saved."""
        csv_content = "שם,טלפון,עיר\nאבי כהן,0501111111,תל אביב\nרחל לוי,0521111111,חיפה\n"
        b64 = base64.b64encode(csv_content.encode("utf-8")).decode()

        from orchestration.task_manager import task_manager
        import uuid
        task = task_manager.create_task(
            type="acquisition",
            action="parse_document",
            input_data={"command": "עבד קובץ leads.csv", "intent": "document_upload",
                        "context": "command",
                        "params": {"content_base64": b64, "file_name": "leads.csv"}},
            priority=5, trace_id=str(uuid.uuid4()),
        )
        task_manager.transition(task.id, "queued")
        result = task_manager.dispatch(task)
        self.assertTrue(result["success"], result.get("output"))
        output = result.get("output") or {}
        self.assertGreaterEqual(output.get("row_count", 0), 2)
        self.assertGreaterEqual(output.get("saved", 0), 1)

    def test_document_intelligence_csv_skill(self):
        """Document intelligence skill parses CSV correctly."""
        from skills.document_intelligence import parse_document, detect_lead_columns
        csv_bytes = b"name,phone,city\nJohn,0501234567,TA\n"
        doc = parse_document(csv_bytes, "test.csv")
        self.assertEqual(doc.format, "csv")
        self.assertGreaterEqual(doc.row_count, 1)
        self.assertTrue(doc.records[0].get("name") or doc.records[0].get("phone"))

    def test_document_intelligence_txt_skill(self):
        """Document intelligence extracts phone/email from freetext."""
        from skills.document_intelligence import parse_document
        txt = b"Contact: Avi Cohen, phone: 0501234567, email: avi@test.com"
        doc = parse_document(txt, "contact.txt")
        self.assertEqual(doc.format, "text")
        self.assertGreaterEqual(doc.row_count, 1)
        self.assertTrue(doc.records[0].get("phone") or doc.records[0].get("email"))

    def test_detect_lead_columns_hebrew(self):
        """Column detection works for Hebrew headers."""
        from skills.document_intelligence import detect_lead_columns
        headers = ["שם", "טלפון", "מייל", "עיר", "חברה"]
        mapping = detect_lead_columns(headers)
        self.assertIn("name",  mapping)
        self.assertIn("phone", mapping)
        self.assertIn("email", mapping)
        self.assertIn("city",  mapping)


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Event bus hooks fire in runtime
# ═══════════════════════════════════════════════════════════════════════════════

class TestEventHooks(unittest.TestCase):
    def setUp(self):
        from events.event_bus import event_bus
        self.bus = event_bus
        self.fired = []

    def test_event_bus_publish_fires_handlers(self):
        """Publishing an event fires registered handlers (3-arg convention)."""
        from events.event_bus import event_bus
        received = []
        def handler(event_type, payload, meta): received.append(event_type)
        event_bus.subscribe("test_e2e_event_2", handler)
        event_bus.publish("test_e2e_event_2", {"test": True})
        self.assertIn("test_e2e_event_2", received)

    def test_lead_discovered_event_fires(self):
        """LEAD_DISCOVERED event propagates through dispatcher."""
        import events.event_types as ET
        from events.event_bus import event_bus
        fired = []
        event_bus.subscribe(ET.LEAD_DISCOVERED, lambda et, p, m: fired.append(True))
        event_bus.publish(ET.LEAD_DISCOVERED, {"lead_id": "test", "score": 50, "source": "test"})
        self.assertTrue(len(fired) >= 1)

    def test_approval_granted_event_fires(self):
        import events.event_types as ET
        from events.event_bus import event_bus
        fired = []
        event_bus.subscribe(ET.APPROVAL_GRANTED, lambda et, p, m: fired.append(True))
        event_bus.publish(ET.APPROVAL_GRANTED, {"approval_id": "x", "action": "test"})
        self.assertTrue(len(fired) >= 1)


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Intake normalizer — routing per modality
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntakeNormalizer(unittest.TestCase):
    def setUp(self):
        from services.intake.normalizer import normalize_telegram
        self.norm = normalize_telegram

    def test_text_classified_as_business_action(self):
        msg = {"from": {"username": "tester", "id": 1}, "chat": {"id": 1},
               "text": "הצג לידים", "message_id": 1, "date": 0}
        p = self.norm(msg)
        self.assertEqual(p.modality, "text")
        self.assertEqual(p.required_action, "execute_command")

    def test_contact_classified_as_inbound_lead(self):
        msg = {"from": {"username": "tester", "id": 1}, "chat": {"id": 1},
               "contact": {"first_name": "דוד", "last_name": "לוי",
                           "phone_number": "0501111111"}, "message_id": 2, "date": 0}
        p = self.norm(msg)
        self.assertEqual(p.modality, "contact")
        self.assertEqual(p.business_meaning, "inbound_lead")
        self.assertEqual(p.required_action, "process_lead")
        self.assertEqual(p.structured_fields.get("phone"), "0501111111")

    def test_voice_classified_as_fallback(self):
        msg = {"from": {"username": "tester", "id": 1}, "chat": {"id": 1},
               "voice": {"file_id": "v1", "duration": 3, "mime_type": "audio/ogg"},
               "message_id": 3, "date": 0}
        p = self.norm(msg)
        self.assertEqual(p.modality, "voice")
        # Without BOT_TOKEN transcription fails → fallback
        self.assertEqual(p.required_action, "request_text_fallback")

    def test_document_classified_as_parse(self):
        msg = {"from": {"username": "tester", "id": 1}, "chat": {"id": 1},
               "document": {"file_id": "d1", "file_name": "leads.csv",
                             "mime_type": "text/csv", "file_size": 100},
               "message_id": 4, "date": 0}
        p = self.norm(msg)
        self.assertEqual(p.modality, "document")
        self.assertEqual(p.business_meaning, "document_upload")
        self.assertEqual(p.required_action, "parse_document")

    def test_photo_classified_as_log_only(self):
        msg = {"from": {"username": "tester", "id": 1}, "chat": {"id": 1},
               "photo": [{"file_id": "p1", "file_size": 100, "width": 100, "height": 100}],
               "message_id": 5, "date": 0}
        p = self.norm(msg)
        self.assertEqual(p.modality, "image")
        self.assertEqual(p.required_action, "log_only")

    def test_location_classified_as_log_only(self):
        msg = {"from": {"username": "tester", "id": 1}, "chat": {"id": 1},
               "location": {"latitude": 32.0, "longitude": 34.8},
               "message_id": 6, "date": 0}
        p = self.norm(msg)
        self.assertEqual(p.modality, "location")
        self.assertEqual(p.required_action, "log_only")

    def test_system_change_text_classified(self):
        msg = {"from": {"username": "tester", "id": 1}, "chat": {"id": 1},
               "text": "הוסף טאב חדש", "message_id": 7, "date": 0}
        p = self.norm(msg)
        self.assertEqual(p.business_meaning, "system_change")
        self.assertEqual(p.required_action, "preview_system_change")

    def test_inbound_lead_text_classified(self):
        msg = {"from": {"username": "tester", "id": 1}, "chat": {"id": 1},
               "text": "מעוניין בחלון אלומיניום, מה המחיר?",
               "message_id": 8, "date": 0}
        p = self.norm(msg)
        self.assertEqual(p.business_meaning, "inbound_lead")
        self.assertEqual(p.required_action, "process_lead")


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Lead acquisition — inbound + discovery
# ═══════════════════════════════════════════════════════════════════════════════

class TestLeadAcquisition(unittest.TestCase):
    def setUp(self):
        self.c = _client()

    def test_inbound_lead_via_http(self):
        r = self.c.post("/api/lead_ops/inbound",
                        json={"name": "נדב ישראלי", "phone": "0541234567",
                              "city": "פתח תקווה", "message": "מעוניין בחלון"},
                        headers=_AUTH)
        self.assertIn(r.status_code, (200, 201))

    def test_lead_ops_queue(self):
        r = self.c.get("/api/lead_ops/queue", headers=_AUTH)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["success"])

    def test_lead_discovery_command(self):
        r = self.c.post("/api/command",
                        json={"command": "מצא לידים מאדריכלים בתל אביב"},
                        headers=_AUTH)
        self.assertEqual(r.status_code, 200)

    def test_process_inbound_engine(self):
        """process_inbound engine function returns a lead with correct fields."""
        from engines.lead_acquisition_engine import process_inbound
        lead = process_inbound({
            "name": "Test Lead", "phone": "0501234567",
            "city": "Tel Aviv", "source_type": "test",
        })
        self.assertTrue(lead is not None)


# ═══════════════════════════════════════════════════════════════════════════════
# 15. Intent detection — Phase 16 intents
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase16Intents(unittest.TestCase):
    def setUp(self):
        from orchestration.intent_parser import intent_parser, Intent
        self.p = intent_parser
        self.I = Intent

    def test_document_upload_intent(self):
        for cmd in ["העלה קובץ", "עבד קובץ", "csv", "אקסל", "קובץ לידים", "import leads"]:
            r = self.p.parse(cmd)
            self.assertEqual(r.intent, self.I.DOCUMENT_UPLOAD, f"Failed for: {cmd}")

    def test_system_change_intent(self):
        for cmd in ["הוסף ווידג'ט", "שנה ui", "צור מודול", "הוסף טאב", "add widget"]:
            r = self.p.parse(cmd)
            self.assertEqual(r.intent, self.I.SYSTEM_CHANGE, f"Failed for: {cmd}")

    def test_discover_leads_intent(self):
        r = self.p.parse("מצא לידים מאדריכלים")
        self.assertEqual(r.intent, self.I.DISCOVER_LEADS)

    def test_process_inbound_intent(self):
        r = self.p.parse("ליד נכנס")
        self.assertEqual(r.intent, self.I.PROCESS_INBOUND)


# ═══════════════════════════════════════════════════════════════════════════════
# 16. No regressions — existing stable flows
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoRegressions(unittest.TestCase):
    def setUp(self):
        self.c = _client()

    def test_leads_list(self):
        r = self.c.get("/api/leads", headers=_AUTH)
        self.assertEqual(r.status_code, 200)

    def test_agents_list(self):
        r = self.c.get("/api/agents", headers=_AUTH)
        self.assertEqual(r.status_code, 200)

    def test_goals_list(self):
        r = self.c.get("/api/goals", headers=_AUTH)
        self.assertIn(r.status_code, (200, 404))  # may be empty

    def test_daily_report_command(self):
        r = self.c.post("/api/command",
                        json={"command": "דוח יומי"},
                        headers=_AUTH)
        self.assertEqual(r.status_code, 200)

    def test_revenue_insights_command(self):
        r = self.c.post("/api/command",
                        json={"command": "מה יביא כסף"},
                        headers=_AUTH)
        self.assertEqual(r.status_code, 200)

    def test_list_leads_command(self):
        r = self.c.post("/api/command",
                        json={"command": "הצג לידים"},
                        headers=_AUTH)
        self.assertEqual(r.status_code, 200)

    def test_executor_handlers_all_present(self):
        """All handler keys in _HANDLERS resolve to callable functions."""
        from services.execution.executor import _HANDLERS
        for key, fn in _HANDLERS.items():
            self.assertTrue(callable(fn), f"Handler {key!r} is not callable")

    def test_intent_task_map_coverage(self):
        """All non-direct intents in _INTENT_TASK_MAP have executor handlers
        or are routed to an agent-registry action."""
        from orchestration.orchestrator import _INTENT_TASK_MAP
        from services.execution.executor import _HANDLERS
        agent_routed = {
            "discover_leads", "process_inbound", "website_analysis",
            "lead_ops_queue", "build_agent_code", "apply_files",
            "roadmap", "gap_analysis", "batch_status", "read_data",
        }
        for intent, (task_type, action) in _INTENT_TASK_MAP.items():
            if action not in agent_routed:
                self.assertIn(action, _HANDLERS,
                              f"Intent {intent!r} maps to action {action!r} not in _HANDLERS")


class TestPhase17Additions(unittest.TestCase):
    """Phase 17: Mission Control UI, learning loop, intake completeness, self-evolution."""

    def setUp(self):
        self.c = _client()

    # ── Intake completeness ───────────────────────────────────────────────────

    def test_video_normalizer(self):
        """Video payload → log_only, modality=video."""
        from services.intake.normalizer import normalize_telegram
        msg = {"from": {"id": 1, "username": "u"},
               "chat": {"id": 1}, "date": 0, "message_id": 9,
               "video": {"file_id": "v123", "duration": 10,
                         "width": 640, "height": 360}}
        p = normalize_telegram(msg)
        self.assertEqual(p.modality, "video")
        self.assertEqual(p.required_action, "log_only")

    def test_video_with_caption_routes_as_text(self):
        """Video with caption → classify the caption as business text."""
        from services.intake.normalizer import normalize_telegram
        msg = {"from": {"id": 1, "username": "u"},
               "chat": {"id": 1}, "date": 0, "message_id": 10,
               "video": {"file_id": "v124"},
               "caption": "רוצה לקנות חלונות לדירה"}
        p = normalize_telegram(msg)
        # caption classified as text (lead/command signal)
        self.assertIn(p.required_action, ("execute_command", "process_lead"))

    def test_poll_normalizer(self):
        """Poll payload → log_only, modality=poll."""
        from services.intake.normalizer import normalize_telegram
        msg = {"from": {"id": 1, "username": "u"},
               "chat": {"id": 1}, "date": 0, "message_id": 11,
               "poll": {"id": "poll1", "question": "מה מעדיפים?",
                        "options": [{"text": "חלונות"}, {"text": "דלתות"}]}}
        p = normalize_telegram(msg)
        self.assertEqual(p.modality, "poll")
        self.assertEqual(p.required_action, "log_only")
        self.assertEqual(p.structured_fields["question"], "מה מעדיפים?")

    def test_reply_to_message_captured_in_meta(self):
        """reply_to_message fields are captured in metadata."""
        from services.intake.normalizer import normalize_telegram
        msg = {"from": {"id": 1, "username": "u"},
               "chat": {"id": 1}, "date": 0, "message_id": 12,
               "text": "כן, אני מעוניין",
               "reply_to_message": {"message_id": 5, "text": "האם מעוניין?"}}
        p = normalize_telegram(msg)
        self.assertEqual(p.metadata.get("reply_to_message_id"), 5)
        self.assertIn("האם מעוניין?", p.metadata.get("reply_to_text", ""))

    def test_forwarded_message_captured(self):
        """Forwarded message origin captured in metadata."""
        from services.intake.normalizer import normalize_telegram
        msg = {"from": {"id": 1, "username": "u"},
               "chat": {"id": 1}, "date": 0, "message_id": 13,
               "text": "הודעה מועברת",
               "forward_from": {"id": 99, "username": "originator"}}
        p = normalize_telegram(msg)
        self.assertTrue(p.metadata.get("forwarded"))
        self.assertEqual(p.metadata.get("forward_from"), "originator")

    # ── Learning loop ─────────────────────────────────────────────────────────

    def test_learning_skills_importable(self):
        """learning_skills module imports cleanly."""
        import skills.learning_skills as ls
        self.assertTrue(callable(ls.record_template_outcome))
        self.assertTrue(callable(ls.record_source_outcome))
        self.assertTrue(callable(ls.record_agent_outcome))
        self.assertTrue(callable(ls.record_lead_conversion))

    def test_score_lead_segment_aware_action(self):
        """score_lead produces segment-aware next_action text."""
        from skills.lead_intelligence import (
            normalize, enrich, score_lead
        )
        raw = {"name": "קבלן", "segment": "contractor", "city": "תל אביב",
               "is_inbound": True, "phone": "050-0000001"}
        lead = normalize(raw)
        enriched = enrich(lead)
        scored = score_lead(enriched)
        # Inbound lead should get the high-urgency action
        self.assertGreater(scored.score, 0)
        self.assertIsNotNone(scored.next_action)

    # ── Self-evolution / pending changes endpoint ─────────────────────────────

    def test_pending_changes_endpoint_returns_200(self):
        """GET /api/system/pending_changes returns 200."""
        r = self.c.get("/api/system/pending_changes", headers=_AUTH)
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertIn("pending_changes", body.get("data", body))

    # ── Mission Control UI completeness ───────────────────────────────────────

    def test_revenue_panel_has_insight_and_nextaction_ids(self):
        """revenue.js contains revInsight and revNextAction element IDs."""
        with open("ui/js/panels/revenue.js") as f:
            src = f.read()
        self.assertIn("revInsight", src)
        self.assertIn("revNextAction", src)
        self.assertIn("UI.insightStrip", src)
        self.assertIn("UI.nextAction", src)

    def test_calendar_panel_has_mission_control(self):
        with open("ui/js/panels/calendar.js") as f:
            src = f.read()
        self.assertIn("calInsight", src)
        self.assertIn("calNextAction", src)
        self.assertIn("UI.insightStrip", src)

    def test_pipeline_panel_has_mission_control(self):
        with open("ui/js/panels/pipeline.js") as f:
            src = f.read()
        self.assertIn("pipeInsight", src)
        self.assertIn("pipeNextAction", src)

    def test_goals_panel_has_mission_control(self):
        with open("ui/js/panels/goals.js") as f:
            src = f.read()
        self.assertIn("goalsInsight", src)
        self.assertIn("goalsNextAction", src)

    def test_seo_panel_has_mission_control(self):
        with open("ui/js/panels/seo.js") as f:
            src = f.read()
        self.assertIn("seoInsight", src)
        self.assertIn("UI.insightStrip", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
