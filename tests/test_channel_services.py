"""
tests/test_channel_services.py — Channel readiness layer proof.

Proves:
  - channel_router.select() returns correct channel based on lead attributes
  - draft_for_channel() returns ChannelResult with draft + manual_instructions
  - manual_send.generate_manual_workflow() always succeeds for any channel
  - email_channel.draft_email() returns readiness result (no SMTP in test env)
  - whatsapp_readiness.draft_whatsapp() produces valid deep link
  - linkedin_readiness.draft_linkedin_message() applies compliance rules
  - channel status API endpoint returns all channels
  - channels/draft API generates draft
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


class TestChannelRouter(unittest.TestCase):

    def test_select_channel_with_phone_returns_whatsapp(self):
        from services.channels.channel_router import select_channel
        ch = select_channel({"name": "טסט", "phone": "0501234567"})
        self.assertEqual(ch, "whatsapp")

    def test_select_channel_with_email_only_returns_email(self):
        from services.channels.channel_router import select_channel
        from config.business_registry import get_active_business
        profile = get_active_business()
        # Override profile channels to email-first
        original = profile.outreach_channels
        profile.outreach_channels = ["email", "whatsapp"]
        ch = select_channel({"name": "טסט", "email": "test@test.com"}, profile)
        profile.outreach_channels = original
        self.assertEqual(ch, "email")

    def test_draft_for_channel_whatsapp_returns_deep_link(self):
        from services.channels.channel_router import draft_for_channel
        result = draft_for_channel(
            "whatsapp",
            {"name": "דוד", "phone": "0501234567"},
            "שלום דוד, אני מ-אשבל",
        )
        self.assertIn("wa.me", result.deep_link)
        self.assertEqual(result.channel, "whatsapp")
        self.assertIsNotNone(result.draft)

    def test_draft_for_channel_email_returns_draft(self):
        from services.channels.channel_router import draft_for_channel
        result = draft_for_channel(
            "email",
            {"name": "שרה", "email": "sara@test.com"},
            "שלום שרה, פנייה מ-אשבל",
            subject="הצעת מחיר",
        )
        self.assertEqual(result.channel, "email")
        self.assertIn("שרה", result.draft)

    def test_channel_status_readiness_no_smtp(self):
        from services.channels.channel_router import get_channel_status
        status = get_channel_status("email")
        self.assertIn(status["status"], ("active", "readiness"))
        self.assertEqual(status["channel"], "email")

    def test_all_channel_statuses_returns_list(self):
        from services.channels.channel_router import all_channel_statuses
        statuses = all_channel_statuses()
        self.assertGreater(len(statuses), 3)
        channels = [s["channel"] for s in statuses]
        self.assertIn("whatsapp", channels)
        self.assertIn("email", channels)


class TestManualSend(unittest.TestCase):

    def test_whatsapp_manual_always_succeeds(self):
        from services.channels.manual_send import generate_manual_workflow
        result = generate_manual_workflow("whatsapp", "דוד", "0501234567", "הודעה לדוד")
        self.assertIsNotNone(result.manual_instructions)
        self.assertIn("WhatsApp", result.manual_instructions)
        self.assertEqual(result.copy_text, "הודעה לדוד")

    def test_email_manual_always_succeeds(self):
        from services.channels.manual_send import generate_manual_workflow
        result = generate_manual_workflow("email", "שרה", "sara@example.com",
                                          "גוף המייל", "נושא")
        self.assertIsNotNone(result.manual_instructions)
        self.assertEqual(result.channel, "email")

    def test_linkedin_manual_returns_compliance_note(self):
        from services.channels.manual_send import generate_manual_workflow
        result = generate_manual_workflow("linkedin", "ראובן", "https://linkedin.com/in/r",
                                          "הודעה מקצועית")
        self.assertIn("LinkedIn", result.manual_instructions)

    def test_unknown_channel_manual_fallback(self):
        from services.channels.manual_send import generate_manual_workflow
        result = generate_manual_workflow("telegram_custom", "יוסי", "0509999999", "הודעה")
        self.assertIsNotNone(result.draft)


class TestWhatsAppReadiness(unittest.TestCase):

    def test_draft_produces_deep_link(self):
        from services.channels.whatsapp_readiness import draft_whatsapp
        result = draft_whatsapp("דוד", "0501234567", "הי דוד")
        self.assertIn("wa.me", result.deep_link)
        self.assertIn("972", result.deep_link)

    def test_draft_normalizes_phone(self):
        from services.channels.whatsapp_readiness import draft_whatsapp
        r1 = draft_whatsapp("טסט", "0501234567", "msg")
        self.assertIn("+972501234567", r1.deep_link)

    def test_no_phone_still_returns_result(self):
        from services.channels.whatsapp_readiness import draft_whatsapp
        result = draft_whatsapp("ליד", "", "הודעה")
        self.assertEqual(result.channel, "whatsapp")
        self.assertIsNotNone(result.draft)


class TestEmailChannel(unittest.TestCase):

    def test_draft_email_readiness_status_without_smtp(self):
        from services.channels.email_channel import draft_email
        result = draft_email("שרה", "sara@example.com", "גוף", "נושא")
        self.assertIn(result.status.value, ("readiness", "active"))
        self.assertEqual(result.draft, "גוף")

    def test_draft_email_includes_blocker_when_no_smtp(self):
        from services.channels.email_channel import draft_email
        result = draft_email("שרה", "sara@example.com", "גוף", "נושא")
        if result.status.value == "readiness":
            self.assertIn("blocker", result.meta)


class TestLinkedInReadiness(unittest.TestCase):

    def test_draft_adds_personalization(self):
        from services.channels.linkedin_readiness import draft_linkedin_message
        result = draft_linkedin_message("ראובן", "", "רוצה לשוחח?")
        self.assertIn("ראובן", result.draft)

    def test_draft_includes_compliance_note(self):
        from services.channels.linkedin_readiness import draft_linkedin_message
        result = draft_linkedin_message("ראובן", "https://li.com/in/r", "הי")
        self.assertIn("ציות", result.manual_instructions)


class TestChannelAPI(unittest.TestCase):

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def test_all_statuses_endpoint(self):
        r = _client().get("/api/channels/status", headers=_headers())
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("success"))
        channels = d.get("data", {}).get("channels") or []
        self.assertGreater(len(channels), 3)

    def test_single_channel_status(self):
        r = _client().get("/api/channels/status/whatsapp", headers=_headers())
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d.get("data", {}).get("channel"), "whatsapp")

    def test_draft_endpoint_returns_result(self):
        r = _client().post("/api/channels/draft",
                           json={"channel": "whatsapp",
                                 "lead": {"name": "דוד", "phone": "0501234567"},
                                 "message": "שלום דוד"},
                           headers=_headers())
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("success"))
        draft = d.get("data", {}).get("draft") or d.get("data", {}).get("copy_text", "")
        self.assertIn("דוד", draft)

    def test_manual_workflow_endpoint(self):
        r = _client().post("/api/channels/manual",
                           json={"channel": "email",
                                 "lead_name": "שרה",
                                 "contact": "sara@test.com",
                                 "message": "גוף המייל",
                                 "subject": "נושא"},
                           headers=_headers())
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("success"))

    def test_select_channel_endpoint(self):
        r = _client().post("/api/channels/select",
                           json={"lead": {"name": "טסט", "phone": "0501111111"}},
                           headers=_headers())
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIsNotNone(d.get("data", {}).get("channel"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
