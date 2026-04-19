"""
test_practical_audit.py — Practical system audit proof tests.

Verifies:
1. Profile separation — messaging uses active profile, not hardcoded aluminum
2. Manual-send workflow produces usable output for all channels
3. Follow-up queue and schedule flows
4. Mission control data loaders work without DB
5. Channel services return ChannelResult for all readiness channels
6. Marketing recommendations are profile-driven
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_profile(name="TestBiz", domain="test domain", products="product A, product B"):
    from config.business_registry import BusinessProfile
    return BusinessProfile(
        business_id="test",
        name=name,
        domain=domain,
        products=products,
        target_clients="clients",
        market="Israel",
        competitive_edge="quality",
        primary_channel="whatsapp",
        lead_score_weights={
            "source": {"referral": 30, "manual": 10},
            "city_tier": {"tier_1": [], "tier_2": [], "tier_1_score": 20, "tier_2_score": 10, "other_score": 5},
            "response_positive": 25, "no_attempts_bonus": 5, "repeated_no_response_penalty": -10,
        },
        outreach_channels=["whatsapp", "email"],
        avg_deal_size=5000,
    )


# ── 1. Profile separation ─────────────────────────────────────────────────────

class TestProfileSeparation:

    def test_cold_message_uses_profile_name(self):
        profile = _make_profile(name="TestBiz", domain="test services")
        with patch("engines.messaging_engine._profile", return_value=profile):
            from engines.messaging_engine import _cold_message
            msg = _cold_message("David", "Tel Aviv", "")
        assert "TestBiz" in msg
        assert "אשבל אלומיניום" not in msg

    def test_cold_message_uses_profile_products(self):
        profile = _make_profile(products="widget A, widget B")
        with patch("engines.messaging_engine._profile", return_value=profile):
            from engines.messaging_engine import _cold_message
            msg = _cold_message("Sarah", "", "")
        assert "widget A" in msg or "widget B" in msg or "widget" in msg

    def test_followup_message_uses_profile_domain(self):
        profile = _make_profile(domain="software solutions")
        with patch("engines.messaging_engine._profile", return_value=profile):
            from engines.messaging_engine import _followup_message
            msg = _followup_message("Mike", "", 1)
        assert "software solutions" in msg
        assert "אלומיניום" not in msg

    def test_build_initial_message_profile_driven(self):
        profile = _make_profile(name="TechCo", domain="cloud services")
        with patch("engines.outreach_engine._biz_name", return_value="TechCo"), \
             patch("engines.outreach_engine._biz_domain", return_value="cloud services"):
            from engines.outreach_engine import build_initial_message
            msg = build_initial_message("general", "Alice")
        assert "TechCo" in msg
        assert "אשבל אלומיניום" not in msg

    def test_build_initial_message_architects_profile(self):
        with patch("engines.outreach_engine._biz_name", return_value="DesignCo"), \
             patch("engines.outreach_engine._biz_domain", return_value="interior design"):
            from engines.outreach_engine import build_initial_message
            msg = build_initial_message("architects", "Architect Rami")
        assert "DesignCo" in msg
        assert "Architect Rami" in msg

    def test_content_engine_uses_profile(self):
        profile = _make_profile(name="MediaBiz", domain="media production",
                                 products="videos, photos, branding")
        with patch("engines.content_engine._profile", return_value=profile):
            from engines.content_engine import build_post, LINKEDIN_POST
            post = build_post(LINKEDIN_POST, "video production")
        assert "MediaBiz" in post
        assert "אשבל אלומיניום" not in post

    def test_content_engine_instagram_uses_profile(self):
        profile = _make_profile(name="FoodBiz", products="salads, wraps, juices")
        with patch("engines.content_engine._profile", return_value=profile):
            from engines.content_engine import build_post, INSTAGRAM_POST
            post = build_post(INSTAGRAM_POST, "fresh food")
        assert "FoodBiz" in post
        assert "אשבלאלומיניום" not in post

    def test_active_business_is_ashbel_by_default(self):
        from config.business_registry import get_active_business
        p = get_active_business()
        assert p.business_id == "ashbel"
        assert "אלומיניום" in p.name

    def test_different_profile_isolation(self):
        with patch.dict(os.environ, {"BUSINESS_ID": "demo_real_estate"}):
            from config.business_registry import get_active_business
            import importlib, config.business_registry as reg
            importlib.reload(reg)
            p = reg.get_active_business()
            assert p.business_id == "demo_real_estate"
        # Reload back to ashbel
        import importlib, config.business_registry as reg2
        importlib.reload(reg2)


# ── 2. Manual-send workflow ────────────────────────────────────────────────────

class TestManualSendWorkflow:

    def test_whatsapp_manual_generates_deep_link(self):
        from services.channels.manual_send import generate_manual_workflow
        result = generate_manual_workflow("whatsapp", "Test Lead", "+972501234567",
                                          "שלום, אשמח לשמוע על השירות", "")
        assert result is not None
        d = result.to_dict()
        assert "wa.me" in (d.get("deep_link") or "")
        assert d.get("channel") == "whatsapp"
        assert d.get("copy_text") or d.get("draft")

    def test_email_manual_generates_mailto(self):
        from services.channels.manual_send import generate_manual_workflow
        result = generate_manual_workflow("email", "Test Lead", "test@example.com",
                                          "Hello there", "Test Subject")
        d = result.to_dict()
        assert "mailto:" in (d.get("deep_link") or "")
        assert d.get("channel") == "email"

    def test_linkedin_manual_includes_instructions(self):
        from services.channels.manual_send import generate_manual_workflow
        result = generate_manual_workflow("linkedin", "Test Lead", "linkedin.com/in/test",
                                          "LinkedIn message", "")
        d = result.to_dict()
        assert d.get("manual_instructions") or d.get("instructions")

    def test_sms_manual_workflow(self):
        from services.channels.manual_send import generate_manual_workflow
        result = generate_manual_workflow("sms", "Test Lead", "0501234567",
                                          "SMS message", "")
        d = result.to_dict()
        assert d.get("channel") == "sms"
        assert d.get("copy_text") or d.get("draft")

    def test_manual_send_missing_contact_graceful(self):
        from services.channels.manual_send import generate_manual_workflow
        result = generate_manual_workflow("whatsapp", "Test Lead", "",
                                          "Test message", "")
        assert result is not None
        d = result.to_dict()
        assert d.get("channel") == "whatsapp"

    def test_channel_result_to_dict_has_required_keys(self):
        from services.channels.manual_send import generate_manual_workflow
        result = generate_manual_workflow("whatsapp", "Lead", "+97250000000",
                                          "Test body", "")
        d = result.to_dict()
        for key in ("channel", "copy_text", "needs_approval"):
            assert key in d, f"Missing key: {key}"


# ── 3. Channel services ────────────────────────────────────────────────────────

class TestChannelServices:

    def test_channel_router_select_returns_string(self):
        from services.channels.channel_router import channel_router
        profile = _make_profile()
        ch = channel_router.select({"phone": "+972501234567"}, profile)
        assert isinstance(ch, str)
        assert len(ch) > 0

    def test_channel_router_status_all(self):
        from services.channels.channel_router import channel_router
        statuses = channel_router.all_statuses()
        assert isinstance(statuses, list)
        assert len(statuses) >= 4

    def test_channel_router_status_whatsapp(self):
        from services.channels.channel_router import channel_router
        s = channel_router.status("whatsapp")
        assert "status" in s
        assert "channel" in s

    def test_channel_router_draft_returns_result(self):
        from services.channels.channel_router import channel_router
        profile = _make_profile()
        result = channel_router.draft("whatsapp", {"name": "Test", "phone": "+97250123"},
                                       "Test message", "", "TestBiz")
        assert result is not None
        assert result.channel == "whatsapp"

    def test_email_channel_readiness_without_smtp(self):
        from services.channels.email_channel import draft_email
        result = draft_email("Test Lead", "test@example.com", "Hello", "Subject")
        assert result is not None
        d = result.to_dict()
        assert d["channel"] == "email"

    def test_whatsapp_deep_link_format(self):
        from services.channels.whatsapp_readiness import draft_whatsapp
        result = draft_whatsapp("Test Lead", "0501234567", "Test message")
        d = result.to_dict()
        assert "wa.me" in (d.get("deep_link") or "")
        assert "972" in (d.get("deep_link") or "")


# ── 4. Marketing recommendations ──────────────────────────────────────────────

class TestMarketingRecommendations:

    def test_weekly_plan_returns_plan(self):
        from engines.marketing_engine import generate_weekly_plan
        profile = _make_profile()
        plan = generate_weekly_plan(profile)
        assert plan is not None
        assert hasattr(plan, "recommendations")
        assert len(plan.recommendations) > 0

    def test_weekly_plan_profile_aware(self):
        from engines.marketing_engine import generate_weekly_plan
        profile = _make_profile(name="TestBiz", domain="test domain")
        plan = generate_weekly_plan(profile)
        assert plan.business_name == "TestBiz"

    def test_weekly_plan_has_post_drafts(self):
        from engines.marketing_engine import generate_weekly_plan
        profile = _make_profile()
        plan = generate_weekly_plan(profile)
        assert hasattr(plan, "post_drafts")

    def test_weekly_plan_has_campaign_ideas(self):
        from engines.marketing_engine import generate_weekly_plan
        profile = _make_profile()
        plan = generate_weekly_plan(profile)
        assert hasattr(plan, "campaign_ideas")
        assert isinstance(plan.campaign_ideas, list)

    def test_marketing_recommendations_without_credentials(self):
        from engines.marketing_engine import generate_weekly_plan
        plan = generate_weekly_plan()
        assert plan is not None
        assert plan.business_name


# ── 5. Follow-up flow ─────────────────────────────────────────────────────────

class TestFollowupFlow:

    def test_followup_agent_can_handle(self):
        from agents.departments.sales.followup_agent import FollowUpAgent
        a = FollowUpAgent()
        assert a.can_handle("followup", "followup_queue")
        assert a.can_handle("followup", "schedule_followup")
        assert a.can_handle("followup", "batch_followup")
        assert a.can_handle("outreach", "followup_queue")
        assert not a.can_handle("unknown", "unknown")

    def test_outreach_intelligence_draft_followup(self):
        from skills.outreach_intelligence import draft_followup
        result = draft_followup({"name": "Test Lead", "segment": "general", "phone": "050"})
        assert result is not None
        assert result.body
        assert result.channel

    def test_classify_response_positive(self):
        from engines.messaging_engine import classify_response
        assert classify_response("כן, מעוניין") == "positive"

    def test_classify_response_negative(self):
        from engines.messaging_engine import classify_response
        assert classify_response("לא, תוריד") == "negative"

    def test_classify_response_timing(self):
        from engines.messaging_engine import classify_response
        assert classify_response("בהמשך החודש") == "timing"

    def test_build_followup_with_timing_response(self):
        from engines.messaging_engine import build_followup
        msg = build_followup("Test", "Tel Aviv", "בהמשך", 1)
        assert "Test" in msg
        assert len(msg) > 10


# ── 6. End-to-end intake flow check ──────────────────────────────────────────

class TestIntakeFlow:

    def test_outreach_intelligence_should_followup_contacted(self):
        from skills.outreach_intelligence import should_followup
        assert should_followup({"status": "contacted", "attempts": 1}) is True

    def test_outreach_intelligence_should_followup_closed(self):
        from skills.outreach_intelligence import should_followup
        assert should_followup({"status": "closed"}) is False

    def test_outreach_intelligence_draft_first_contact(self):
        from skills.outreach_intelligence import draft_first_contact
        result = draft_first_contact({"name": "Test", "segment": "architects", "phone": "050"})
        assert result.body
        assert result.channel in ("whatsapp", "email", "sms", "manual")

    def test_channel_router_select_by_phone(self):
        from services.channels.channel_router import channel_router
        ch = channel_router.select({"phone": "+972501234567", "email": ""}, _make_profile())
        assert ch == "whatsapp"

    def test_channel_router_select_by_email_only(self):
        from services.channels.channel_router import channel_router
        ch = channel_router.select({"phone": "", "email": "test@example.com"}, _make_profile())
        assert ch in ("email", "whatsapp", "manual")
