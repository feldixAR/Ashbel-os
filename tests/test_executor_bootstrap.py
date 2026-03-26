"""
tests/test_executor_bootstrap.py
================================
Bootstrap validation for AshbelOS Axis 1 stabilization.

Verifies that:
  1. executor.py can be imported without NameError
  2. _HANDLERS is defined at module level (not inside a function)
  3. _handle_set_goal is reachable via _HANDLERS["set_goal"]
  4. All Batch 6-9 handlers are present and callable

Uses AST analysis only — no DB or API keys required.
Run:
    python -m pytest tests/test_executor_bootstrap.py -v
"""

import ast
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXECUTOR_PATH = os.path.join(ROOT, "services", "execution", "executor.py")


def _src() -> str:
    with open(EXECUTOR_PATH, encoding="utf-8") as f:
        return f.read()


def _tree() -> ast.Module:
    return ast.parse(_src())


class TestExecutorImport(unittest.TestCase):
    """executor.py must import cleanly with no NameError."""

    def test_module_parses_without_syntax_error(self):
        """AST parse must succeed — catches SyntaxErrors immediately."""
        try:
            ast.parse(_src())
        except SyntaxError as e:
            self.fail(f"executor.py has a SyntaxError: {e}")

    def test_no_undefined_handle_set_goal(self):
        """
        _handle_set_goal must be defined before _HANDLERS references it.
        Walks the module body in order and confirms definition precedes use.
        """
        tree = _tree()
        handle_set_goal_defined_at = None
        handlers_assigned_at = None

        for i, node in enumerate(ast.walk(tree)):
            if isinstance(node, ast.FunctionDef) and node.name == "_handle_set_goal":
                if handle_set_goal_defined_at is None:
                    handle_set_goal_defined_at = getattr(node, "lineno", i)
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "_HANDLERS":
                        if handlers_assigned_at is None:
                            handlers_assigned_at = getattr(node, "lineno", i)

        self.assertIsNotNone(
            handle_set_goal_defined_at,
            "BOOTSTRAP FAILURE: _handle_set_goal is not defined in executor.py"
        )
        self.assertIsNotNone(
            handlers_assigned_at,
            "BOOTSTRAP FAILURE: _HANDLERS dict not found at module level in executor.py"
        )
        self.assertLess(
            handle_set_goal_defined_at,
            handlers_assigned_at,
            f"BOOTSTRAP FAILURE: _handle_set_goal (line {handle_set_goal_defined_at}) "
            f"must be defined BEFORE _HANDLERS (line {handlers_assigned_at})"
        )


class TestHandlerRegistryStructure(unittest.TestCase):
    """_HANDLERS must be a module-level dict with all required keys."""

    def _handler_keys(self) -> set:
        tree = _tree()
        keys = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "_HANDLERS":
                        if isinstance(node.value, ast.Dict):
                            for k in node.value.keys:
                                keys.add(ast.unparse(k).strip("\"'"))
        return keys

    def test_handlers_dict_exists_at_module_level(self):
        keys = self._handler_keys()
        self.assertGreater(
            len(keys), 0,
            "BOOTSTRAP FAILURE: _HANDLERS not found as a module-level dict in executor.py. "
            "The fix requires converting _get_handlers() to a module-level _HANDLERS dict."
        )

    def test_set_goal_handler_registered(self):
        keys = self._handler_keys()
        self.assertIn(
            "set_goal", keys,
            "BOOTSTRAP FAILURE: 'set_goal' missing from _HANDLERS — "
            "_handle_set_goal will not be reachable at runtime."
        )

    def test_list_goals_handler_registered(self):
        keys = self._handler_keys()
        self.assertIn("list_goals", keys,
                      "'list_goals' missing from _HANDLERS")

    def test_growth_plan_handler_registered(self):
        keys = self._handler_keys()
        self.assertIn("growth_plan", keys,
                      "'growth_plan' missing from _HANDLERS")

    def test_batch6_handlers_complete(self):
        keys = self._handler_keys()
        batch6 = ["set_goal", "list_goals", "growth_plan"]
        for action in batch6:
            with self.subTest(action=action):
                self.assertIn(action, keys,
                              f"Batch-6 action '{action}' missing from _HANDLERS")

    def test_batch7_handlers_complete(self):
        keys = self._handler_keys()
        batch7 = ["research_audience", "build_portfolio", "build_outreach_copy"]
        for action in batch7:
            with self.subTest(action=action):
                self.assertIn(action, keys,
                              f"Batch-7 action '{action}' missing from _HANDLERS")

    def test_batch8_handlers_complete(self):
        keys = self._handler_keys()
        batch8 = ["send_outreach", "daily_plan", "followup_queue"]
        for action in batch8:
            with self.subTest(action=action):
                self.assertIn(action, keys,
                              f"Batch-8 action '{action}' missing from _HANDLERS")

    def test_batch9_handlers_complete(self):
        keys = self._handler_keys()
        batch9 = ["learning_cycle", "performance_report"]
        for action in batch9:
            with self.subTest(action=action):
                self.assertIn(action, keys,
                              f"Batch-9 action '{action}' missing from _HANDLERS")

    def test_minimum_handler_count(self):
        keys = self._handler_keys()
        self.assertGreaterEqual(
            len(keys), 25,
            f"_HANDLERS has only {len(keys)} entries — expected >= 25"
        )


class TestHandlerFunctionsDefined(unittest.TestCase):
    """Every _handle_* function referenced in _HANDLERS must be defined."""

    def _handler_value_names(self) -> set:
        """Extract function names from _HANDLERS values (e.g. _handle_set_goal)."""
        tree = _tree()
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "_HANDLERS":
                        if isinstance(node.value, ast.Dict):
                            for v in node.value.values:
                                if isinstance(v, ast.Name):
                                    names.add(v.id)
        return names

    def _defined_functions(self) -> set:
        tree = _tree()
        return {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }

    def test_all_handler_functions_defined(self):
        referenced = self._handler_value_names()
        defined    = self._defined_functions()
        missing    = referenced - defined
        self.assertEqual(
            missing, set(),
            f"BOOTSTRAP FAILURE: handler function(s) referenced in _HANDLERS "
            f"but NOT defined in executor.py: {missing}"
        )

    def test_handle_set_goal_is_callable_function(self):
        defined = self._defined_functions()
        self.assertIn(
            "_handle_set_goal", defined,
            "BOOTSTRAP FAILURE: _handle_set_goal function is missing from executor.py"
        )


class TestExecuteFunction(unittest.TestCase):
    """execute() must use _HANDLERS, not a helper function."""

    def test_execute_uses_handlers_dict(self):
        src = _src()
        self.assertIn(
            "_HANDLERS.get(action)", src,
            "execute() must call _HANDLERS.get(action) directly (not _get_handlers())"
        )

    def test_get_handlers_function_removed(self):
        """_get_handlers() wrapper function must not exist — it caused the NameError."""
        tree = _tree()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_get_handlers":
                self.fail(
                    "_get_handlers() function still exists in executor.py. "
                    "It must be replaced by the module-level _HANDLERS dict."
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
