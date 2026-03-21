"""
ModelRegistry — wraps config/models.py.

Single source of truth for model metadata, task-type mapping,
and fallback chains. No business logic here — pure lookup.

All other routing modules import from here, never from config/models.py directly.
"""

import logging
from typing import Optional

from config.models import (
    MODEL_REGISTRY,
    TASK_MODEL_MAP,
    FALLBACK_CHAIN,
    DEFAULT_MODEL_KEY,
    ModelConfig,
)

log = logging.getLogger(__name__)


def get_model(model_key: str) -> Optional[ModelConfig]:
    """Return ModelConfig for a key, or None if unknown."""
    return MODEL_REGISTRY.get(model_key)


def get_default() -> ModelConfig:
    return MODEL_REGISTRY[DEFAULT_MODEL_KEY]


def model_for_task(task_type: str) -> ModelConfig:
    """Return the preferred model for a task_type."""
    key = TASK_MODEL_MAP.get(task_type, DEFAULT_MODEL_KEY)
    return MODEL_REGISTRY.get(key, MODEL_REGISTRY[DEFAULT_MODEL_KEY])


def fallback_chain(model_key: str) -> list[ModelConfig]:
    """
    Return ordered list of fallback ModelConfigs for a given model_key.
    Returns empty list if no fallbacks defined.
    """
    keys = FALLBACK_CHAIN.get(model_key, [])
    return [MODEL_REGISTRY[k] for k in keys if k in MODEL_REGISTRY]


def model_for_priority(priority: str) -> ModelConfig:
    """
    Return the best model for a given priority string.
        quality  → highest quality_score
        speed    → highest speed_score
        cost     → lowest cost_per_1k_input
        balanced → uses task mapping (caller should call model_for_task instead)
    """
    models = list(MODEL_REGISTRY.values())
    if priority == "quality":
        return max(models, key=lambda m: m.quality_score)
    if priority == "speed":
        return max(models, key=lambda m: m.speed_score)
    if priority == "cost":
        return min(models, key=lambda m: m.cost_per_1k_input)
    return MODEL_REGISTRY[DEFAULT_MODEL_KEY]


def all_models() -> list[ModelConfig]:
    return list(MODEL_REGISTRY.values())
