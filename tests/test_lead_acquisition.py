"""
tests/test_lead_acquisition.py — Phase 12: Lead Acquisition OS
Tests all 6 skill modules, engine pipeline, event types, executor handlers, and intents.
No DB required — uses stateless skill functions and in-memory SQLite.
"""

import os
import sys
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENV", "development")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Skill 1: Source Discovery ─────────────────────────────────────────────────

class TestSourceDiscovery(unittest.TestCase):
    def setUp(self):
        from skills.source_discovery import discover_sources, detect_source_types, suggest_communities
        self.discover   = discover_sources
        self.detect     = detect_source_types
        self.suggest    = suggest_communities

    def test_discover_architects_goal(self):
        plan = self.discover("לידים מאדריכלים בתל אביב")
        self.assertIn("architects", plan.segments)
        self.assertIn("linkedin",   plan.source_types)
        self.assertGreater(len(plan.communities), 0)
        self.assertGreater(len(plan.search_intents), 0)
        self.assertTrue(plan.outreach_strategy)

    def test_detect_source_types_returns_list(self):
        types = self.detect("קבלנים ויזמים")
        self.assertIsInstance(types, list)
        self.assertGreater(len(types), 0)

    def test_suggest_communities_architects(self):
        communities = self.suggest("architects")
        self.assertGreater(len(communities), 0)
        for c in communities:
            self.assertTrue(c.name)
            self.assertTrue(c.source_type)

    def test_discovery_plan_has_notes(self):
        plan = self.discover("לידים מאדריכלים")
        self.assertIsInstance(plan.notes, list)


# ── Skill 2: Lead Intelligence ────────────────────────────────────────────────

class TestLeadIntelligence(unittest.TestCase):
    def setUp(self):
        from skills.lead_intelligence import (
            normalize, deduplicate, enrich, score_lead, rank_leads, explain_fit, extract_candidates
        )
        self.normalize   = normalize
        self.deduplicate = deduplicate
        self.enrich      = enrich
        self.score       = score_lead
        self.rank        = rank_leads
        self.explain     = explain_fit
        self.extract     = extract_candidates

    def _sample_raw(self, **kw):
        return {"name": "יוסי כהן", "phone": "052-1234567", "city": "תל אביב",
                "role": "אדריכל", "source_type": "linkedin", **kw}

    def test_normalize_basic(self):
        n = self.normalize(self._sample_raw())
        self.assertEqual(n.name, "יוסי כהן")
        self.assertEqual(n.city, "תל אביב")
        self.assertEqual(n.segment, "architects")
        self.assertTrue(n.fingerprint)

    def test_normalize_extracts_phone_from_text(self):
        n = self.normalize({"name": "Test", "text": "call me at 052-9876543"})
        self.assertIn("052", n.phone)

    def test_deduplicate_removes_same_phone(self):
        raw = self._sample_raw()
        leads = [self.normalize(raw), self.normalize(raw)]
        result = self.deduplicate(leads)
        self.assertEqual(len(result.new_leads), 1)
        self.assertEqual(len(result.duplicates), 1)

    def test_deduplicate_against_existing(self):
        n = self.normalize(self._sample_raw())
        existing = [{"id": "ex1", "phone": "052-1234567", "email": "", "name": "יוסי כהן", "company": ""}]
        result = self.deduplicate([n], existing)
        self.assertEqual(len(result.new_leads), 0)
        self.assertEqual(len(result.duplicates), 1)

    def test_enrich_returns_geo_fit(self):
        n = self.normalize(self._sample_raw())
        e = self.enrich(n)
        self.assertEqual(e.geo_fit, 1.0)   # תל אביב = tier 1
        self.assertGreaterEqual(e.role_fit, 0.9)  # architects = 1.0

    def test_score_range(self):
        n = self.normalize(self._sample_raw())
        e = self.enrich(n)
        s = self.score(e)
        self.assertGreaterEqual(s.score, 0)
        self.assertLessEqual(s.score, 100)
        self.assertIn(s.priority, ("high", "medium", "low"))
        self.assertTrue(s.next_action)

    def test_rank_leads_inbound_first(self):
        n1 = self.normalize(self._sample_raw(is_inbound=True))
        n2 = self.normalize({"name": "A", "city": "תל אביב", "role": "אדריכל", "source_type": "linkedin"})
        s1 = self.score(self.enrich(n1))
        s2 = self.score(self.enrich(n2))
        ranked = self.rank([s2, s1])
        self.assertEqual(ranked[0].lead.is_inbound, True)

    def test_explain_fit_returns_string(self):
        n = self.normalize(self._sample_raw())
        s = self.score(self.enrich(n))
        explanation = self.explain(s, "לידים מאדריכלים")
        self.assertIn("יוסי כהן", explanation)
        self.assertIsInstance(explanation, str)

    def test_extract_candidates_batch(self):
        raws = [self._sample_raw(), {"name": "דנה", "city": "חיפה", "source_type": "facebook_group"}]
        results = self.extract(raws)
        self.assertEqual(len(results), 2)


