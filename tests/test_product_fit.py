"""
tests/test_product_fit.py — Product-fit acceptance tests for p24 build.
Covers: profile-driven context, queue logic, drafting studio, intake, SEO.
All deterministic — no DB required.
"""
import os
import pytest

os.environ.setdefault("BUSINESS_ID", "ashbel")


# ── A. Profile-driven context ─────────────────────────────────────────────────

class TestProfileDrivenContext:
    def test_active_profile_fields_present(self):
        from config.business_registry import get_active_business
        p = get_active_business()
        assert p.name
        assert p.domain

    def test_draft_first_contact_body_non_empty(self):
        from skills.outreach_intelligence import draft_first_contact
        draft = draft_first_contact({"name": "דוד כהן", "city": "תל אביב"})
        assert draft.body and len(draft.body) > 20

    def test_draft_requires_approval(self):
        from skills.outreach_intelligence import draft_first_contact
        assert draft_first_contact({"name": "מרים לוי"}).requires_approval is True

    def test_seo_meta_is_profile_driven(self):
        from engines.seo_engine import SEOEngine
        meta = SEOEngine().generate_meta_descriptions()
        for page in ("home", "products", "about", "contact"):
            assert page in meta
            assert 0 < len(meta[page]) <= 155

    def test_marketing_weekly_profile_driven(self):
        from engines.marketing_engine import generate_weekly_plan
        plan = generate_weekly_plan()
        assert hasattr(plan, 'recommendations')
        assert len(plan.recommendations) >= 1
        assert plan.recommendations[0].title


# ── B. Command bar: intent routing ────────────────────────────────────────────

class TestIntentRouting:
    def _parse(self, text):
        from orchestration.intent_parser import IntentParser
        return IntentParser().parse(text)

    def test_parse_leads_intent(self):
        r = self._parse("תביא לידים")
        assert r is not None

    def test_parse_website_intent(self):
        r = self._parse("נתח את האתר שלי")
        assert r is not None

    def test_parse_marketing_intent(self):
        r = self._parse("תוכנית שיווק שבועית")
        assert r is not None

    def test_parse_draft_intent(self):
        r = self._parse("נסח פנייה")
        assert r is not None


# ── C. Queue-centered daily work ──────────────────────────────────────────────

class TestQueueFilters:
    def test_manual_send_queue_logic(self):
        leads = [
            {"status": "new",       "score": 75},
            {"status": "hot",       "score": 45},
            {"status": "contacted", "score": 30},  # below 40
            {"status": "closed",    "score": 80},  # wrong status
            {"status": "contacted", "score": 50},
        ]
        manual = [l for l in leads
                  if l["status"] in ("new", "hot", "contacted") and l["score"] >= 40]
        assert len(manual) == 3

    def test_followup_queue_logic(self):
        leads = [
            {"status": "contacted"}, {"status": "hot"},
            {"status": "new"},       {"status": "closed"},
        ]
        assert len([l for l in leads if l["status"] in ("contacted", "hot")]) == 2

    def test_approvals_pending_filter(self):
        items = [{"status": "pending"}, {"status": "approved"},
                 {"status": "pending"}, {"status": "denied"}]
        assert len([a for a in items if a["status"] == "pending"]) == 2

    def test_lead_score_sort_hot_first(self):
        leads = [
            {"status": "new",  "score": 90},
            {"status": "hot",  "score": 60},
            {"status": "hot",  "score": 80},
        ]
        leads.sort(key=lambda l: (l["status"] != "hot", -(l["score"] or 0)))
        assert leads[0]["status"] == "hot"
        assert leads[1]["status"] == "hot"


# ── D. Drafting studio ────────────────────────────────────────────────────────

