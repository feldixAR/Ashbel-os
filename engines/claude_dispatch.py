"""
claude_dispatch.py — Detachable adapter: AshbelOS → Anthropic Messages API.

Sensitive action flow (governance-enforced):
  Intent → Preview (/api/claude/preview) → Approval → Execute (/api/claude/dispatch) → Audit Log

Non-sensitive actions may dispatch directly with approved=true.
Sensitive actions (sensitive=true) MUST pass through preview first.
"""
import json
import logging
import datetime
import os

from services.storage.repositories.claude_task_repo import ClaudeTaskRepository

log = logging.getLogger(__name__)
_repo = ClaudeTaskRepository()

_SYSTEM_PROMPT = """\
You are an execution assistant for AshbelOS (Ashbal Aluminum).
You receive a single instruction and optional repo/branch/allowed_paths context.
Respond with a JSON object only — no markdown, no explanation outside the object.

Schema:
{
  "summary":       "<one-paragraph description of what was done or what should be done>",
  "changed_files": ["<relative/path/file.py>", ...],
  "diff_available": false
}

Rules:
- If you cannot fulfill the instruction, set summary to explain why and changed_files to [].
- Never include keys outside the schema.
- Respect allowed_paths if provided: only reference files within those paths.
"""

_PREVIEW_SYSTEM_PROMPT = """\
You are a planning assistant for AshbelOS (Ashbal Aluminum).
You receive an instruction and optional context. Do NOT execute anything.
Describe only what you would do if asked to execute.
Respond with a JSON object only — no markdown, no explanation outside the object.

Schema:
{
  "preview_plan": "<step-by-step description of what would be done, what files would change, and why>"
}

Rules:
- Be specific: list file paths, functions, and logic changes you would make.
- Never include keys outside the schema.
- Respect allowed_paths if provided.
"""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"


# ── Public entry points ───────────────────────────────────────────────────────

def preview(payload: dict) -> dict:
    """
    Called by POST /api/claude/preview.
    Creates a task at status=preview_pending and returns the plan.
    No execution occurs.
    """
    instruction   = payload.get("instruction", "").strip()
    repo          = payload.get("repo")
    branch        = payload.get("branch")
    allowed_paths = payload.get("allowed_paths")
    return_format = payload.get("return_format")
    task_id       = payload.get("task_id")

    id_kwarg = {"id": task_id} if task_id else {}

    if not instruction:
        task = _repo.create(
            **id_kwarg,
            instruction="(empty)",
            repo=repo, branch=branch,
            allowed_paths=allowed_paths, return_format=return_format,
            sensitive=True, approved=False,
            status="failed", error="instruction is required",
        )
        return task.to_response()

    task = _repo.create(
        **id_kwarg,
        instruction=instruction,
        repo=repo, branch=branch,
        allowed_paths=allowed_paths, return_format=return_format,
        sensitive=True, approved=False,
        status="preview_pending",
    )

    try:
        result = _call_claude_preview(task)
        _repo.update(task.id, preview_plan=result.get("preview_plan"))
    except Exception as exc:
        log.exception(f"[Preview] provider error for {task.id}")
        _repo.update(task.id, status="failed", error=str(exc))

    return _repo.get(task.id).to_response()


def dispatch(payload: dict) -> dict:
    """
    Called by POST /api/claude/dispatch.

    Sensitive path  (sensitive=true):
      Requires task_id pointing to an existing preview_pending task.
      Advances that task to execution. No direct execute without prior preview.

    Non-sensitive path (sensitive absent or False):
      Existing behaviour unchanged — approved=true required, direct dispatch.
    """
    sensitive     = payload.get("sensitive") is True
    instruction   = payload.get("instruction", "").strip()
    repo          = payload.get("repo")
    branch        = payload.get("branch")
    allowed_paths = payload.get("allowed_paths")
    approved      = payload.get("approved")
    return_format = payload.get("return_format")
    task_id       = payload.get("task_id")

    # ── Sensitive path ────────────────────────────────────────────────────────
    if sensitive:
        if not task_id:
            return {"task_id": None, "status": "rejected", "sensitive": True,
                    "preview_plan": None, "summary": None, "changed_files": [],
                    "diff_available": False,
                    "error": "sensitive actions require a preview task_id"}

        task = _repo.get(task_id)
        if task is None:
            return {"task_id": task_id, "status": "rejected", "sensitive": True,
                    "preview_plan": None, "summary": None, "changed_files": [],
                    "diff_available": False,
                    "error": "preview task not found"}

        if task.status != "preview_pending":
            return {"task_id": task_id, "status": "rejected", "sensitive": True,
                    "preview_plan": task.preview_plan, "summary": None,
                    "changed_files": [], "diff_available": False,
                    "error": f"sensitive dispatch requires preview_pending task; current status: {task.status}"}

        # Approved — advance existing preview task to execution
        _repo.update(task.id, approved=True, approved_at=_now(), status="queued")
        return _execute(task.id)

    # ── Non-sensitive path (unchanged) ────────────────────────────────────────
    id_kwarg = {"id": task_id} if task_id else {}

    if approved is not True:
        task = _repo.create(
            **id_kwarg,
            instruction=instruction or "(none)",
            repo=repo, branch=branch,
            allowed_paths=allowed_paths, return_format=return_format,
            approved=False, sensitive=False,
            status="rejected", error="approved must be true to dispatch",
        )
        log.warning(f"[Dispatch] rejected {task.id}")
        return task.to_response()

    if not instruction:
        task = _repo.create(
            **id_kwarg,
            instruction="(empty)",
            repo=repo, branch=branch,
            allowed_paths=allowed_paths, return_format=return_format,
            approved=True, approved_at=_now(), sensitive=False,
            status="failed", error="instruction is required",
        )
        return task.to_response()

    task = _repo.create(
        **id_kwarg,
        instruction=instruction,
        repo=repo, branch=branch,
        allowed_paths=allowed_paths, return_format=return_format,
        approved=True, approved_at=_now(), sensitive=False,
        status="queued",
    )
    return _execute(task.id)


