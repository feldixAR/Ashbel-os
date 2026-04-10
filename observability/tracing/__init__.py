"""
TraceStore — link trace_id across intent → task → agent → result.
Stores in memory/sessions/. Exposed via GET /api/system/traces/{trace_id}.
"""
import datetime
import threading
import pathlib
import json

_lock   = threading.Lock()
_traces: dict = {}  # trace_id → list of events
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


def record(trace_id: str, stage: str, detail: dict) -> None:
    if not trace_id:
        return
    event = {
        "ts":    datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "stage": stage,
        **detail,
    }
    with _lock:
        _traces.setdefault(trace_id, []).append(event)

    # Also write to sessions
    try:
        sessions_dir = _REPO_ROOT / "memory" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today().isoformat()
        line  = f"- trace:{trace_id[:8]} [{stage}] {json.dumps(detail, ensure_ascii=False)[:120]}\n"
        with open(sessions_dir / f"{today}.md", "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def get(trace_id: str) -> list:
    with _lock:
        return list(_traces.get(trace_id, []))


def all_traces() -> dict:
    with _lock:
        return {k: list(v) for k, v in _traces.items()}
