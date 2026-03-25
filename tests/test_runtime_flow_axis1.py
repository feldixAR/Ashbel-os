"""
tests/test_runtime_flow_axis1.py
================================
Axis 1 — Runtime Flow validation.
Verifies the three bugs found in the Axis 1 audit are fixed.

All checks use AST analysis so no runtime dependencies (DB, API keys) are needed.
Run:
    python -m pytest tests/test_runtime_flow_axis1.py -v
"""

import ast
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src(rel: str) -> str:
    with open(os.path.join(ROOT, rel)) as f:
        return f.read()


def _tree(rel: str) -> ast.Module:
    return ast.parse(_src(rel))


def _calls_in_func(tree: ast.Module, func_name: str):
    """Yield all ast.Call nodes inside the named function."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    yield child


# ─────────────────────────────────────────────────────────────────────────────
# BUG-1 — orchestrator.py: handle_command must NOT call mark_completed/mark_failed
# ─────────────────────────────────────────────────────────────────────────────

class TestBug1NoDuplicateLifecycle(unittest.TestCase):
    """
    dispatch() owns mark_started → execute → mark_completed/mark_failed.
    orchestrator.handle_command() must only call dispatch() and read its result.
    """

    ORCHESTRATOR = "orchestration/orchestrator.py"

    def _attr_calls_in_handle_command(self):
        tree = _tree(self.ORCHESTRATOR)
        return [
            c.func.attr
            for c in _calls_in_func(tree, "handle_command")
            if isinstance(c.func, ast.Attribute)
        ]

    def test_mark_completed_not_in_handle_command(self):
        attrs = self._attr_calls_in_handle_command()
        self.assertNotIn(
            "mark_completed", attrs,
            "BUG-1 NOT FIXED: handle_command() still calls mark_completed(). "
            "dispatch() already does this — results in duplicate DB write and "
            "duplicate TASK_COMPLETED event."
        )

    def test_mark_failed_not_in_handle_command(self):
        attrs = self._attr_calls_in_handle_command()
        self.assertNotIn(
            "mark_failed", attrs,
            "BUG-1 NOT FIXED: handle_command() still calls mark_failed(). "
            "dispatch() already handles failure lifecycle."
        )

    def test_dispatch_is_called_in_handle_command(self):
        """dispatch() must still be called — we only removed the duplicate calls."""
        attrs = self._attr_calls_in_handle_command()
        self.assertIn(
            "dispatch", attrs,
            "REGRESSION: dispatch() was removed from handle_command()."
        )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-2 — whatsapp.py: receive_webhook must call handle_command, not handle
# ─────────────────────────────────────────────────────────────────────────────

class TestBug2CorrectOrchestratorMethod(unittest.TestCase):

    WHATSAPP = "api/routes/whatsapp.py"

    def _attr_calls_in_receive_webhook(self):
        tree = _tree(self.WHATSAPP)
        return [
            c.func.attr
            for c in _calls_in_func(tree, "receive_webhook")
            if isinstance(c.func, ast.Attribute)
        ]

    def test_handle_not_called(self):
        """
        Orchestrator has no .handle() method.
        Calling it raises AttributeError which is swallowed by except,
        meaning every inbound WhatsApp message is silently dropped.
        """
        attrs = self._attr_calls_in_receive_webhook()
        # attr must not be exactly "handle" (handle_command is fine)
        bare_handle = [a for a in attrs if a == "handle"]
        self.assertEqual(
            bare_handle, [],
            "BUG-2 NOT FIXED: receive_webhook() still calls .handle(). "
            "Orchestrator.handle() does not exist → AttributeError → silent drop."
        )

    def test_handle_command_is_called(self):
        attrs = self._attr_calls_in_receive_webhook()
        self.assertIn(
            "handle_command", attrs,
            "BUG-2 NOT FIXED: receive_webhook() does not call handle_command()."
        )

    def test_result_get_response_not_used(self):
        """
        OrchestratorResult is a @dataclass, not a dict.
        result.get('response') raises AttributeError.
        """
        tree = _tree(self.WHATSAPP)
        for call in _calls_in_func(tree, "receive_webhook"):
            if (isinstance(call.func, ast.Attribute)
                    and call.func.attr == "get"
                    and call.args
                    and isinstance(call.args[0], ast.Constant)
                    and call.args[0].value == "response"):
                self.fail(
                    "BUG-2 NOT FIXED: result.get('response') still in receive_webhook(). "
                    "OrchestratorResult is a dataclass — use result.message."
                )

    def test_result_message_attribute_used(self):
        tree = _tree(self.WHATSAPP)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "receive_webhook":
                for child in ast.walk(node):
                    if (isinstance(child, ast.Attribute)
                            and child.attr == "message"
                            and isinstance(child.value, ast.Name)
                            and child.value.id == "result"):
                        found = True
        self.assertTrue(
            found,
            "BUG-2 NOT FIXED: result.message not found in receive_webhook(). "
            "Must access the dataclass attribute, not use .get()."
        )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-3 — whatsapp.py: must use singleton, not per-request Orchestrator()
# ─────────────────────────────────────────────────────────────────────────────

class TestBug3SingletonUsed(unittest.TestCase):

    WHATSAPP = "api/routes/whatsapp.py"

    def test_no_per_request_orchestrator_instantiation(self):
        """Orchestrator() must NOT be constructed inside receive_webhook."""
        tree = _tree(self.WHATSAPP)
        for call in _calls_in_func(tree, "receive_webhook"):
            if (isinstance(call.func, ast.Name)
                    and call.func.id == "Orchestrator"):
                self.fail(
                    "BUG-3 NOT FIXED: Orchestrator() instantiated inside receive_webhook(). "
                    "Use the module-level singleton `orchestrator` (lowercase) — "
                    "same pattern already used correctly in api/routes/commands.py."
                )

    def test_singleton_imported_at_module_level(self):
        """Module must import the singleton `orchestrator`, not the class."""
        tree = _tree(self.WHATSAPP)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "orchestration.orchestrator":
                    for alias in node.names:
                        if alias.name == "orchestrator":
                            found = True
        self.assertTrue(
            found,
            "BUG-3 NOT FIXED: whatsapp.py does not import the singleton `orchestrator`. "
            "Add: from orchestration.orchestrator import orchestrator"
        )

    def test_class_Orchestrator_not_imported(self):
        """Class Orchestrator (capital O) should not be imported — only singleton needed."""
        tree = _tree(self.WHATSAPP)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "orchestration.orchestrator":
                    for alias in node.names:
                        if alias.name == "Orchestrator":
                            self.fail(
                                "BUG-3 NOT FIXED: whatsapp.py imports Orchestrator class. "
                                "Import only the singleton: "
                                "from orchestration.orchestrator import orchestrator"
                            )


# ─────────────────────────────────────────────────────────────────────────────
# Regression — commands.py must be unchanged (already correct)
# ─────────────────────────────────────────────────────────────────────────────

class TestCommandsRouteUnchanged(unittest.TestCase):
    """commands.py was already correct — verify it wasn't broken."""

    COMMANDS = "api/routes/commands.py"

    def test_uses_singleton(self):
        src = _src(self.COMMANDS)
        self.assertIn(
            "from orchestration.orchestrator import orchestrator", src,
            "commands.py singleton import was broken."
        )

    def test_calls_handle_command(self):
        tree = _tree(self.COMMANDS)
        found = any(
            isinstance(c.func, ast.Attribute) and c.func.attr == "handle_command"
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            for c in _calls_in_func(tree, node.name)
        )
        self.assertTrue(found, "commands.py no longer calls handle_command().")

    def test_accesses_result_attributes(self):
        src = _src(self.COMMANDS)
        self.assertIn("result.intent",  src)
        self.assertIn("result.message", src)


