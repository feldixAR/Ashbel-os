"""
tests/test_learning_feedback.py — Learning feedback loop proof.

Proves that recorded outcomes change live runtime decisions:
  - get_best_template() returns promoted templates and is used in draft paths
  - model routing overrides (promote_model) flow through model_router
  - source outcomes accumulate and best_source is updated
  - promote_model → model_router._get_learning_override() returns override
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


class TestTemplateFeedbackLoop(unittest.TestCase):

    def setUp(self):
        _app()

    def test_record_then_get_best_template(self):
        from skills.learning_skills import record_template_outcome, get_best_template
        record_template_outcome(
            template_type="first_contact",
            template_text="שלום מ-אשבל, ניסיון A",
            outcome="reply",
            segment="commercial",
            channel="whatsapp",
        )
        record_template_outcome(
            template_type="first_contact",
            template_text="שלום מ-אשבל, ניסיון A",
            outcome="meeting",
            segment="commercial",
            channel="whatsapp",
        )
        result = get_best_template("first_contact", "commercial", "whatsapp")
        self.assertIsNotNone(result, "get_best_template must return a template after 2 positive outcomes")
        self.assertIn("אשבל", result)

    def test_get_best_template_fallback_chain(self):
        from skills.learning_skills import record_template_outcome, get_best_template
        record_template_outcome(
            template_type="follow_up",
            template_text="מעקב אשבל — ניסיון type-only",
            outcome="reply",
        )
        record_template_outcome(
            template_type="follow_up",
            template_text="מעקב אשבל — ניסיון type-only",
            outcome="meeting",
        )
        result = get_best_template("follow_up", "nonexistent_segment", "nonexistent_channel")
        # Fallback chain: segment+channel → segment-only → type-only
        # The type-only key should be found
        self.assertIsNotNone(result, "Fallback chain should reach type-only key")

    def test_draft_first_contact_uses_learned_template(self):
        from skills.learning_skills import record_template_outcome
        from skills.outreach_intelligence import draft_first_contact

        learned_text = "הודעה מנצחת — אשבל אלומיניום פרו"
        # Promote enough to qualify
        for _ in range(2):
            record_template_outcome(
                template_type="first_contact",
                template_text=learned_text,
                outcome="meeting",
                segment="testloop",
                channel="whatsapp",
            )
        lead = {"name": "בדיקה", "segment": "testloop", "phone": "0501234567"}
        draft = draft_first_contact(lead)
        self.assertEqual(draft.body, learned_text,
                         "draft_first_contact must return the learned template body when available")

    def test_draft_followup_uses_learned_template(self):
        from skills.learning_skills import record_template_outcome
        from skills.outreach_intelligence import draft_followup

        learned_text = "follow-up מנצח — אשבל"
        for _ in range(2):
            record_template_outcome(
                template_type="follow_up",
                template_text=learned_text,
                outcome="reply",
                segment="testfollowup",
                channel="whatsapp",
            )
        lead = {"name": "טסט", "segment": "testfollowup", "phone": "0509999999"}
        draft = draft_followup(lead)
        self.assertEqual(draft.body, learned_text,
                         "draft_followup must return the learned template body when available")

    def test_no_learned_template_uses_default(self):
        from skills.outreach_intelligence import draft_first_contact
        lead = {"name": "ללא למידה", "segment": "totally_new_segment_xyz"}
        draft = draft_first_contact(lead)
        self.assertIn("אשבל", draft.body, "Default template must contain brand name")
        self.assertTrue(len(draft.body) > 50)


class TestModelRoutingFeedbackLoop(unittest.TestCase):

    def setUp(self):
        _app()

    def test_promote_model_then_routing_override_returned(self):
        from skills.learning_skills import promote_model
        from routing.model_router import model_router

        promote_model("test_routing_task", "claude_sonnet", reason="test feedback loop")
        override = model_router._get_learning_override("test_routing_task")
        self.assertEqual(override, "claude_sonnet",
                         "model_router._get_learning_override must return the promoted model key")

    def test_promote_model_affects_select_model(self):
        from skills.learning_skills import promote_model
        from routing.model_router import model_router
        from config.models import ModelConfig

        promote_model("feedback_task_x", "claude_haiku", reason="test select_model")
        model = model_router._select_model("feedback_task_x", "balanced")
        self.assertIsInstance(model, ModelConfig)
        self.assertEqual(model.key, "claude_haiku",
                         "promote_model must change the model selected by _select_model")

    def test_no_override_falls_back_to_task_type_mapping(self):
        from routing.model_router import model_router
        # Using a task type with no override
        model = model_router._select_model("__no_override_task__", "balanced")
        self.assertIsNotNone(model)


class TestSourceStrategyFeedbackLoop(unittest.TestCase):

    def setUp(self):
        _app()

    def test_record_source_outcome_and_get_best(self):
        from skills.learning_skills import record_source_outcome, get_best_source

        goal = "test_residential_goal"
        # Run 3 times for qualification threshold
        for _ in range(3):
            record_source_outcome("google_maps", goal, leads_found=10, leads_qualified=7)
        for _ in range(3):
            record_source_outcome("manual", goal, leads_found=10, leads_qualified=2)

        best = get_best_source(goal)
        self.assertEqual(best, "google_maps",
                         "get_best_source must return source with highest qualification rate after 3+ runs")

    def test_below_threshold_returns_none(self):
        from skills.learning_skills import record_source_outcome, get_best_source
        goal = "test_threshold_goal_only1run"
        record_source_outcome("linkedin", goal, leads_found=5, leads_qualified=4)
        best = get_best_source(goal)
        # Only 1 run — threshold is 3, so no recommendation yet
        self.assertIsNone(best, "get_best_source must return None if no source has 3+ runs")

    def test_acquisition_engine_returns_recommended_source(self):
        from skills.learning_skills import record_source_outcome
        from engines.lead_acquisition_engine import run_acquisition

        goal = "acquisition_test_goal_xyz"
        goal_key = goal.lower().replace(" ", "_")[:30]
        for _ in range(3):
            record_source_outcome("google_maps", goal_key, leads_found=8, leads_qualified=6)

        result = run_acquisition(goal=goal, signals=[])
        self.assertEqual(result.recommended_source, "google_maps",
                         "run_acquisition must return recommended_source when learning data exists")

    def test_acquisition_with_signals_records_source_outcomes(self):
        from skills.learning_skills import get_source_stats
        from engines.lead_acquisition_engine import run_acquisition

        signals = [
            {"name": "בדיקה 1", "phone": "0501111111", "source_type": "linkedin",
             "city": "תל אביב", "company": "חברת A"},
        ]
        goal = "test_record_source"
        run_acquisition(goal=goal, signals=signals)
        goal_key = goal.lower().replace(" ", "_")[:30]
        stats = get_source_stats(goal_key)
        # linkedin stats should be recorded
        self.assertIn("linkedin", stats,
                      "run_acquisition must call record_source_outcome for signals with source_type")


class TestLearningSnapshotEndpoint(unittest.TestCase):

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def test_snapshot_endpoint_returns_ok(self):
        from skills.learning_skills import promote_model, record_template_outcome
        promote_model("sales", "haiku", reason="snapshot test")
        record_template_outcome("first_contact", "snapshot body", "reply")

        client = _app().test_client()
        r = client.get("/api/learning/snapshot")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("success"))
        snap = d.get("snapshot", {})
        self.assertIn("model_overrides", snap)
        self.assertIn("best_templates", snap)
        self.assertIn("conversion", snap)

    def test_snapshot_reflects_promote_model(self):
        from skills.learning_skills import promote_model
        promote_model("snapshot_task", "claude_opus", reason="endpoint test")

        client = _app().test_client()
        r = client.get("/api/learning/snapshot")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        overrides = d.get("snapshot", {}).get("model_overrides", {})
        self.assertEqual(overrides.get("snapshot_task"), "claude_opus")


if __name__ == "__main__":
    unittest.main(verbosity=2)
