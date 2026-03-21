"""Trace repository."""
import json
from typing import Optional
from services.storage.db import get_session
from services.storage.models.trace import TraceModel
from .base_repo import utcnow_iso


class TraceRepository:

    def open_trace(self, trace_id: str, command: str = "",
                    task_id: str = None) -> TraceModel:
        from services.storage.models.base import new_uuid
        trace = TraceModel(
            id=new_uuid(), trace_id=trace_id,
            task_id=task_id, command=command,
            spans=[], status="open",
            created_at=utcnow_iso(),
        )
        with get_session() as s:
            s.add(trace)
        return trace

    def add_span(self, trace_id: str, span: dict) -> None:
        with get_session() as s:
            trace = (s.query(TraceModel)
                     .filter_by(trace_id=trace_id)
                     .first())
            if trace:
                spans = list(trace.spans or [])
                spans.append(span)
                trace.spans = spans

    def close_trace(self, trace_id: str, duration_ms: int) -> None:
        with get_session() as s:
            trace = (s.query(TraceModel)
                     .filter_by(trace_id=trace_id)
                     .first())
            if trace:
                trace.status      = "closed"
                trace.duration_ms = duration_ms
                trace.closed_at   = utcnow_iso()

    def get(self, trace_id: str) -> Optional[TraceModel]:
        with get_session() as s:
            return (s.query(TraceModel)
                    .filter_by(trace_id=trace_id)
                    .first())
