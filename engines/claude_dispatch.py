"""
claude_dispatch.py — Detachable adapter between AshbelOS and Claude Code.

Fully implemented:
  - approval gate (rejects if approved != True)
  - task persistence (ClaudeTaskModel row created before any dispatch)
  - audit timestamps (approved_at, dispatched_at, completed_at)
  - structured response (status, summary, changed_files, diff_available, error)

Stubbed (replace with real SDK call when ready):
  - _call_claude_sdk(): currently returns a placeholder result dict.
    Replace the body of that function with the actual Anthropic / Claude Code
    SDK invocation without touching anything else.
"""
import logging
import datetime

from services.storage.repositories.claude_task_repo import ClaudeTaskRepository

log = logging.getLogger(__name__)
_repo = ClaudeTaskRepository()


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


# ── Public entry point ────────────────────────────────────────────────────────

def dispatch(payload: dict) -> dict:
    """
    Main entry point called by POST /api/claude/dispatch.

    Returns a dict matching ClaudeTaskModel.to_response().
    Raises nothing — all errors are captured into the task record.
    """
    instruction   = payload.get("instruction", "").strip()
    repo          = payload.get("repo")
    branch        = payload.get("branch")
    allowed_paths = payload.get("allowed_paths")
    approved      = payload.get("approved")
    return_format = payload.get("return_format")
    task_id       = payload.get("task_id")  # caller may supply a stable ID

    # ── Approval gate ─────────────────────────────────────────────────────────
    if approved is not True:
        task = _repo.create(
            **({"id": task_id} if task_id else {}),
            instruction=instruction or "(none)",
            repo=repo,
            branch=branch,
            allowed_paths=allowed_paths,
            return_format=return_format,
            approved=False,
            status="rejected",
            error="approved must be true to dispatch",
        )
        log.warning(f"[Dispatch] rejected {task.id} — approved not true")
        return task.to_response()

    # ── Create audit record ───────────────────────────────────────────────────
    if not instruction:
        task = _repo.create(
            **({"id": task_id} if task_id else {}),
            instruction="(empty)",
            repo=repo,
            branch=branch,
            allowed_paths=allowed_paths,
            return_format=return_format,
            approved=True,
            approved_at=_now(),
            status="failed",
            error="instruction is required",
        )
        return task.to_response()

    task = _repo.create(
        **({"id": task_id} if task_id else {}),
        instruction=instruction,
        repo=repo,
        branch=branch,
        allowed_paths=allowed_paths,
        return_format=return_format,
        approved=True,
        approved_at=_now(),
        status="dispatched",
        dispatched_at=_now(),
    )

    # ── Call adapter (stubbed) ────────────────────────────────────────────────
    try:
        result = _call_claude_sdk(task)
        _repo.update(
            task.id,
            status="completed",
            completed_at=_now(),
            summary=result.get("summary"),
            changed_files=result.get("changed_files", []),
            diff_available=result.get("diff_available", False),
            error=None,
        )
    except Exception as exc:
        log.exception(f"[Dispatch] adapter error for {task.id}")
        _repo.update(
            task.id,
            status="failed",
            completed_at=_now(),
            error=str(exc),
        )

    return _repo.get(task.id).to_response()


def get_task(task_id: str) -> dict | None:
    """Lookup by task_id. Returns None if not found."""
    task = _repo.get(task_id)
    return task.to_response() if task else None


# ── STUB — replace this function body with real SDK call ─────────────────────

def _call_claude_sdk(task) -> dict:
    """
    STUBBED.

    Replace this body with the real Claude Code / Anthropic SDK call.
    Contract: return a dict with keys:
        summary       : str   — human-readable description of what was done
        changed_files : list  — list of relative file paths modified
        diff_available: bool  — True if a diff can be retrieved separately
    Raise any exception on failure — the caller wraps it into task.error.
    """
    log.info(f"[Dispatch] stub executing task {task.id[:8]}")
    return {
        "summary":        f"[STUB] Received instruction: {task.instruction[:80]}",
        "changed_files":  [],
        "diff_available": False,
    }