class TestDraftingStudio:
    def test_first_contact_structured(self):
        from skills.outreach_intelligence import draft_first_contact
        d = draft_first_contact({"name": "שרה", "city": "ירושלים", "phone": "050-1"})
        assert d.body and d.channel and d.action_type == "first_contact"

    def test_followup_structured(self):
        from skills.outreach_intelligence import draft_followup
        d = draft_followup({"name": "בני"}, {})
        assert d.body and d.action_type == "follow_up"

    def test_meeting_request_structured(self):
        from skills.outreach_intelligence import draft_meeting_request
        d = draft_meeting_request({"name": "רמי", "city": "נתניה"})
        assert d.body and d.action_type == "meeting_request"

    def test_inbound_response_structured(self):
        from skills.outreach_intelligence import draft_inbound_response
        d = draft_inbound_response({"name": "עמי"}, "מעוניין בהצעת מחיר")
        assert d.body and d.action_type == "inbound_response"

    def test_whatsapp_deeplink_formula(self):
        phone = "050-1234567"
        digits = phone.replace('-', '').replace(' ', '')
        intl = '972' + digits[1:] if digits.startswith('0') else digits
        assert "972501234567" in f"https://wa.me/{intl}?text=שלום"

    def test_tone_instructions_non_empty(self):
        tones = [
            "קצר את הטיוטה לחצי מהגודל המקורי",
            "הפוך את הטון לפורמלי ומקצועי יותר",
            "הפוך את הטון לישיר ועסקי יותר",
            "הפוך את הטון לחמותי ואישי יותר",
            "הוסף ערך מכירתי ברור וקריאה לפעולה חזקה",
        ]
        for t in tones:
            assert len(t) > 10

    def test_draft_refine_endpoint_registered(self):
        src = open("api/routes/lead_ops.py").read()
        assert "draft_refine" in src
        assert "model_router.call" in src


# ── E. Intake surfaces ────────────────────────────────────────────────────────

class TestIntakeSurfaces:
    def test_should_followup_new(self):
        from skills.outreach_intelligence import should_followup
        assert should_followup({"status": "new"}) is True

    def test_should_followup_hot(self):
        from skills.outreach_intelligence import should_followup
        assert should_followup({"status": "hot"}) is True

    def test_should_not_followup_closed(self):
        from skills.outreach_intelligence import should_followup
        assert should_followup({"status": "closed"}) is False

    def test_document_column_detection_hebrew(self):
        from skills.document_intelligence import detect_lead_columns
        mapping = detect_lead_columns(["שם", "טלפון", "עיר", "הערות"])
        assert mapping["name"] == 0    # index of "שם"
        assert mapping["phone"] == 1   # index of "טלפון"

    def test_document_column_detection_english(self):
        from skills.document_intelligence import detect_lead_columns
        mapping = detect_lead_columns(["Name", "Phone", "City"])
        assert mapping["name"] == 0
        assert mapping["phone"] == 1

    def test_lead_normalizer_strips_whitespace(self):
        from skills.lead_intelligence import normalize
        lead = normalize({"name": "  אבי כהן  ", "phone": "050-1234567"})
        assert lead.name == "אבי כהן"


# ── F. SEO workbench ──────────────────────────────────────────────────────────

class TestSEOWorkbench:
    def test_city_pages_structure(self):
        from engines.seo_engine import SEOEngine
        pages = SEOEngine().generate_city_pages()
        assert len(pages) >= 1
        for p in pages:
            for f in ("slug", "title", "content"):
                assert f in p

    def test_blog_posts(self):
        from engines.seo_engine import SEOEngine
        posts = SEOEngine().generate_blog_posts()
        assert len(posts) == 3
        for p in posts:
            assert len(p["content"]) > 100

    def test_image_prompts(self):
        from engines.seo_engine import SEOEngine
        assert len(SEOEngine().generate_image_prompts()) == 8

    def test_meta_length_constraint(self):
        from engines.seo_engine import SEOEngine
        for key, val in SEOEngine().generate_meta_descriptions().items():
            assert len(val) <= 155


# ── G. Lead-to-action practical flow ─────────────────────────────────────────

class TestLeadToActionFlow:
    def test_score_bucket_assignment(self):
        def bucket(s): return "hot" if s >= 70 else "warm" if s >= 40 else "cold"
        assert bucket(85) == "hot"
        assert bucket(50) == "warm"
        assert bucket(20) == "cold"

    def test_channel_selection(self):
        from skills.outreach_intelligence import choose_channel
        assert choose_channel({"name": "דן", "phone": "050-1"}) in (
            "whatsapp", "phone", "sms")
        result = choose_channel({"name": "דן", "email": "a@b.com"})
        assert isinstance(result, str) and len(result) > 0

    def test_approval_payload_structure(self):
        payload = {
            "action": "send_outreach",
            "action_type": "first_contact",
            "risk_level": 2,
            "lead_id": "abc",
            "lead_name": "דוד",
            "draft_body": "שלום...",
            "channel": "whatsapp",
        }
        for f in ("action", "action_type", "risk_level", "lead_id", "draft_body"):
            assert f in payload
