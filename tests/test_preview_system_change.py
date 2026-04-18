"""
tests/test_preview_system_change.py — Preview → system change approval → MemoryStore plan proof.

Proves the full self-evolution flow:
  1. preview_system_change handler creates ApprovalModel
  2. Approving the approval stores plan in MemoryStore
  3. /api/system/pending_changes lists it
  4. /api/system/execute_change applies bounded change and marks implemented
  5. Implemented changes no longer appear in pending_changes
Also proves agent dispatch → DB task status is updated.
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


class TestPreviewSystemChangeHandler(unittest.TestCase):

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def test_preview_handler_creates_approval(self):
        from services.storage.models.approval import ApprovalModel
        from services.storage.db import get_session
        from orchestration.task_manager import task_manager

        task = task_manager.create_task(
            type="executive",
            action="preview_system_change",
            input_data={"command": "שנה את גודל הבית ברוחב"},
            priority=3,
        )
        task_manager.transition(task.id, "queued")
        result = task_manager.dispatch(task)
        self.assertIsNotNone(result)

        with get_session() as s:
            approvals = s.query(ApprovalModel).filter_by(action="system_change").all()
        self.assertGreater(len(approvals), 0,
                           "_handle_preview_system_change must create an ApprovalModel")

    def test_preview_approval_status_pending(self):
        from services.storage.models.approval import ApprovalModel
        from services.storage.db import get_session
        from orchestration.task_manager import task_manager

        task = task_manager.create_task(
            type="executive",
            action="preview_system_change",
            input_data={"command": "עדכן הגדרות מסנן לידים"},
            priority=3,
        )
        task_manager.transition(task.id, "queued")
        task_manager.dispatch(task)

        with get_session() as s:
            approvals = s.query(ApprovalModel).filter_by(action="system_change").all()
        self.assertTrue(
            all(a.status == "pending" for a in approvals),
            "system_change approvals must be created in pending status"
        )


class TestSystemChangeApprovalToMemoryStore(unittest.TestCase):

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def _create_system_change_approval(self):
        from services.storage.repositories.approval_repo import ApprovalRepository
        approval = ApprovalRepository().create(
            action="system_change",
            details={
                "change_type": "routing_override",
                "request":     "שפר ניתוב מודל לשיחות מכירה",
                "implementation_plan": "Promote sonnet for sales task",
                "affected_files": ["routing/model_router.py"],
                "task_type":    "sales_test_preview",
                "model_key":    "sonnet",
            },
            risk_level=3,
            requested_by="test",
        )
        return approval

    def test_approve_system_change_stores_plan(self):
        from memory.memory_store import MemoryStore
        approval = self._create_system_change_approval()

        r = _client().post(f"/api/approvals/{approval.id}",
                           json={"action": "approve"},
                           headers=_headers())
        self.assertEqual(r.status_code, 200)

        all_keys = MemoryStore.list_namespace("global")
        change_keys = [k for k in all_keys if k.startswith("pending_change_")]
        self.assertGreater(len(change_keys), 0,
                           "Approving a system_change must store plan in MemoryStore global namespace")

    def test_pending_changes_endpoint_lists_approved_plan(self):
        approval = self._create_system_change_approval()
        _client().post(f"/api/approvals/{approval.id}",
                       json={"action": "approve"},
                       headers=_headers())

        r = _client().get("/api/system/pending_changes", headers=_headers())
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        data = d.get("data", d)
        self.assertGreater(data.get("count", 0), 0,
                           "pending_changes endpoint must list the approved plan")

    def test_deny_system_change_does_not_store_plan(self):
        from memory.memory_store import MemoryStore
        approval = self._create_system_change_approval()

        before = set(MemoryStore.list_namespace("global").keys())
        r = _client().post(f"/api/approvals/{approval.id}",
                           json={"action": "deny"},
                           headers=_headers())
        self.assertEqual(r.status_code, 200)
        after = set(MemoryStore.list_namespace("global").keys())
        new_change_keys = [k for k in after - before if k.startswith("pending_change_")]
        self.assertEqual(len(new_change_keys), 0,
                         "Denying a system_change must NOT store a plan in MemoryStore")


class TestSelfEvolutionExecuteChange(unittest.TestCase):

    def setUp(self):
        _app()
        os.environ["OS_API_KEY"] = "test"

    def _store_pending_change(self, change_id, change_type, extra=None):
        from memory.memory_store import MemoryStore
        plan = {
            "approval_id":   f"approval_{change_id}",
            "change_type":   change_type,
            "request":       "בדיקה",
            "plan":          "test plan",
            "affected_files": [],
            "status":        "approved_pending_implementation",
        }
        if extra:
            plan.update(extra)
        MemoryStore.write("global", f"pending_change_{change_id}", plan,
                          updated_by="test")
        return change_id

    def test_execute_routing_override_returns_applied(self):
        cid = self._store_pending_change(
            "exectest1", "routing_override",
            {"task_type": "sales_exec_test", "model_key": "haiku"}
        )
        r = _client().post(f"/api/system/execute_change/{cid}", headers=_headers())
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("data", d).get("applied"),
                        "execute_change with routing_override must return applied=True")

    def test_execute_routing_override_updates_model_router(self):
        cid = self._store_pending_change(
            "exectest2", "routing_override",
            {"task_type": "exec_proof_task", "model_key": "sonnet"}
        )
        _client().post(f"/api/system/execute_change/{cid}", headers=_headers())

        from routing.model_router import model_router
        override = model_router._get_learning_override("exec_proof_task")
        self.assertEqual(override, "sonnet",
                         "execute_change must update model routing via promote_model")

    def test_execute_template_update_applies(self):
        cid = self._store_pending_change(
            "exectest3", "template_update",
            {"template_type": "first_contact_exec_test",
             "template_text": "תבנית ניסיון מ-execute_change"}
        )
        r = _client().post(f"/api/system/execute_change/{cid}", headers=_headers())
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d.get("data", d).get("applied"))

        from memory.memory_store import MemoryStore
        val = MemoryStore.read("messaging", "best_first_contact_exec_test")
        self.assertIsNotNone(val, "execute_change template_update must write to messaging MemoryStore")

    def test_execute_unknown_type_returns_plan_only(self):
        cid = self._store_pending_change("exectest4", "unknown_type")
        r = _client().post(f"/api/system/execute_change/{cid}", headers=_headers())
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        data = d.get("data", d)
        self.assertFalse(data.get("applied"),
                         "Unknown change_type must return applied=False (plan_only)")
        self.assertEqual(data.get("status"), "plan_only")

    def test_execute_marks_plan_as_implemented(self):
        from memory.memory_store import MemoryStore
        cid = self._store_pending_change(
            "exectest5", "routing_override",
            {"task_type": "impl_check_task", "model_key": "haiku"}
        )
        _client().post(f"/api/system/execute_change/{cid}", headers=_headers())

        updated = MemoryStore.read("global", f"pending_change_{cid}")
        self.assertEqual(updated.get("status"), "implemented",
                         "execute_change must update MemoryStore plan status to 'implemented'")
        self.assertIn("implemented_at", updated)

    def test_execute_not_found_returns_404(self):
        r = _client().post("/api/system/execute_change/nonexistent_change_id",
                           headers=_headers())
        self.assertEqual(r.status_code, 404)

    def test_implemented_change_excluded_from_pending_list(self):
        from memory.memory_store import MemoryStore
        cid = self._store_pending_change(
            "exectest6", "routing_override",
            {"task_type": "excl_test_task", "model_key": "haiku"}
        )
        _client().post(f"/api/system/execute_change/{cid}", headers=_headers())

        r = _client().get("/api/system/pending_changes", headers=_headers())
        d = r.get_json()
        changes = d.get("data", {}).get("pending_changes") or []
        ids = [c.get("approval_id") for c in changes]
        self.assertNotIn(f"approval_{cid}", ids,
                         "Implemented changes must not appear in pending_changes list")


class TestAgentDispatchStatusUpdate(unittest.TestCase):
    """Agent dispatch updates task status in DB — not just returns a result dict."""

    def setUp(self):
        _app()

    def test_dispatch_updates_task_status_to_completed(self):
        from orchestration.task_manager import task_manager
        from services.storage.models.task import TaskModel
        from services.storage.db import get_session

        task = task_manager.create_task(
            type="acquisition",
            action="discover_leads",
            input_data={"command": "מצא לידים בתל אביב"},
            priority=5,
        )
        task_manager.transition(task.id, "queued")
        task_manager.dispatch(task)

        with get_session() as s:
            db_task = s.get(TaskModel, task.id)
            status = db_task.status if db_task else None
        _TERMINAL = {"completed", "failed", "done", "error"}
        self.assertIn(status, _TERMINAL,
                      f"Task status must be terminal after dispatch; got '{status}'")

    def test_dispatch_returns_dict(self):
        from orchestration.task_manager import task_manager
        task = task_manager.create_task(
            type="crm",
            action="create_lead",
            input_data={"command": "צור ליד בדיקה"},
            priority=5,
        )
        task_manager.transition(task.id, "queued")
        result = task_manager.dispatch(task)
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main(verbosity=2)
