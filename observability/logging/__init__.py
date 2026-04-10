"""
StructuredLogger — structured logging with IL timestamp, Telegram alerts on ERROR+.
Writes to memory/sessions/YYYY-MM-DD.md.
"""
import datetime
import logging
import pathlib

log = logging.getLogger(__name__)
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


class StructuredLogger:

    def __init__(self, agent_name: str = "system"):
        self._agent = agent_name

    def _log(self, level: str, action: str, lead_id: str = "",
             result: str = "", duration_ms: int = 0, **extra) -> None:
        now_il = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        getattr(log, level.lower(), log.info)(
            f"[{self._agent}] {action} lead={lead_id} result={result} {duration_ms}ms"
        )
        self._write_session(level, action, lead_id, result, duration_ms)
        if level in ("ERROR", "CRITICAL"):
            self._telegram_alert(level, action, result)

    def info(self, action: str, **kw):     self._log("INFO",     action, **kw)
    def warning(self, action: str, **kw):  self._log("WARNING",  action, **kw)
    def error(self, action: str, **kw):    self._log("ERROR",    action, **kw)
    def critical(self, action: str, **kw): self._log("CRITICAL", action, **kw)

    def _write_session(self, level: str, action: str, lead_id: str,
                       result: str, duration_ms: int) -> None:
        try:
            sessions_dir = _REPO_ROOT / "memory" / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            today = datetime.date.today().isoformat()
            ts    = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
            line  = (f"- {ts} [{level}] {self._agent} | {action}"
                     f" | lead={lead_id} | {result} | {duration_ms}ms\n")
            with open(sessions_dir / f"{today}.md", "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def _telegram_alert(self, level: str, action: str, result: str) -> None:
        try:
            from services.telegram_service import telegram_service
            telegram_service.send(
                f"🚨 *{level}* — {self._agent}\n`{action}`\n{result[:200]}"
            )
        except Exception:
            pass


def get_logger(agent_name: str) -> StructuredLogger:
    return StructuredLogger(agent_name)
