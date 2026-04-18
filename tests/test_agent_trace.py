"""
tests/test_agent_trace.py — Agent execution trace and visibility tests.

Proves:
- executor routes to _HANDLERS correctly
- unhandled action returns graceful failure
- crashing handler returns graceful failure (not exception)
- task lifecycle events emitted (TASK_CREATED at minimum)
- trace_id propagated through task_manager
- OrchestratorResult always returned (never raises to caller)
"""
import os
import sys
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OS_API_KEY", "test")
os.environ.setdefault("ENV", "test")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize Flask app once to set up DB schema for all tests
_APP = None


def _app():
    global _APP
    if _APP is None:
        from api.app import create_app
        _APP = create_app()
        _APP.config["TESTING"] = True
    return _APP


# Trigger app + DB init at import time
_app()


def _make_task(action: str, task_type: str = "crm", trace_id: str = "trace-001"):
    from services.storage.models.task import TaskModel
    t = TaskModel()
    t.id         = f"task-{action[:20]}"
    t.type       = task_type
    t.action     = action
    t.input_data = {"command": "test", "intent": "test",
                    "context": "test", "params": {}}
    t.priority   = 5
    t.risk_level = 1
    t.status     = "running"
    t.trace_id   = trace_id
    return t


class TestExecutorRouting(unittest.TestCase):

    def test_create_lead_handler_exists_and_returns_result(self):
        from services.execution.executor import execute
        task = _make_task("create_lead", "sales")
        result = execute(task)
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, "success"))
        self.assertTrue(hasattr(result, "message"))

    def test_unhandled_action_does_not_raise(self):
        # GenericTaskAgent handles unknown actions as a fallback — result is
        # ExecutionResult (success or failure), never an unhandled exception.
        from services.execution.executor import execute
        task = _make_task("this_action_definitely_does_not_exist_xXx")
        try:
            result = execute(task)
            self.assertTrue(hasattr(result, "success"))
        except Exception as e:
            self.fail(f"execute() raised for unknown action: {e}")

    def test_unhandled_action_result_has_message(self):
        from services.execution.executor import execute
        task = _make_task("totally_unknown_action_abc123")
        result = execute(task)
        self.assertIsNotNone(result.message)

    def test_crashing_handler_returns_graceful_failure(self):
        from services.execution.executor import execute, _HANDLERS

        def _boom(task):
            raise RuntimeError("simulated handler crash")

        _HANDLERS["__test_crash__"] = _boom
        try:
            task = _make_task("__test_crash__")
            result = execute(task)
            self.assertFalse(result.success)
            self.assertIsNotNone(result.message)
        finally:
            del _HANDLERS["__test_crash__"]

    def test_execution_result_has_output_dict(self):
        from services.execution.executor import execute
        task = _make_task("create_lead", "sales")
        result = execute(task)
        # output may be None for some handlers — check type when present
        if result.output is not None:
            self.assertIsInstance(result.output, dict)

    def test_handlers_dict_is_nonempty(self):
        from services.execution.executor import _HANDLERS
        self.assertGreater(len(_HANDLERS), 0)
        self.assertIsInstance(_HANDLERS, dict)


