"""
FallbackPolicy — executes an AI call with automatic model fallback.

execute_with_fallback():
    try primary model
        success  → return text
        retryable error (RateLimit, Server, Timeout)
            → emit MODEL_FALLBACK_TRIGGERED
            → try next model in fallback chain
        non-retryable error (AuthError, ContentPolicy)
            → raise immediately (no fallback)
    all models exhausted → return FALLBACK_RESPONSE string

Never raises to ModelRouter — always returns a string.
"""

import logging
import time
from typing import Optional

from config.models import ModelConfig

log = logging.getLogger(__name__)

# Returned when all models in the chain fail
FALLBACK_RESPONSE = "[שגיאה: לא ניתן לקבל תשובה מהמודל כרגע. נסה שוב מאוחר יותר.]"

# Errors that trigger fallback to next model
_RETRYABLE = ("RateLimitError", "APIStatusError", "APITimeoutError",
              "APIConnectionError", "InternalServerError")

# Errors that abort immediately without fallback
_NON_RETRYABLE = ("AuthenticationError", "PermissionDeniedError",
                  "InvalidRequestError")


def execute_with_fallback(
    model:         ModelConfig,
    system_prompt: str,
    user_prompt:   str,
    max_tokens:    int = 800,
    task_type:     str = "unknown",
) -> str:
    """
    Try model, then fallback chain if retryable error occurs.
    Returns text string. Never raises.
    """
    from routing.model_registry import fallback_chain
    from routing.model_router   import ModelRouter

    chain = [model] + fallback_chain(model.key)

    for i, current_model in enumerate(chain):
        try:
            text = ModelRouter.call_model(
                current_model, system_prompt, user_prompt, max_tokens)
            if i > 0:
                log.info(f"[Fallback] succeeded on fallback model "
                         f"{current_model.model_id} (attempt {i+1})")
            return text

        except Exception as e:
            error_type = type(e).__name__

            # Non-retryable — abort immediately
            if any(nr in error_type for nr in _NON_RETRYABLE):
                log.error(f"[Fallback] non-retryable error {error_type}: {e}")
                return FALLBACK_RESPONSE

            # Last in chain — give up
            if i == len(chain) - 1:
                log.error(f"[Fallback] all models exhausted. "
                          f"Last error: {error_type}: {e}")
                return FALLBACK_RESPONSE

            # Retryable — try next model
            next_model = chain[i + 1]
            log.warning(f"[Fallback] {current_model.model_id} failed "
                        f"({error_type}) → trying {next_model.model_id}")
            _emit_fallback_event(task_type, current_model.key,
                                  next_model.key, str(e))

            # Brief pause before fallback
            time.sleep(0.5)

    return FALLBACK_RESPONSE


def _emit_fallback_event(task_type: str, from_model: str,
                          to_model: str, error: str) -> None:
    try:
        from events.event_bus  import event_bus
        import events.event_types as ET
        event_bus.publish(
            ET.MODEL_FALLBACK_TRIGGERED,
            payload={
                "task_type":  task_type,
                "from_model": from_model,
                "to_model":   to_model,
                "error":      error[:200],
            },
        )
    except Exception as e:
        log.debug(f"[Fallback] could not emit event: {e}")
