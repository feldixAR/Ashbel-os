"""
GitHubWriterAgent — writes generated files to GitHub repository.

Handles:
    (development, apply_files)
"""

import os
import json
import base64
import logging
import urllib.request
import urllib.error

from services.storage.models.task import TaskModel
from services.execution.result  import ExecutionResult
from agents.base.base_agent import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("development", "apply_files"),
}


class GitHubWriterAgent(BaseAgent):
    agent_id = "builtin_github_writer_agent_v1"
    name = "GitHub Writer Agent"
    department = "executive"
    version = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[GitHubWriterAgent] error task={task.id}: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                message=f"שגיאה בכתיבה ל־GitHub: {e}",
                output={"error": str(e)},
            )

    def _run(self, task: TaskModel) -> ExecutionResult:
        payload = task.input_data or {}
        params = payload.get("params", {}) or {}
        files = params.get("files", []) or []
        commit_message = params.get("commit_message") or "Update project files via GitHub Writer Agent"

        if not files:
            return ExecutionResult(
                success=False,
                message="לא התקבלו קבצים לכתיבה",
                output={"error": "missing_files"},
            )

        token = os.getenv("GITHUB_TOKEN", "").strip()
        repo = os.getenv("GITHUB_REPO", "").strip()
        branch = os.getenv("GITHUB_BRANCH", "main").strip()

        if not token or not repo:
            return ExecutionResult(
                success=False,
                message="חסרים GITHUB_TOKEN או GITHUB_REPO",
                output={
                    "error": "missing_github_env",
                    "required_env": ["GITHUB_TOKEN", "GITHUB_REPO", "GITHUB_BRANCH"],
                },
            )

        written = []
        for item in files:
            path = item.get("path")
            content = item.get("content", "")
            if not path:
                continue

            result = self._upsert_file(
                token=token,
                repo=repo,
                branch=branch,
                path=path,
                content=content,
                commit_message=commit_message,
            )
            written.append(result)

        return ExecutionResult(
            success=True,
            message="הקבצים נשלחו ל־GitHub",
            output={
                "status": "github_write_completed",
                "repo": repo,
                "branch": branch,
                "written_files": written,
                "count": len(written),
            },
        )

    def _upsert_file(self, token: str, repo: str, branch: str, path: str, content: str, commit_message: str) -> dict:
        existing_sha = self._get_file_sha(token, repo, branch, path)

        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        body = {
            "message": commit_message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "branch": branch,
        }
        if existing_sha:
            body["sha"] = existing_sha

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "AshbalOS-GitHubWriter",
            },
            method="PUT",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)

        return {
            "path": path,
            "status": "updated" if existing_sha else "created",
            "sha": data.get("content", {}).get("sha"),
            "html_url": data.get("content", {}).get("html_url"),
        }

    def _get_file_sha(self, token: str, repo: str, branch: str, path: str):
        url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "AshbalOS-GitHubWriter",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                return data.get("sha")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