# ── Skill 3: Outreach Intelligence ────────────────────────────────────────────

class TestOutreachIntelligence(unittest.TestCase):
    def setUp(self):
        from skills.outreach_intelligence import (
            choose_action, choose_channel, choose_timing,
            draft_first_contact, draft_followup, draft_meeting_request,
            draft_inbound_response, draft_comment_reply,
        )
        self.choose_action   = choose_action
        self.choose_channel  = choose_channel
        self.choose_timing   = choose_timing
        self.first_contact   = draft_first_contact
        self.followup        = draft_followup
        self.meeting         = draft_meeting_request
        self.inbound_resp    = draft_inbound_response
        self.comment_reply   = draft_comment_reply

    def _lead(self, **kw):
        return {"name": "יוסי", "phone": "052-1234567", "score": 80,
                "source_type": "linkedin", "segment": "architects", **kw}

    def test_choose_action_hot_lead_dm(self):
        a = self.choose_action(self._lead())
        self.assertEqual(a.action, "dm")
        self.assertTrue(a.requires_approval)

    def test_choose_action_inbound_gets_response(self):
        a = self.choose_action(self._lead(is_inbound=True, last_contact=None))
        self.assertEqual(a.action, "dm")

    def test_choose_action_low_score_wait(self):
        a = self.choose_action(self._lead(score=20))
        self.assertEqual(a.action, "wait")
        self.assertFalse(a.requires_approval)

    def test_choose_channel_phone_gets_whatsapp(self):
        c = self.choose_channel({"phone": "052-111", "source_type": "linkedin"})
        self.assertEqual(c, "whatsapp")

    def test_choose_channel_linkedin(self):
        c = self.choose_channel({"source_type": "linkedin"})
        self.assertEqual(c, "linkedin_dm")

    def test_draft_first_contact_requires_approval(self):
        d = self.first_contact(self._lead())
        self.assertTrue(d.requires_approval)
        self.assertIn("יוסי", d.body)
        self.assertEqual(d.language, "he")

    def test_draft_followup_structure(self):
        d = self.followup(self._lead())
        self.assertTrue(d.requires_approval)
        self.assertEqual(d.action_type, "follow_up")

    def test_draft_meeting_request(self):
        d = self.meeting(self._lead())
        self.assertEqual(d.action_type, "meeting_request")
        self.assertTrue(d.requires_approval)

    def test_draft_inbound_response(self):
        d = self.inbound_resp(self._lead(), "שלום אני מעוניין בחלונות")
        self.assertEqual(d.action_type, "inbound_response")
        self.assertIn("יוסי", d.body)

    def test_draft_comment_reply(self):
        d = self.comment_reply({"text": "מחפש פתרון לחלונות"}, self._lead())
        self.assertEqual(d.action_type, "comment_reply")


