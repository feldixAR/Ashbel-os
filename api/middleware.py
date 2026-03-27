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
    Token is compared against API_KEY env var.
    Returns 401 if missing or invalid.
"""

import logging
import datetime
import functools
import os

from flask import request, jsonify, g

log = logging.getLogger(__name__)

# Accepts OS_API_KEY (preferred) or API_KEY (legacy Railway secret name).
_API_KEY = os.getenv("OS_API_KEY") or os.getenv("API_KEY") or ""


def require_auth(fn):
    """Decorator — validates X-API-Key header before calling the route."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if not key or not _API_KEY or key != _API_KEY:
            log.warning(f"[Auth] rejected {request.method} {request.path} "
                        f"from {request.remote_addr}")
            return _error("unauthorized", 401)
        return fn(*args, **kwargs)
    return wrapper


def log_request(fn):
    """Decorator — logs method, path, and duration for every request."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = datetime.datetime.utcnow()
        result = fn(*args, **kwargs)
        ms = int((datetime.datetime.utcnow() - start).total_seconds() * 1000)
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
    return datetime.datetime.utcnow().isoformat()
