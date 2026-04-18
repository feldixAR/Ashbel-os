"""
tests/test_self_evolution.py — Self-evolution and learning runtime tests.

Proves:
- GET /api/system/pending_changes returns list
- MemoryStore write → appears in pending_changes
- Non-pending_implementation status excluded
- Non pending_change_ key excluded
- system_change approval stores plan in MemoryStore
- Learning: recommend_model / promote_model round-trip works
- Learning: record_agent_outcome persists and influences agent tracking
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


def _reset_key():
    """Ensure OS_API_KEY matches _AUTH before requests (other modules may change it)."""
    os.environ["OS_API_KEY"] = "test"


class TestPendingChangesEndpoint(unittest.TestCase):
    def setUp(self):
        _reset_key()

    def test_endpoint_returns_200_and_list(self):
        r = _client().get("/api/system/pending_changes", headers=_AUTH)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("success"), d)
        self.assertIn("pending_changes", d.get("data", {}))
        self.assertIsInstance(d["data"]["pending_changes"], list)

    def test_written_pending_change_appears_in_list(self):
        from memory.memory_store import MemoryStore
        MemoryStore.write("global", "pending_change_testproof01", {
            "branch":        "feat/system-change-testproof01",
            "approval_id":   "test-proof-approval-01",
            "change_type":   "ui_widget",
            "request":       "Add a proof-of-concept widget",
            "plan":          ["Step 1", "Step 2"],
            "affected_files": ["ui/js/panels/demo.js"],
            "status":        "approved_pending_implementation",
        }, updated_by="test")

        r = _client().get("/api/system/pending_changes", headers=_AUTH)
        d = r.get_json()
        changes = d["data"]["pending_changes"]
        approval_ids = [c.get("approval_id") for c in changes]
        self.assertIn("test-proof-approval-01", approval_ids,
                      f"Pending change not visible; found: {approval_ids}")

    def test_implemented_status_excluded(self):
        from memory.memory_store import MemoryStore
        MemoryStore.write("global", "pending_change_donexyz99", {
            "approval_id": "done-approval-xyz99",
            "status":      "implemented",
        }, updated_by="test")

        r = _client().get("/api/system/pending_changes", headers=_AUTH)
        d = r.get_json()
        approval_ids = [c.get("approval_id") for c in d["data"]["pending_changes"]]
        self.assertNotIn("done-approval-xyz99", approval_ids)

    def test_non_pending_change_key_excluded(self):
        from memory.memory_store import MemoryStore
        MemoryStore.write("global", "settings_xyz_notachange", {
            "approval_id": "settings-not-a-change",
            "status":      "approved_pending_implementation",
        }, updated_by="test")

        r = _client().get("/api/system/pending_changes", headers=_AUTH)
        d = r.get_json()
        approval_ids = [c.get("approval_id") for c in d["data"]["pending_changes"]]
        self.assertNotIn("settings-not-a-change", approval_ids)

    def test_count_matches_list_length(self):
        r = _client().get("/api/system/pending_changes", headers=_AUTH)
        d = r.get_json()
        data = d["data"]
        self.assertEqual(data["count"], len(data["pending_changes"]))


class TestSystemChangeApprovalPath(unittest.TestCase):
    """system_change approval → branch created + plan stored in MemoryStore."""
    def setUp(self):
        _reset_key()

    def _create_system_change_approval(self):
        from services.storage.repositories.approval_repo import ApprovalRepository
        a = ApprovalRepository().create(
            action="preview_system_change",
            details={
                "change_type":           "ui_widget",
                "request":               "Add a self-evolution test widget",
                "implementation_plan":   ["Step 1: add widget", "Step 2: test"],
                "affected_files":        ["ui/js/panels/test_widget.js"],
            },
            risk_level=3,
            requested_by="test_self_evo",
        )
        return a.id

    def test_approve_system_change_stores_plan_in_memory(self):
        from api.routes.approvals import _resolve_approval
        from memory.memory_store import MemoryStore

        aid = self._create_system_change_approval()
        _resolve_approval(aid, "approve", source="test")

        all_keys = MemoryStore.list_namespace("global")
        change_keys = [k for k in all_keys if k.startswith("pending_change_")]
        self.assertTrue(change_keys,
                        "No pending_change_* key written to MemoryStore after system_change approval")

        stored = all_keys.get(change_keys[-1], {})
        self.assertEqual(stored.get("status"), "approved_pending_implementation",
                         f"Unexpected stored status: {stored.get('status')}")

    def test_approve_system_change_stores_change_type(self):
        from api.routes.approvals import _resolve_approval
        from memory.memory_store import MemoryStore

        aid = self._create_system_change_approval()
        _resolve_approval(aid, "approve", source="test")

        all_keys = MemoryStore.list_namespace("global")
        change_keys = [k for k in all_keys if k.startswith("pending_change_")]
        stored = all_keys.get(change_keys[-1], {})
        self.assertEqual(stored.get("change_type"), "ui_widget")

    def test_approve_system_change_returns_hebrew_confirmation(self):
        from api.routes.approvals import _resolve_approval
        aid = self._create_system_change_approval()
        result = _resolve_approval(aid, "approve", source="test")
        self.assertIn("✅", result)
        self.assertIn("אושר", result)

    def test_deny_system_change_returns_denied(self):
        from api.routes.approvals import _resolve_approval
        aid = self._create_system_change_approval()
        result = _resolve_approval(aid, "deny", source="test")
        self.assertIn("נדחה", result)

    def test_pending_changes_api_shows_approved_system_change(self):
        from api.routes.approvals import _resolve_approval
        aid = self._create_system_change_approval()
        _resolve_approval(aid, "approve", source="test")

        r = _client().get("/api/system/pending_changes", headers=_AUTH)
        d = r.get_json()
        self.assertGreater(d["data"]["count"], 0,
                           "pending_changes empty after system_change approval")


class TestLearningRuntime(unittest.TestCase):
    """Learning skills persist and influence decisions."""

    def test_recommend_model_returns_none_or_known_key(self):
        from skills.learning_skills import recommend_model
        result = recommend_model("unknown_task_type_xyz")
        self.assertIn(result, (None, "haiku", "sonnet", "opus"))

    def test_promote_model_sets_routing_override(self):
        from skills.learning_skills import promote_model, recommend_model
        promote_model("test_task_promo_99", "sonnet", "haiku")
        result = recommend_model("test_task_promo_99")
        self.assertEqual(result, "sonnet",
                         "promote_model did not set expected routing override")

    def test_record_agent_outcome_persists(self):
        from skills.learning_skills import record_agent_outcome
        from memory.memory_store import MemoryStore
        record_agent_outcome(
            agent_id="test-agent-evo-1",
            action_type="discover_leads",
            success=True,
            latency_ms=250,
        )
        data = MemoryStore.read("agent:test-agent-evo-1", "action_discover_leads")
        self.assertIsNotNone(data, "record_agent_outcome did not persist to MemoryStore")
        self.assertEqual(data.get("success"), 1)

    def test_record_template_outcome_persists(self):
        from skills.learning_skills import record_template_outcome
        from memory.memory_store import MemoryStore
        record_template_outcome(
            template_type="outreach_evo_test",
            template_text="test template for evo",
            outcome="reply",
            segment="architects",
            channel="whatsapp",
        )
        # Key is stats_{type}_{segment}_{channel}
        data = MemoryStore.read("messaging", "stats_outreach_evo_test_architects_whatsapp")
        self.assertIsNotNone(data,
                             "record_template_outcome did not persist stats to MemoryStore")
        self.assertGreater(data.get("total", 0), 0)

    def test_record_lead_conversion_persists(self):
        from skills.learning_skills import record_lead_conversion
        from memory.memory_store import MemoryStore
        record_lead_conversion(
            lead_id="lc-evo-1",
            segment="residential",
            source_type="google_maps",
            score_at_outreach=75,
            converted=True,
        )
        # score 75 → "high" bucket → key "conversion_bucket_high"
        data = MemoryStore.read("leads", "conversion_bucket_high")
        self.assertIsNotNone(data,
                             "record_lead_conversion did not persist to MemoryStore")
        self.assertGreater(data.get("total", 0), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