def get_task(task_id: str) -> dict | None:
    task = _repo.get(task_id)
    return task.to_response() if task else None


# ── Shared execution (used by both sensitive and non-sensitive paths) ─────────

def _execute(task_id: str) -> dict:
    _repo.update(task_id, status="dispatched", dispatched_at=_now())
    task = _repo.get(task_id)
    try:
        result = _call_claude_api(task)
        _repo.update(
            task_id,
            status="completed", completed_at=_now(),
            summary=result.get("summary"),
            changed_files=result.get("changed_files", []),
            diff_available=result.get("diff_available", False),
            error=None,
        )
        _notify_telegram(task_id, result.get("summary", ""))
    except Exception as exc:
        log.exception(f"[Dispatch] provider error for {task_id}")
        _repo.update(task_id, status="failed", completed_at=_now(), error=str(exc))
    return _repo.get(task_id).to_response()


# ── Provider calls — isolated boundaries ─────────────────────────────────────

def _notify_telegram(task_id: str, summary: str) -> None:
    """Send Wave One Telegram notification on task completion. Fails silently."""
    try:
        from services.telegram_service import telegram_service
        task = _repo.get(task_id)
        source = getattr(task, "orchestration_source", None) or "direct"
        text = (
            f"✅ *AshbelOS Task Complete*\n"
            f"Source: `{source}`\n"
            f"Task: `{task_id[:8]}`\n"
            f"Summary: {summary[:300] if summary else '—'}"
        )
        telegram_service.send(text)
    except Exception:
        log.debug("[Dispatch] Telegram notification skipped (not configured or failed)")


def _call_claude_api(task) -> dict:
    """Real Anthropic call for execution. Swap body only for filesystem SDK."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY env var is not set")

    client = anthropic.Anthropic(api_key=api_key)
    log.info(f"[Dispatch] calling Anthropic API for task {task.id[:8]}")
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(task)}],
    )
    return _parse_response(message.content[0].text.strip())


def _call_claude_preview(task) -> dict:
    """Real Anthropic call for preview planning only — no execution."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY env var is not set")

    client = anthropic.Anthropic(api_key=api_key)
    log.info(f"[Preview] calling Anthropic API for task {task.id[:8]}")
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=_PREVIEW_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(task)}],
    )
    raw = message.content[0].text.strip()
    try:
        text = raw
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0].strip()
        data = json.loads(text)
        return {"preview_plan": str(data.get("preview_plan", raw))}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {"preview_plan": raw}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_user_message(task) -> str:
    parts = [f"Instruction: {task.instruction}"]
    if task.repo:
        parts.append(f"Repo: {task.repo}")
    if task.branch:
        parts.append(f"Branch: {task.branch}")
    if task.allowed_paths:
        parts.append(f"Allowed paths: {', '.join(task.allowed_paths)}")
    return "\n".join(parts)


def _parse_response(raw: str) -> dict:
    try:
        text = raw
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0].strip()
        data = json.loads(text)
        return {
            "summary":        str(data.get("summary", "")),
            "changed_files":  [str(p) for p in data.get("changed_files", [])],
            "diff_available": bool(data.get("diff_available", False)),
        }
    except (json.JSONDecodeError, KeyError, TypeError):
        log.warning("[Dispatch] response was not valid JSON — using as plaintext summary")
        return {"summary": raw, "changed_files": [], "diff_available": False}
