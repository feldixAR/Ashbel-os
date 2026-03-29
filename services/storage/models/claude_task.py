"""
ClaudeTaskModel — audit record for every POST /api/claude/dispatch call.
One row per dispatch attempt; immutable after creation except for status fields.
"""
from sqlalchemy import Column, String, Boolean, Text, JSON
from .base import Base, TimestampMixin, new_uuid


class ClaudeTaskModel(Base, TimestampMixin):
    __tablename__ = "claude_tasks"

    # Identity
    id             = Column(String(36),  primary_key=True, default=new_uuid)

    # Payload (written once on creation)
    instruction    = Column(Text,         nullable=False)
    repo           = Column(String(300),  nullable=True)
    branch         = Column(String(120),  nullable=True)
    allowed_paths  = Column(JSON,         nullable=True)   # list[str]
    return_format  = Column(String(60),   nullable=True)

    # Approval gate
    approved       = Column(Boolean,      nullable=False, default=False)
    approved_at    = Column(String(40),   nullable=True)   # ISO-8601

    # Sensitive action flag (audited)
    sensitive      = Column(Boolean,      nullable=False, default=False)

    # Lifecycle
    status         = Column(String(30),   nullable=False, default="queued", index=True)
    # preview_pending | queued | rejected | dispatched | completed | failed
    dispatched_at  = Column(String(40),   nullable=True)   # ISO-8601
    completed_at   = Column(String(40),   nullable=True)   # ISO-8601

    # Preview plan (populated by /preview before execution)
    preview_plan   = Column(Text,         nullable=True)

    # Result fields (populated by adapter)
    summary        = Column(Text,         nullable=True)
    changed_files  = Column(JSON,         nullable=True)   # list[str]
    diff_available = Column(Boolean,      nullable=False, default=False)
    error          = Column(Text,         nullable=True)

    def to_response(self) -> dict:
        """Minimal public shape returned to callers."""
        return {
            "task_id":        self.id,
            "status":         self.status,
            "sensitive":      self.sensitive,
            "preview_plan":   self.preview_plan,
            "summary":        self.summary,
            "changed_files":  self.changed_files or [],
            "diff_available": self.diff_available,
            "error":          self.error,
        }

    def __repr__(self) -> str:
        return f"<ClaudeTask {self.id[:8]} [{self.status}]>"
