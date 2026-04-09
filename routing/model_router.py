"""
ModelRouter — stateless entry point for all AI calls.

Routing priority:
    1. priority override  ("quality" | "speed" | "cost")
    2. learning override  (from MemoryStore — set by learning engine)
    3. task_type mapping  (from config/models.py)

All actual API calls go through _call_anthropic().
Fallback chain is executed by fallback_policy.execute().

Usage:
    from routing.model_router import model_router

    text = model_router.call(
        task_type="sales",
        system_prompt="...",
        user_prompt="...",
        priority="balanced",   # optional
        max_tokens=400,        # optional
    )
"""

import logging
from typing import Optional

from routing.model_registry import model_for_task, model_for_priority, get_model
from config.models          import ModelConfig
from config.settings        import ANTHROPIC_API_KEY

log = logging.getLogger(__name__)


class ModelRouter:

    # ── Public entry point ────────────────────────────────────────────────────

    def call(
        self,
        task_type:     str,
        system_prompt: str,
        user_prompt:   str,
        priority:      str = "balanced",
        max_tokens:    int = 800,
    ) -> str:
        """
        Select the best model and execute the AI call.
        Returns the text response string.
        On total failure returns a fallback string (never raises).
        """
        model = self._select_model(task_type, priority)
        log.debug(f"[ModelRouter] task={task_type} priority={priority} "
                  f"→ {model.model_id}")

        from routing.fallback_policy import execute_with_fallback
        result = execute_with_fallback(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            task_type=task_type,
        )

        # Record cost
        self._record_cost(model, user_prompt, result)

        return result

    # ── Model selection ───────────────────────────────────────────────────────

    def _select_model(self, task_type: str, priority: str) -> ModelConfig:
        # 1. Priority override
        if priority in ("quality", "speed", "cost"):
            return model_for_priority(priority)

        # 2. Learning override (from MemoryStore)
        learning_key = self._get_learning_override(task_type)
        if learning_key:
            model = get_model(learning_key)
            if model:
                log.debug(f"[ModelRouter] learning override: {task_type} → {learning_key}")
                return model

        # 3. Task type mapping
        return model_for_task(task_type)

    def _get_learning_override(self, task_type: str) -> Optional[str]:
        try:
            from memory.memory_store import MemoryStore
            return MemoryStore.get_routing_override(task_type)
        except Exception:
            return None

    # ── Cost recording ────────────────────────────────────────────────────────

    def _record_cost(self, model: ModelConfig, prompt: str, result: str) -> None:
        try:
            from routing.cost_tracker import cost_tracker
            # Rough token estimate: 1 token ≈ 4 chars
            tokens_in  = max(1, len(prompt) // 4)
            tokens_out = max(1, len(result) // 4)
            cost_tracker.record(model.key, tokens_in, tokens_out,
                                 model.cost_per_1k_input,
                                 model.cost_per_1k_output)
        except Exception as e:
            log.debug(f"[ModelRouter] cost record skipped: {e}")

    # ── Direct model call (used by fallback_policy) ───────────────────────────

    def call_batch(
        self,
        task_type:     str,
        system_prompt: str,
        user_prompts:  list,
        priority:      str = "balanced",
        max_tokens:    int = 800,
    ) -> list:
        """
        Process up to 10 prompts per batch. Returns list of text responses.
        Uses the same model selection as call(). Reduces per-lead AI calls.
        """
        results = []
        for i in range(0, len(user_prompts), 10):
            batch = user_prompts[i:i + 10]
            for prompt in batch:
                results.append(self.call(
                    task_type=task_type,
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    priority=priority,
                    max_tokens=max_tokens,
                ))
        return results

    @staticmethod
    def call_model(model: ModelConfig, system_prompt: str,
                   user_prompt: str, max_tokens: int = 800,
                   use_cache: bool = False) -> str:
        """
        Direct call to a specific model. No routing, no fallback.
        Raises on failure — caller (fallback_policy) handles exceptions.
        use_cache=True adds cache_control to system prompt (prompt caching).
        """
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        if use_cache:
            system_block = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_block = system_prompt

        response = client.messages.create(
            model=model.model_id,
            max_tokens=max_tokens,
            system=system_block,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text


# ── Singleton ─────────────────────────────────────────────────────────────────
model_router = ModelRouter()