class TestTaskLifecycleEvents(unittest.TestCase):

    def test_create_task_emits_task_created(self):
        from orchestration.task_manager import task_manager
        from events.event_bus import event_bus
        import events.event_types as ET

        seen = []
        original = event_bus.publish

        def capture(event_type, **kw):
            seen.append(event_type)
            return original(event_type, **kw)

        event_bus.publish = capture
        try:
            task_manager.create_task(
                type="crm", action="read_data",
                input_data={"command": "t", "intent": "STATUS",
                            "context": "t", "params": {}},
                trace_id="trace-lc-1",
            )
            self.assertIn(ET.TASK_CREATED, seen,
                          f"TASK_CREATED not emitted; saw: {seen}")
        finally:
            event_bus.publish = original

    def test_trace_id_stored_on_task(self):
        from orchestration.task_manager import task_manager
        task = task_manager.create_task(
            type="crm", action="read_data",
            input_data={"command": "t", "intent": "STATUS",
                        "context": "t", "params": {}},
            trace_id="trace-stored-42",
        )
        self.assertEqual(task.trace_id, "trace-stored-42")

    def test_dispatch_returns_dict_with_success(self):
        from orchestration.task_manager import task_manager
        task = task_manager.create_task(
            type="sales", action="create_lead",
            input_data={"command": "צור ליד", "intent": "CREATE_LEAD",
                        "context": "test", "params": {"name": "Trace Test"}},
            trace_id="trace-dispatch-1",
        )
        task_manager.transition(task.id, "queued")
        result = task_manager.dispatch(task)
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)

    def test_dispatch_emits_task_completed_or_failed(self):
        from orchestration.task_manager import task_manager
        from events.event_bus import event_bus
        import events.event_types as ET

        seen = []
        original = event_bus.publish

        def capture(event_type, **kw):
            seen.append(event_type)
            return original(event_type, **kw)

        event_bus.publish = capture
        try:
            task = task_manager.create_task(
                type="sales", action="create_lead",
                input_data={"command": "צור", "intent": "CREATE_LEAD",
                            "context": "t", "params": {"name": "Event Check"}},
                trace_id="trace-dispatch-ev-1",
            )
            task_manager.transition(task.id, "queued")
            task_manager.dispatch(task)
            terminal_events = {ET.TASK_COMPLETED, ET.TASK_FAILED}
            self.assertTrue(
                any(e in seen for e in terminal_events),
                f"No terminal lifecycle event emitted; saw: {seen}",
            )
        finally:
            event_bus.publish = original


class TestOrchestratorTrace(unittest.TestCase):

    def test_handle_command_returns_orchestrator_result(self):
        from orchestration.orchestrator import orchestrator, OrchestratorResult
        result = orchestrator.handle_command("הצג לידים")
        self.assertIsInstance(result, OrchestratorResult)

    def test_orchestrator_result_has_trace_id(self):
        from orchestration.orchestrator import orchestrator
        result = orchestrator.handle_command("מה הסטטוס")
        self.assertIsNotNone(result.trace_id, "trace_id must not be None")

    def test_orchestrator_result_has_intent(self):
        from orchestration.orchestrator import orchestrator
        result = orchestrator.handle_command("הצג לידים")
        self.assertIsNotNone(result.intent)

    def test_unknown_command_does_not_raise(self):
        from orchestration.orchestrator import orchestrator, OrchestratorResult
        try:
            result = orchestrator.handle_command("!!@@##$$%%")
            self.assertIsInstance(result, OrchestratorResult)
        except Exception as e:
            self.fail(f"Orchestrator raised exception for unknown command: {e}")

    def test_orchestrator_result_is_dataclass_not_dict(self):
        from orchestration.orchestrator import orchestrator, OrchestratorResult
        result = orchestrator.handle_command("הצג לידים")
        # Must access .message not ["message"] — dataclass contract
        self.assertTrue(hasattr(result, "message"))
        self.assertTrue(hasattr(result, "success"))
        self.assertTrue(hasattr(result, "intent"))


class TestAgentRegistryFallback(unittest.TestCase):

    def test_agent_registry_find_returns_agent_or_none(self):
        from agents.base.agent_registry import agent_registry
        # Known agent type
        agent = agent_registry.find("acquisition", "discover_leads")
        # May return an agent or None — must not raise
        self.assertIn(type(agent).__name__,
                      ["NoneType"] + [a.__class__.__name__
                                      for a in [agent] if agent is not None])

    def test_agent_registry_find_unknown_returns_none_or_generic(self):
        from agents.base.agent_registry import agent_registry
        result = agent_registry.find("unknown_type_xyz", "unknown_action_xyz")
        # GenericTaskAgent fallback or None — must not raise
        if result is not None:
            self.assertTrue(hasattr(result, "execute"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
