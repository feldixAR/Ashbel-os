"""
tests/test_marketing_engine.py — Marketing engine + SEO agent proof.

Proves:
  - generate_weekly_plan() returns MarketingPlan with recommendations + posts + ideas
  - plan is profile-aware (uses business name)
  - marketing/weekly API endpoint returns expected structure
  - SEOAgent handles seo_report, city_pages, blog_posts
  - business profile has new fields: site_url, site_keywords, top_offers
  - ChannelStrategyAgent routes correctly
  - MarketingStrategyAgent returns recommendations
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


class TestBusinessProfileExtended(unittest.TestCase):

    def test_active_profile_has_new_fields(self):
        from config.business_registry import get_active_business
        p = get_active_business()
        self.assertIsNotNone(p.site_url)
        self.assertIsInstance(p.site_keywords, list)
        self.assertIsInstance(p.top_offers, list)
        self.assertIsInstance(p.service_areas, list)
        self.assertIsInstance(p.seasonal_peaks, list)

    def test_ashbel_profile_has_seo_data(self):
        from config.business_registry import get_active_business
        p = get_active_business()
        self.assertGreater(len(p.site_keywords), 0)
        self.assertGreater(len(p.service_areas), 0)
        self.assertIn("אלומיניום", p.site_keywords[0])


class TestMarketingEngine(unittest.TestCase):

    def test_generate_weekly_plan_returns_plan(self):
        from engines.marketing_engine import generate_weekly_plan
        plan = generate_weekly_plan()
        self.assertIsNotNone(plan)
        self.assertGreater(len(plan.recommendations), 0)
        self.assertGreater(len(plan.campaign_ideas), 0)
        self.assertIsNotNone(plan.week_start)
        self.assertIsNotNone(plan.business_name)

    def test_recommendations_have_required_fields(self):
        from engines.marketing_engine import generate_weekly_plan
        plan = generate_weekly_plan()
        for rec in plan.recommendations:
            self.assertIsNotNone(rec.category)
            self.assertIsNotNone(rec.title)
            self.assertIsNotNone(rec.body)
            self.assertIsNotNone(rec.channel)

    def test_post_drafts_generated(self):
        from engines.marketing_engine import generate_weekly_plan
        plan = generate_weekly_plan()
        self.assertGreater(len(plan.post_drafts), 0)
        for post in plan.post_drafts:
            self.assertIn("platform", post)
            self.assertIn("caption", post)

    def test_plan_uses_profile_name(self):
        from engines.marketing_engine import generate_weekly_plan
        from config.business_registry import get_active_business
        profile = get_active_business()
        plan = generate_weekly_plan(profile)
        self.assertEqual(plan.business_name, profile.name)

    def test_marketing_report_is_string(self):
        from engines.marketing_engine import generate_marketing_report
        report = generate_marketing_report()
        self.assertIsInstance(report, str)
        self.assertGreater(len(report), 50)


class TestMarketingWeeklyAPI(unittest.TestCase):

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def test_marketing_weekly_endpoint(self):
        r = _client().get("/api/marketing/weekly", headers=_headers())
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("success"))
        data = d.get("data", {})
        self.assertIn("recommendations", data)
        self.assertIn("campaign_ideas", data)
        self.assertGreater(len(data.get("recommendations", [])), 0)


class TestSEOAgent(unittest.TestCase):

    def setUp(self):
        _app()

    def test_seo_agent_handles_seo_report(self):
        from agents.departments.executive.seo_agent import SEOAgent
        from orchestration.task_manager import task_manager
        agent = SEOAgent()
        self.assertTrue(agent.can_handle("seo", "seo_report"))
        task = task_manager.create_task(
            type="seo", action="seo_report",
            input_data={"command": "דוח seo"}, priority=5,
        )
        task_manager.transition(task.id, "queued")
        result = agent.execute(task)
        self.assertTrue(result.success)
        self.assertIn("meta_count", result.output)

    def test_seo_agent_city_pages(self):
        from agents.departments.executive.seo_agent import SEOAgent
        from orchestration.task_manager import task_manager
        agent = SEOAgent()
        task = task_manager.create_task(
            type="seo", action="city_pages",
            input_data={}, priority=5,
        )
        task_manager.transition(task.id, "queued")
        result = agent.execute(task)
        self.assertTrue(result.success)
        self.assertGreater(result.output.get("count", 0), 0)

    def test_seo_agent_blog_posts(self):
        from agents.departments.executive.seo_agent import SEOAgent
        from orchestration.task_manager import task_manager
        agent = SEOAgent()
        task = task_manager.create_task(
            type="seo", action="blog_posts",
            input_data={}, priority=5,
        )
        task_manager.transition(task.id, "queued")
        result = agent.execute(task)
        self.assertTrue(result.success)
        self.assertGreater(result.output.get("count", 0), 0)


class TestChannelStrategyAgent(unittest.TestCase):

    def setUp(self):
        _app()

    def test_channel_strategy_can_handle(self):
        from agents.departments.sales.channel_strategy_agent import ChannelStrategyAgent
        agent = ChannelStrategyAgent()
        self.assertTrue(agent.can_handle("channel", "select_channel"))
        self.assertTrue(agent.can_handle("channel", "channel_status"))

    def test_select_channel_task(self):
        from agents.departments.sales.channel_strategy_agent import ChannelStrategyAgent
        from orchestration.task_manager import task_manager
        agent = ChannelStrategyAgent()
        task = task_manager.create_task(
            type="channel", action="select_channel",
            input_data={"name": "דוד", "phone": "0501234567"}, priority=5,
        )
        task_manager.transition(task.id, "queued")
        result = agent.execute(task)
        self.assertTrue(result.success)
        self.assertIn("channel", result.output)

    def test_all_statuses_task(self):
        from agents.departments.sales.channel_strategy_agent import ChannelStrategyAgent
        from orchestration.task_manager import task_manager
        agent = ChannelStrategyAgent()
        task = task_manager.create_task(
            type="channel", action="all_statuses",
            input_data={}, priority=5,
        )
        task_manager.transition(task.id, "queued")
        result = agent.execute(task)
        self.assertTrue(result.success)
        self.assertIn("channels", result.output)


class TestMarketingStrategyAgent(unittest.TestCase):

    def setUp(self):
        _app()

    def test_marketing_agent_can_handle(self):
        from agents.departments.sales.marketing_strategy_agent import MarketingStrategyAgent
        agent = MarketingStrategyAgent()
        self.assertTrue(agent.can_handle("marketing", "weekly_recommendations"))
        self.assertTrue(agent.can_handle("marketing", "post_draft"))

    def test_weekly_recommendations_task(self):
        from agents.departments.sales.marketing_strategy_agent import MarketingStrategyAgent
        from orchestration.task_manager import task_manager
        agent = MarketingStrategyAgent()
        task = task_manager.create_task(
            type="marketing", action="weekly_recommendations",
            input_data={"command": "המלצות שיווק"}, priority=5,
        )
        task_manager.transition(task.id, "queued")
        result = agent.execute(task)
        self.assertTrue(result.success)
        self.assertIn("recommendations", result.output)
        self.assertGreater(len(result.output["recommendations"]), 0)

    def test_post_draft_task(self):
        from agents.departments.sales.marketing_strategy_agent import MarketingStrategyAgent
        from orchestration.task_manager import task_manager
        agent = MarketingStrategyAgent()
        task = task_manager.create_task(
            type="marketing", action="post_draft",
            input_data={}, priority=5,
        )
        task_manager.transition(task.id, "queued")
        result = agent.execute(task)
        self.assertTrue(result.success)
        self.assertGreater(len(result.output.get("posts", [])), 0)


class TestAgentRegistryHas16Agents(unittest.TestCase):

    def setUp(self):
        _app()

    def test_registry_has_all_new_agents(self):
        from agents.base.agent_registry import agent_registry
        agents = agent_registry.list_agents()
        agent_ids = {a.agent_id for a in agents}
        self.assertIn("builtin_followup_agent_v1",           agent_ids)
        self.assertIn("builtin_reporting_agent_v1",          agent_ids)
        self.assertIn("builtin_channel_strategy_agent_v1",   agent_ids)
        self.assertIn("builtin_marketing_strategy_agent_v1", agent_ids)
        self.assertIn("builtin_seo_agent_v1",                agent_ids)
        self.assertGreaterEqual(len(agents), 14)


if __name__ == "__main__":
    unittest.main(verbosity=2)
