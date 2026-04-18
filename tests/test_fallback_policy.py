"""
tests/test_fallback_policy.py — Fallback policy unit tests.

Proves:
- successful call returns text on first try
- retryable error triggers chain, second model used
- non-retryable error aborts immediately with FALLBACK_RESPONSE
- all models exhausted returns FALLBACK_RESPONSE
- FALLBACK_RESPONSE is Hebrew
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENV", "test")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routing.fallback_policy import execute_with_fallback, FALLBACK_RESPONSE


def _model(key: str = "haiku"):
    m = MagicMock()
    m.key = key
    m.model_id = f"fake-{key}"
    return m


class TestFallbackPolicySuccess(unittest.TestCase):

    @patch("routing.model_registry.fallback_chain", return_value=[])
    @patch("routing.model_router.ModelRouter.call_model", return_value="תשובה בעברית")
    def test_success_first_try_returns_text(self, mock_call, _):
        result = execute_with_fallback(_model(), "sys", "user", task_type="test")
        self.assertEqual(result, "תשובה בעברית")
        self.assertEqual(mock_call.call_count, 1)

    @patch("routing.model_registry.fallback_chain", return_value=[])
    @patch("routing.model_router.ModelRouter.call_model", return_value="hello")
    def test_max_tokens_passed(self, mock_call, _):
        execute_with_fallback(_model(), "sys", "user", max_tokens=1200, task_type="t")
        args = mock_call.call_args
        # max_tokens is 4th positional arg
        self.assertEqual(args[0][3], 1200)


class TestFallbackPolicyRetryable(unittest.TestCase):

    @patch("routing.model_registry.fallback_chain")
    @patch("routing.model_router.ModelRouter.call_model")
    def test_retryable_error_uses_fallback_model(self, mock_call, mock_chain):
        fallback_m = _model("sonnet")
        mock_chain.return_value = [fallback_m]
        attempt = [0]

        def side(*args, **kw):
            attempt[0] += 1
            if attempt[0] == 1:
                raise Exception("APITimeoutError: request timed out")
            return "fallback succeeded"

        mock_call.side_effect = side
        result = execute_with_fallback(_model(), "sys", "user", task_type="t")
        self.assertEqual(result, "fallback succeeded")
        self.assertEqual(attempt[0], 2)

    @patch("routing.model_registry.fallback_chain")
    @patch("routing.model_router.ModelRouter.call_model")
    def test_second_fallback_model_used_after_two_failures(self, mock_call, mock_chain):
        m2 = _model("sonnet")
        m3 = _model("opus")
        mock_chain.return_value = [m2, m3]
        attempt = [0]

        def side(*args, **kw):
            attempt[0] += 1
            if attempt[0] < 3:
                raise Exception("APIStatusError: 529 overloaded")
            return "third model success"

        mock_call.side_effect = side
        result = execute_with_fallback(_model(), "sys", "user", task_type="t")
        self.assertEqual(result, "third model success")
        self.assertEqual(attempt[0], 3)


class TestFallbackPolicyNonRetryable(unittest.TestCase):
    # Policy checks type(e).__name__ — must use exception with matching class name.

    @patch("routing.model_registry.fallback_chain", return_value=[_model("sonnet")])
    @patch("routing.model_router.ModelRouter.call_model")
    def test_auth_error_aborts_immediately(self, mock_call, _):
        AuthenticationError = type("AuthenticationError", (Exception,), {})
        mock_call.side_effect = AuthenticationError("invalid api-key")
        result = execute_with_fallback(_model(), "sys", "user", task_type="t")
        self.assertEqual(result, FALLBACK_RESPONSE)
        self.assertEqual(mock_call.call_count, 1)

    @patch("routing.model_registry.fallback_chain", return_value=[_model("sonnet")])
    @patch("routing.model_router.ModelRouter.call_model")
    def test_permission_error_aborts_immediately(self, mock_call, _):
        PermissionDeniedError = type("PermissionDeniedError", (Exception,), {})
        mock_call.side_effect = PermissionDeniedError("forbidden")
        result = execute_with_fallback(_model(), "sys", "user", task_type="t")
        self.assertEqual(result, FALLBACK_RESPONSE)
        self.assertEqual(mock_call.call_count, 1)


class TestFallbackPolicyExhausted(unittest.TestCase):

    @patch("routing.model_registry.fallback_chain", return_value=[])
    @patch("routing.model_router.ModelRouter.call_model")
    def test_single_model_exhausted_returns_fallback(self, mock_call, _):
        mock_call.side_effect = Exception("APIConnectionError: connection failed")
        result = execute_with_fallback(_model(), "sys", "user", task_type="t")
        self.assertEqual(result, FALLBACK_RESPONSE)

    @patch("routing.model_registry.fallback_chain")
    @patch("routing.model_router.ModelRouter.call_model")
    def test_all_three_models_exhausted(self, mock_call, mock_chain):
        mock_chain.return_value = [_model("sonnet"), _model("opus")]
        mock_call.side_effect = Exception("InternalServerError: 500")
        result = execute_with_fallback(_model(), "sys", "user", task_type="t")
        self.assertEqual(result, FALLBACK_RESPONSE)
        self.assertEqual(mock_call.call_count, 3)

    def test_fallback_response_is_hebrew_string(self):
        self.assertIn("שגיאה", FALLBACK_RESPONSE)
        self.assertIsInstance(FALLBACK_RESPONSE, str)
        self.assertTrue(len(FALLBACK_RESPONSE) > 10)


class TestFallbackEventEmission(unittest.TestCase):

    @patch("routing.model_registry.fallback_chain")
    @patch("routing.model_router.ModelRouter.call_model")
    def test_fallback_event_emitted_on_retry(self, mock_call, mock_chain):
        """MODEL_FALLBACK_TRIGGERED published when fallback chain triggered."""
        mock_chain.return_value = [_model("sonnet")]
        attempt = [0]

        def side(*a, **kw):
            attempt[0] += 1
            if attempt[0] == 1:
                raise Exception("RateLimitError: quota exceeded")
            return "ok"

        mock_call.side_effect = side

        published = []
        with patch("events.event_bus.event_bus") as mock_bus:
            mock_bus.publish = lambda event_type, **kw: published.append(event_type)
            execute_with_fallback(_model(), "sys", "user", task_type="t")

        import events.event_types as ET
        self.assertIn(ET.MODEL_FALLBACK_TRIGGERED, published,
                      f"MODEL_FALLBACK_TRIGGERED not published; saw: {published}")

    @patch("routing.model_registry.fallback_chain", return_value=[])
    @patch("routing.model_router.ModelRouter.call_model")
    def test_no_fallback_event_on_success(self, mock_call, _):
        mock_call.return_value = "ok"
        published = []
        with patch("events.event_bus.event_bus") as mock_bus:
            mock_bus.publish = lambda et, **kw: published.append(et)
            execute_with_fallback(_model(), "sys", "user", task_type="t")
        import events.event_types as ET
        self.assertNotIn(ET.MODEL_FALLBACK_TRIGGERED, published)


if __name__ == "__main__":
    unittest.main(verbosity=2)
