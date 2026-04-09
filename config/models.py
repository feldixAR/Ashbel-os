"""
AI model registry — capabilities, cost, routing weights.
All routing decisions reference this file.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class ModelConfig:
    key:                str
    provider:           str          # "anthropic" | "openai"
    model_id:           str
    cost_per_1k_input:  float        # USD
    cost_per_1k_output: float        # USD
    quality_score:      int          # 1–10
    speed_score:        int          # 1–10
    context_window:     int          # tokens
    best_for:           List[str]    = field(default_factory=list)


MODEL_REGISTRY: dict[str, ModelConfig] = {
    "claude_opus": ModelConfig(
        key="claude_opus",
        provider="anthropic",
        model_id="claude-opus-4-6",
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        quality_score=10,
        speed_score=5,
        context_window=200000,
        best_for=["strategy", "legal", "agent_build",
                  "complex_reasoning", "contract", "analysis"],
    ),
    "claude_sonnet": ModelConfig(
        key="claude_sonnet",
        provider="anthropic",
        model_id="claude-sonnet-4-6",
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        quality_score=8,
        speed_score=7,
        context_window=200000,
        best_for=["sales", "marketing", "content",
                  "outreach", "seo", "followup"],
    ),
    "claude_haiku": ModelConfig(
        key="claude_haiku",
        provider="anthropic",
        model_id="claude-haiku-3-5-20251001",
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00125,
        quality_score=6,
        speed_score=10,
        context_window=200000,
        best_for=["classification", "crm", "scoring",
                  "short_response", "routing", "summarization"],
    ),
}

# Task type → preferred model key
TASK_MODEL_MAP: dict[str, str] = {
    "strategy":          "claude_opus",
    "legal":             "claude_opus",
    "agent_build":       "claude_opus",
    "complex_reasoning": "claude_opus",
    "contract":          "claude_opus",
    "analysis":          "claude_opus",
    "sales":             "claude_sonnet",
    "marketing":         "claude_sonnet",
    "content":           "claude_sonnet",
    "outreach":          "claude_sonnet",
    "seo":               "claude_sonnet",
    "followup":          "claude_sonnet",
    "classification":    "claude_haiku",
    "crm":               "claude_haiku",
    "scoring":           "claude_haiku",
    "short_response":    "claude_haiku",
    "routing":           "claude_haiku",
    "summarization":     "claude_haiku",
}

DEFAULT_MODEL_KEY  = "claude_haiku"
FALLBACK_MODEL_KEY = "claude_haiku"

# Fallback chain per model
FALLBACK_CHAIN: dict[str, list[str]] = {
    "claude_opus":   ["claude_sonnet", "claude_haiku"],
    "claude_sonnet": ["claude_haiku"],
    "claude_haiku":  [],
}
