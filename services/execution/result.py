"""
result.py — ExecutionResult dataclass.
Separated from executor.py to avoid circular import issues at module load time.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExecutionResult:
    success:     bool
    message:     str
    output:      dict          = field(default_factory=dict)
    model_used:  Optional[str] = None
    cost_usd:    float         = 0.0
    duration_ms: int           = 0

    def to_dict(self) -> dict:
        return {
            "success":     self.success,
            "message":     self.message,
            "output":      self.output,
            "model_used":  self.model_used,
            "cost_usd":    self.cost_usd,
            "duration_ms": self.duration_ms,
        }