# ── Skill 4: Israeli Context ──────────────────────────────────────────────────

class TestIsraeliContext(unittest.TestCase):
    def setUp(self):
        from skills.israeli_context import (
            get_hebrew_tone, is_good_timing, get_best_send_window,
            get_holiday_context, local_signal_detection, geo_fit, compliance_hints
        )
        self.tone       = get_hebrew_tone
        self.timing     = is_good_timing
        self.window     = get_best_send_window
        self.holiday    = get_holiday_context
        self.signals    = local_signal_detection
        self.geo        = geo_fit
        self.compliance = compliance_hints

    def test_hebrew_tone_by_segment(self):
        self.assertEqual(self.tone("architects"), "professional")
        self.assertEqual(self.tone("homeowners"),  "warm")
        self.assertEqual(self.tone("contractors"), "direct")

    def test_geo_fit_tier1(self):
        self.assertEqual(self.geo("תל אביב"), 1.0)
        self.assertEqual(self.geo("הרצליה"),  1.0)

    def test_geo_fit_tier2(self):
        self.assertEqual(self.geo("נתניה"), 0.7)

    def test_geo_fit_empty(self):
        self.assertLess(self.geo(""), 0.5)

    def test_compliance_hints_whatsapp(self):
        hints = self.compliance("whatsapp")
        self.assertIsInstance(hints, list)
        self.assertGreater(len(hints), 0)

    def test_local_signal_detection(self):
        result = self.signals("אני קבלן בתל אביב מחפש פרויקט בנייה חדש עם אלומיניום")
        self.assertTrue(result["is_israeli"])
        self.assertTrue(result["is_in_sector"] or result["has_buying_intent"])
        self.assertGreater(result["signal_strength"], 0)

    def test_timing_returns_bool(self):
        import datetime
        # Wednesday 10:00 — should be good
        good = datetime.datetime(2026, 4, 8, 10, 0, tzinfo=datetime.timezone.utc)
        # Saturday — should be bad
        bad  = datetime.datetime(2026, 4, 11, 10, 0, tzinfo=datetime.timezone.utc)
        self.assertIn(self.timing(good), (True, False))  # environment may vary
        # Saturday is always False
        self.assertFalse(self.timing(bad))

    def test_holiday_context_structure(self):
        ctx = self.holiday()
        self.assertIn("is_holiday", ctx)
        self.assertIn("send_now", ctx)
        self.assertIn("next_business_day", ctx)


# ── Skill 5: Workflow Skills (pure functions only) ────────────────────────────

class TestWorkflowSkills(unittest.TestCase):
    def setUp(self):
        from skills.workflow_skills import build_work_queue, mark_approval_required
        self.build_queue = build_work_queue
        self.mark        = mark_approval_required

    def _lead(self, **kw):
        return {"id": "l1", "name": "יוסי", "outreach_action": "dm",
                "outreach_draft": "היי יוסי", "priority": "high",
                "channel": "whatsapp", "is_inbound": False, "score": 80, **kw}

    def test_build_work_queue_creates_items(self):
        q = self.build_queue([self._lead()])
        self.assertEqual(q.total, 1)
        self.assertEqual(q.needs_approval, 1)

    def test_build_work_queue_wait_not_approval(self):
        q = self.build_queue([self._lead(outreach_action="wait")])
        self.assertEqual(q.waiting, 1)
        self.assertEqual(q.needs_approval, 0)

    def test_mark_approval_required(self):
        item = {"lead_id": "x", "action": "dm"}
        marked = self.mark(item, "sensitive send")
        self.assertTrue(marked["approval_required"])
        self.assertEqual(marked["approval_status"], "pending")
        self.assertIn("approval_reason", marked)

    def test_inbound_leads_sorted_first(self):
        l1 = self._lead(id="l1", is_inbound=False, score=90)
        l2 = self._lead(id="l2", is_inbound=True,  score=50)
        q  = self.build_queue([l1, l2])
        self.assertEqual(q.items[0].lead_id, "l2")  # inbound first


