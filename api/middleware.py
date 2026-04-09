"""
Middleware — API key authentication and request logging.

Usage:
    from api.middleware import require_auth

    @bp.route("/my-route")
    @require_auth
    def my_route():
        ...

Auth:
    Every request must include header: X-API-Key: <token>
    Token is compared against OS_API_KEY env var.
    Returns 401 if missing or invalid.
"""

import logging
import datetime
import functools
import os

from flask import request, jsonify, g

log = logging.getLogger(__name__)

def _norm_key(raw: str) -> str:
    """
    Normalize an API key value:
      1. strip surrounding whitespace and control characters
      2. strip surrounding single or double quotes
         (Railway dashboard sometimes stores values with literal quotes
          when pasted or set via CLI: e.g. "Ashbel2026" → Ashbel2026)
      3. strip again in case quotes had padding
    """
    k = raw.strip()
    if len(k) >= 2 and k[0] == k[-1] and k[0] in ('"', "'"):
        k = k[1:-1].strip()
    return k


def require_auth(fn):
    """Decorator — validates X-API-Key header before calling the route."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        # Read per-request: avoids module-import-time env var timing issue
        # (Gunicorn worker fork may not have env vars at import time)
        raw_server = os.getenv("OS_API_KEY", "")
        raw_client = request.headers.get("X-API-Key", "")

        api_key = _norm_key(raw_server)
        key     = _norm_key(raw_client)

        # ── Forensic debug (safe: logs lengths + masked repr, never full value) ──
        log.debug(
            f"[Auth] path={request.path} "
            f"client_len={len(key)} server_len={len(api_key)} "
            f"client_first={repr(key[:2]) if key else 'EMPTY'} "
            f"server_first={repr(api_key[:2]) if api_key else 'EMPTY'} "
            f"client_last={repr(key[-1:]) if key else 'EMPTY'} "
            f"server_last={repr(api_key[-1:]) if api_key else 'EMPTY'} "
            f"match={key == api_key}"
        )

        if not key or not api_key or key != api_key:
            log.warning(
                f"[Auth] REJECTED {request.method} {request.path} "
                f"client_len={len(key)} server_len={len(api_key)} "
                f"client_present={bool(key)} server_present={bool(api_key)} "
                f"raw_server_len={len(raw_server)} raw_client_len={len(raw_client)}"
            )
            return _error("unauthorized", 401)

        return fn(*args, **kwargs)
    return wrapper


def log_request(fn):
    """Decorator — logs method, path, and duration for every request."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = datetime.datetime.now(datetime.timezone.utc)
        result = fn(*args, **kwargs)
        ms = int((datetime.datetime.now(datetime.timezone.utc) - start).total_seconds() * 1000)
        log.info(f"[API] {request.method} {request.path} → {ms}ms")
        return result
    return wrapper


# ── Response helpers ──────────────────────────────────────────────────────────

def ok(data: dict = None, status: int = 200):
    return jsonify({
        "success": True,
        "data":    data or {},
        "error":   None,
        "ts":      _now(),
    }), status


def _error(message: str, status: int = 400):
    return jsonify({
        "success": False,
        "data":    None,
        "error":   message,
        "ts":      _now(),
    }), status


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
