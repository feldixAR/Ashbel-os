"""
MetricsCollector — in-memory metrics for agent calls, leads, stage changes.
Exposed via GET /api/system/metrics.
Flushed to memory/sessions/ every hour via scheduler.
"""
import datetime
import threading
import pathlib

_lock    = threading.Lock()
_metrics: dict = {}
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


def _get(key: str) -> dict:
    return _metrics.setdefault(key, {
        "calls": 0, "successes": 0, "failures": 0,
        "total_tokens": 0, "total_duration_ms": 0,
    })


def record_agent_call(agent: str, success: bool,
                      tokens: int = 0, duration_ms: int = 0) -> None:
    with _lock:
        d = _get(f"agent:{agent}")
        d["calls"]             += 1
        d["successes" if success else "failures"] += 1
        d["total_tokens"]      += tokens
        d["total_duration_ms"] += duration_ms


def record_lead_touch(lead_id: str) -> None:
    with _lock:
        _get("leads")["calls"] += 1


def record_stage_change(lead_id: str, from_s: str, to_s: str) -> None:
    with _lock:
        _get("stage_changes")["calls"] += 1


def snapshot() -> dict:
    with _lock:
        out = {}
        for k, v in _metrics.items():
            avg_t = (v["total_tokens"] // v["calls"]) if v["calls"] else 0
            avg_d = (v["total_duration_ms"] // v["calls"]) if v["calls"] else 0
            out[k] = {**v, "avg_tokens": avg_t, "avg_duration_ms": avg_d}
        return out


def flush_to_session() -> None:
    try:
        sessions_dir = _REPO_ROOT / "memory" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today().isoformat()
        ts    = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
        data  = snapshot()
        if not data:
            return
        lines = [f"\n## {ts} UTC — MetricsCollector flush\n"]
        for k, v in data.items():
            lines.append(f"- {k}: calls={v['calls']} ok={v['successes']} fail={v['failures']}\n")
        with open(sessions_dir / f"{today}.md", "a", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception:
        pass