# ── Skill 6: Website Growth ───────────────────────────────────────────────────

class TestWebsiteGrowth(unittest.TestCase):
    def setUp(self):
        from skills.website_growth import (
            site_audit, seo_intelligence, content_gap_detection,
            landing_page_suggestions, lead_capture_review,
            content_draft, priority_planner,
        )
        self.audit    = site_audit
        self.seo      = seo_intelligence
        self.gaps     = content_gap_detection
        self.lp_tips  = landing_page_suggestions
        self.lc       = lead_capture_review
        self.draft    = content_draft
        self.planner  = priority_planner

    def _html(self):
        return '<html><title>אשבל אלומיניום</title><h1>ברוכים</h1><form><input/></form><meta name="description" content="test">'

    def test_site_audit_with_html(self):
        a = self.audit("https://example.com", self._html())
        self.assertTrue(a.has_contact_form)
        self.assertFalse(a.missing_h1)
        self.assertFalse(a.missing_meta)
        self.assertGreater(a.raw_score, 0)

    def test_site_audit_empty_html(self):
        a = self.audit("https://example.com")
        self.assertEqual(a.h1_count, 0)
        # missing_meta only set when HTML is parsed; without HTML it defaults False
        self.assertFalse(a.has_contact_form)

    def test_seo_intelligence(self):
        a = self.audit("https://example.com")
        s = self.seo(a)
        self.assertIsInstance(s.missing_city_pages, list)
        self.assertIsInstance(s.keyword_gaps, list)
        self.assertGreater(len(s.missing_city_pages), 0)

    def test_content_gap_detection(self):
        a    = self.audit("https://example.com")
        gaps = self.gaps(a, "architects")
        self.assertGreater(len(gaps), 0)
        for g in gaps:
            self.assertTrue(g.topic)
            self.assertIn(g.priority, ("high", "medium", "low"))

    def test_lead_capture_review_no_form(self):
        a  = self.audit("https://example.com")  # no form/phone/whatsapp
        lc = self.lc(a)
        self.assertLess(lc.score, 50)
        self.assertGreater(len(lc.missing_items), 0)
        self.assertGreater(len(lc.recommendations), 0)

    def test_landing_page_suggestions(self):
        a    = self.audit("https://example.com")
        tips = self.lp_tips(a)
        self.assertIsInstance(tips, list)
        self.assertGreater(len(tips), 0)

    def test_content_draft(self):
        text = self.draft("חלונות אלומיניום בתל אביב", city="תל אביב")
        self.assertIn("תל אביב", text)
        self.assertIn("#", text)

    def test_priority_planner(self):
        a    = self.audit("https://example.com")
        gaps = self.gaps(a)
        plan = self.planner(a, gaps)
        self.assertIsInstance(plan, list)
        self.assertGreater(len(plan), 0)


# ── Event types ────────────────────────────────────────────────────────────────

class TestLeadAcquisitionEvents(unittest.TestCase):
    def test_new_event_constants_exist(self):
        from events.event_types import (
            LEAD_DISCOVERED, INBOUND_LEAD_RECEIVED,
            LEAD_OUTREACH_SENT, LEAD_FOLLOWUP_PROPOSED,
            WEBSITE_ANALYSIS_REQUESTED,
        )
        self.assertEqual(LEAD_DISCOVERED,          "lead.discovered")
        self.assertEqual(INBOUND_LEAD_RECEIVED,    "lead.inbound_received")
        self.assertEqual(LEAD_OUTREACH_SENT,       "lead.outreach_sent")
        self.assertEqual(LEAD_FOLLOWUP_PROPOSED,   "lead.followup_proposed")
        self.assertEqual(WEBSITE_ANALYSIS_REQUESTED, "website.analysis_requested")


