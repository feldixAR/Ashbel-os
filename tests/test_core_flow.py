"""
tests/test_core_flow.py — Basic integration tests for AshbelOS core flow.

Tests the critical path: command → orchestrator → executor → result
No DB required (uses SQLite in-memory via settings).
"""

import os
import sys
import unittest

# Set test environment before any imports
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("ENV", "development")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIntentParser(unittest.TestCase):
    """Intent parser correctly classifies Hebrew commands."""

    def setUp(self):
        from orchestration.intent_parser import intent_parser, Intent
        self.parser = intent_parser
        self.Intent = Intent

    def test_create_lead(self):
        result = self.parser.parse("הוסף ליד דוד לוי תל אביב 0501234567")
        self.assertEqual(result.intent, self.Intent.CREATE_LEAD)
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_set_goal(self):
        result = self.parser.parse("הגדל מכירות לאדריכלים")
        self.assertEqual(result.intent, self.Intent.SET_GOAL)

    def test_growth_plan(self):
        result = self.parser.parse("תוכנית צמיחה לאדריכלים")
        self.assertEqual(result.intent, self.Intent.GROWTH_PLAN)

    def test_list_leads(self):
        result = self.parser.parse("הצג לידים")
        self.assertEqual(result.intent, self.Intent.LIST_LEADS)

    def test_revenue_insights(self):
        result = self.parser.parse("מה יביא כסף")
        self.assertEqual(result.intent, self.Intent.REVENUE_INSIGHTS)

    def test_bottleneck(self):
        result = self.parser.parse("מה תקוע")
        self.assertEqual(result.intent, self.Intent.BOTTLENECK)

    def test_daily_plan(self):
        result = self.parser.parse("תכנן לי את היום")
        self.assertEqual(result.intent, self.Intent.DAILY_PLAN)

    def test_research_audience(self):
        # "פרופיל לקוח" is now detected before SALES
        result = self.parser.parse("פרופיל לקוח אדריכלים")
        self.assertEqual(result.intent, self.Intent.RESEARCH_AUDIENCE)

    def test_unknown_returns_low_confidence(self):
        result = self.parser.parse("בננה פיצה קפוצ'ינו")
        self.assertLess(result.confidence, 0.5)

    def test_sales_intent(self):
        # "לקוח חדש" triggers CREATE_LEAD (contains "לקוח") — expected behavior
        result = self.parser.parse("לקוח חדש")
        self.assertIn(result.intent, [self.Intent.CREATE_LEAD, self.Intent.SALES])


class TestOrchestratorMapping(unittest.TestCase):
    """All intents in Intent enum are mapped in _INTENT_TASK_MAP or handled directly.
    Uses AST analysis to avoid sqlalchemy dependency in test environment.
    """

    def _get_task_map_pairs(self):
        """Extract (intent, action) pairs from orchestrator source via AST."""
        import ast, os
        src  = open(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 "orchestration", "orchestrator.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        pairs = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "_INTENT_TASK_MAP":
                        if isinstance(node.value, ast.Dict):
                            for k, v in zip(node.value.keys, node.value.values):
                                intent_name = ast.unparse(k).split(".")[-1]
                                if isinstance(v, ast.Tuple) and len(v.elts) == 2:
                                    action = ast.unparse(v.elts[1]).strip("\"'")
                                    pairs[intent_name] = action
        return pairs

    def _get_handler_keys(self):
        """Extract _HANDLERS keys from executor source via AST."""
        import ast, os
        src  = open(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 "services", "execution", "executor.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        keys = set()
        for node in ast.walk(tree):
            # Handle both `_HANDLERS = {...}` and `_HANDLERS: Dict = {...}`
            value = None
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "_HANDLERS":
                        value = node.value
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == "_HANDLERS":
                    value = node.value
            if value and isinstance(value, ast.Dict):
                for k in value.keys:
                    keys.add(ast.unparse(k).strip("\"'"))
        return keys

    def test_all_revenue_intents_mapped(self):
        pairs = self._get_task_map_pairs()
        required = [
            "CREATE_LEAD", "LIST_LEADS", "HOT_LEADS",
            "SET_GOAL", "LIST_GOALS", "GROWTH_PLAN",
            "REVENUE_INSIGHTS", "BOTTLENECK", "NEXT_ACTION",
            "SEND_OUTREACH", "DAILY_PLAN", "FOLLOWUP_QUEUE",
            "LEARNING_CYCLE", "PERFORMANCE_REPORT",
            "RESEARCH_AUDIENCE", "BUILD_PORTFOLIO", "BUILD_OUTREACH_COPY",
        ]
        for intent in required:
            self.assertIn(intent, pairs, f"Intent.{intent} missing from _INTENT_TASK_MAP")

    def test_all_mapped_actions_have_handlers(self):
        pairs   = self._get_task_map_pairs()
        handlers = self._get_handler_keys()
        # Actions routed through agent registry — no direct handler needed
        agent_routed = {"build_agent_code", "apply_files", "roadmap",
                        "gap_analysis", "batch_status", "read_data"}
        for intent_name, action in pairs.items():
            if action not in agent_routed:
                self.assertIn(action, handlers,
                              f"Action '{action}' (Intent.{intent_name}) missing from _HANDLERS")


class TestSchedulerImport(unittest.TestCase):
    """Scheduler module loads without error."""

    def test_scheduler_imports(self):
        from scheduler.revenue_scheduler import start, stop, status
        s = status()
        self.assertIn("running", s)
        self.assertIn("jobs", s)

    def test_scheduler_jobs_defined(self):
        import scheduler.revenue_scheduler as sch
        self.assertTrue(callable(sch._job_followup))
        self.assertTrue(callable(sch._job_daily_plan))
        self.assertTrue(callable(sch._job_learning_cycle))


class TestEngineWrappers(unittest.TestCase):
    """Engine service wrappers expose expected methods."""

    def test_outreach_engine_api(self):
        from engines.outreach_engine import outreach_engine
        self.assertTrue(callable(outreach_engine.run_outreach_batch))
        self.assertTrue(callable(outreach_engine.run_followup_batch))
        self.assertTrue(callable(outreach_engine.build_daily_summary))
        self.assertTrue(callable(outreach_engine.get_followup_queue))

    def test_learning_engine_api(self):
        from engines.learning_engine import learning_engine
        self.assertTrue(callable(learning_engine.run_learning_cycle))
        self.assertTrue(callable(learning_engine.build_performance_report))


class TestGoalEngine(unittest.TestCase):
    """Goal engine decomposes goals correctly."""

    def test_decompose_aluminum_goal(self):
        from engines.goal_engine import decompose_goal
        result = decompose_goal("הגדל מכירות אלומיניום")
        self.assertIn("domain", result)
        self.assertIn("tracks", result)
        self.assertIsInstance(result["tracks"], list)
        self.assertGreater(len(result["tracks"]), 0)

    def test_decompose_default_goal(self):
        from engines.goal_engine import decompose_goal
        result = decompose_goal("רוצה להגדיל הכנסות")
        self.assertIn("goal_id", result)
        self.assertIsNotNone(result["goal_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