# ─────────────────────────────────────────────────────────────────────────────
# Structural — OrchestratorResult is @dataclass with required fields
# ─────────────────────────────────────────────────────────────────────────────

class TestOrchestratorResultContract(unittest.TestCase):

    ORCHESTRATOR = "orchestration/orchestrator.py"

    def _class_node(self) -> ast.ClassDef:
        tree = _tree(self.ORCHESTRATOR)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "OrchestratorResult":
                return node
        self.fail("OrchestratorResult class not found in orchestrator.py")

    def test_is_dataclass(self):
        cls = self._class_node()
        decorators = [
            ast.unparse(d) for d in cls.decorator_list
        ]
        self.assertIn("dataclass", decorators,
                      "OrchestratorResult must be decorated with @dataclass")

    def test_has_message_field(self):
        cls = self._class_node()
        fields = [
            n.target.id for n in ast.walk(cls)
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
        ]
        self.assertIn("message", fields)

    def test_has_success_field(self):
        cls = self._class_node()
        fields = [
            n.target.id for n in ast.walk(cls)
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
        ]
        self.assertIn("success", fields)

    def test_has_to_dict_method(self):
        cls = self._class_node()
        methods = [
            n.name for n in ast.walk(cls)
            if isinstance(n, ast.FunctionDef)
        ]
        self.assertIn("to_dict", methods)


# ─────────────────────────────────────────────────────────────────────────────
# _INTENT_TASK_MAP — all revenue-critical intents mapped
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentTaskMapCoverage(unittest.TestCase):

    ORCHESTRATOR = "orchestration/orchestrator.py"

    def _map_keys(self):
        tree = _tree(self.ORCHESTRATOR)
        keys = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "_INTENT_TASK_MAP":
                        if isinstance(node.value, ast.Dict):
                            for k in node.value.keys:
                                keys[ast.unparse(k).split(".")[-1]] = True
        return keys

    def test_all_required_intents_present(self):
        keys = self._map_keys()
        required = [
            "CREATE_LEAD", "SET_GOAL", "LIST_GOALS", "GROWTH_PLAN",
            "SEND_OUTREACH", "DAILY_PLAN", "FOLLOWUP_QUEUE",
            "LEARNING_CYCLE", "PERFORMANCE_REPORT",
            "RESEARCH_AUDIENCE", "BUILD_PORTFOLIO", "BUILD_OUTREACH_COPY",
        ]
        for intent in required:
            with self.subTest(intent=intent):
                self.assertIn(
                    intent, keys,
                    f"Intent.{intent} missing from _INTENT_TASK_MAP"
                )

    def test_map_has_minimum_entries(self):
        keys = self._map_keys()
        self.assertGreaterEqual(
            len(keys), 25,
            f"_INTENT_TASK_MAP has only {len(keys)} entries — expected >= 25"
        )


# ─────────────────────────────────────────────────────────────────────────────
# singleton defined at module level in orchestrator.py
# ─────────────────────────────────────────────────────────────────────────────

class TestSingletonDefined(unittest.TestCase):

    def test_orchestrator_singleton_at_module_level(self):
        tree = _tree("orchestration/orchestrator.py")
        found = False
        for node in tree.body:          # top-level statements only
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "orchestrator":
                        found = True
        self.assertTrue(
            found,
            "orchestrator singleton not defined at module level in orchestrator.py"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