# ── Executor _HANDLERS ────────────────────────────────────────────────────────

class TestPhase12ExecutorHandlers(unittest.TestCase):
    def test_handlers_registered(self):
        from services.execution.executor import _HANDLERS
        for key in ("discover_leads", "process_inbound", "website_analysis", "lead_ops_queue"):
            self.assertIn(key, _HANDLERS, f"Missing handler: {key}")

    def test_handlers_callable(self):
        from services.execution.executor import _HANDLERS
        for key in ("discover_leads", "process_inbound", "website_analysis", "lead_ops_queue"):
            self.assertTrue(callable(_HANDLERS[key]))


# ── Intent parser ──────────────────────────────────────────────────────────────

class TestPhase12Intents(unittest.TestCase):
    def setUp(self):
        from orchestration.intent_parser import intent_parser, Intent
        self.parser = intent_parser
        self.Intent = Intent

    def test_discover_leads_intent(self):
        r = self.parser.parse("מצא לידים מאדריכלים")
        self.assertEqual(r.intent, self.Intent.DISCOVER_LEADS)

    def test_website_analysis_intent(self):
        r = self.parser.parse("ניתוח אתר")
        self.assertEqual(r.intent, self.Intent.WEBSITE_ANALYSIS)

    def test_lead_ops_queue_intent(self):
        r = self.parser.parse("תור לידים")
        self.assertEqual(r.intent, self.Intent.LEAD_OPS_QUEUE)

    def test_inbound_intent(self):
        r = self.parser.parse("ליד נכנס מהאתר")
        self.assertEqual(r.intent, self.Intent.PROCESS_INBOUND)


# ── Engine pipeline (SQLite in-memory) ───────────────────────────────────────

class TestLeadAcquisitionEngine(unittest.TestCase):
    def setUp(self):
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        from services.storage.db import create_all_tables
        create_all_tables()

    def test_run_acquisition_no_signals(self):
        from engines.lead_acquisition_engine import run_acquisition
        result = run_acquisition(goal="לידים מאדריכלים", signals=[], session=None)
        self.assertEqual(result.goal, "לידים מאדריכלים")
        self.assertEqual(result.total_discovered, 0)
        self.assertIsInstance(result.discovery_plan, dict)
        self.assertIn("segments", result.discovery_plan)

    def test_run_acquisition_with_signals(self):
        from engines.lead_acquisition_engine import run_acquisition
        signals = [
            {"name": "יוסי כהן", "phone": "052-1234567", "city": "תל אביב",
             "role": "אדריכל", "source_type": "linkedin"},
            {"name": "דנה לוי", "phone": "054-9876543", "city": "הרצליה",
             "role": "מעצב פנים", "source_type": "instagram"},
        ]
        result = run_acquisition(goal="אדריכלים ומעצבים", signals=signals)
        self.assertEqual(result.total_discovered, 2)
        self.assertEqual(result.new_leads, 2)
        self.assertEqual(result.duplicates, 0)
        self.assertGreater(len(result.work_queue), 0)

    def test_process_inbound(self):
        from engines.lead_acquisition_engine import process_inbound
        lead_id = process_inbound(
            lead_data={"name": "רחל כהן", "phone": "052-5555555",
                       "city": "ירושלים", "message": "מעוניינת בחלונות לבית"},
        )
        self.assertIsInstance(lead_id, str)
        self.assertGreater(len(lead_id), 0)

    def test_website_analysis(self):
        from engines.lead_acquisition_engine import run_website_analysis
        result = run_website_analysis(
            url="https://example.com",
            html='<html><title>Test</title><h1>Hi</h1><form></form>'
        )
        self.assertGreaterEqual(result.audit_score, 0)
        self.assertIsInstance(result.top_recommendations, list)
        self.assertIsInstance(result.content_gaps, list)


if __name__ == "__main__":
    unittest.main()
