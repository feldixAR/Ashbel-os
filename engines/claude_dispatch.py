"""
claude_dispatch.py — Detachable adapter: AshbelOS → Anthropic Messages API.

Fully implemented:
  - approval gate
  - task persistence + audit timestamps
  - task lifecycle: queued → dispatched → completed | failed
  - real Anthropic API call (_call_claude_api)
  - structured JSON response parsing with plaintext fallback
  - changed_files extracted from model response when returned

One remaining boundary (isolatable):
  - _call_claude_api() calls Anthropic Messages API (real).
    Actual file-system writes require Claude Code remote execution,
    which is not available via Messages API — changed_files are
    model-reported intent, not confirmed filesystem changes.
    When Claude Code SDK remote execution is available, replace
    only _call_claude_api() body. Contract is unchanged.
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
  "changed_files": ["<relative/path/file.py>", ...],  // files modified or that should be modified
  "diff_available": false
}

Rules:
- If you cannot fulfill the instruction, set summary to explain why and changed_files to [].
- Never include keys outside the schema.
- Respect allowed_paths if provided: only reference files within those paths.
"""


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


# ── Public entry points ───────────────────────────────────────────────────────

def dispatch(payload: dict) -> dict:
    """
    Called by POST /api/claude/dispatch.
    Returns dict matching ClaudeTaskModel.to_response().
    Never raises — all errors captured into the task record.
    """
    instruction   = payload.get("instruction", "").strip()
    repo          = payload.get("repo")
    branch        = payload.get("branch")
    allowed_paths = payload.get("allowed_paths")
    approved      = payload.get("approved")
    return_format = payload.get("return_format")
    task_id       = payload.get("task_id")

    id_kwarg = {"id": task_id} if task_id else {}

    # ── Approval gate ─────────────────────────────────────────────────────────
    if approved is not True:
        task = _repo.create(
            **id_kwarg,
            instruction=instruction or "(none)",
            repo=repo, branch=branch,
            allowed_paths=allowed_paths, return_format=return_format,
            approved=False, status="rejected",
            error="approved must be true to dispatch",
        )
        log.warning(f"[Dispatch] rejected {task.id}")
        return task.to_response()

    if not instruction:
        task = _repo.create(
            **id_kwarg,
            instruction="(empty)",
            repo=repo, branch=branch,
            allowed_paths=allowed_paths, return_format=return_format,
            approved=True, approved_at=_now(),
            status="failed", error="instruction is required",
        )
        return task.to_response()

    # ── Create audit record at queued ─────────────────────────────────────────
    task = _repo.create(
        **id_kwarg,
        instruction=instruction,
        repo=repo, branch=branch,
        allowed_paths=allowed_paths, return_format=return_format,
        approved=True, approved_at=_now(),
        status="queued",
    )

    # ── Advance to dispatched before provider call ────────────────────────────
    _repo.update(task.id, status="dispatched", dispatched_at=_now())

    # ── Provider call ─────────────────────────────────────────────────────────
    try:
        result = _call_claude_api(task)
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
        log.exception(f"[Dispatch] provider error for {task.id}")
        _repo.update(task.id, status="failed", completed_at=_now(), error=str(exc))

    return _repo.get(task.id).to_response()


def get_task(task_id: str) -> dict | None:
    task = _repo.get(task_id)
    return task.to_response() if task else None


# ── Provider call — isolated boundary ────────────────────────────────────────

def _call_claude_api(task) -> dict:
    """
    Real Anthropic Messages API call.

    Returns:
        summary       : str        — what was done / should be done
        changed_files : list[str]  — model-reported file paths
        diff_available: bool       — always False (Messages API, no filesystem)

    To wire actual filesystem execution: replace this function body only.
    When Claude Code remote SDK becomes available, swap body here — contract
    and all upstream/downstream code remain unchanged.
    """
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY env var is not set")

    user_content = _build_user_message(task)
    client = anthropic.Anthropic(api_key=api_key)

    log.info(f"[Dispatch] calling Anthropic API for task {task.id[:8]}")
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = message.content[0].text.strip()
    return _parse_response(raw)


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
    """Parse model JSON response; fall back to plaintext summary on failure."""
    try:
        # Strip accidental markdown fences
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
