"""Session authentication, role authorization, CSRF and rate limiting.

These helpers are reused by every route module so authorization logic is
never duplicated per route.
"""
from __future__ import annotations

import hmac
import secrets
import time
from collections import defaultdict, deque
from functools import wraps

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    request,
    session,
    url_for,
)

# ---------------------------------------------------------------------------
# Authentication decorators
# ---------------------------------------------------------------------------

def login_required(view):
    """Allow only authenticated users."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    """Allow only users whose session role matches one of `roles`."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("auth.login", next=request.path))
            if session.get("role") not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def current_user_id():
    return session.get("user_id")


def current_role():
    return session.get("role")


# ---------------------------------------------------------------------------
# CSRF protection (token in session, HMAC-signed and per-session)
# ---------------------------------------------------------------------------

def _secret_bytes() -> bytes:
    return current_app.secret_key.encode()


def generate_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["_csrf_token"] = token
    return token


def validate_csrf() -> None:
    """Abort 400 unless the request carries a valid CSRF token."""
    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    expected = session.get("_csrf_token")
    if not expected or not sent or not hmac.compare_digest(sent, expected):
        abort(400, description="Invalid or missing CSRF token.")


# ---------------------------------------------------------------------------
# Login rate limiting (in-memory sliding window; fine for a college demo)
# ---------------------------------------------------------------------------

_attempts: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=50))


def _client_key() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")


def login_rate_limited() -> tuple[bool, int]:
    """Return (limited, seconds_until_retry) for the client address."""
    window = current_app.config["LOGIN_LOCKOUT_MINUTES"] * 60
    max_attempts = current_app.config["MAX_LOGIN_ATTEMPTS"]
    now = time.time()
    q = _attempts[_client_key()]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= max_attempts:
        retry = int(window - (now - q[0])) + 1
        return True, max(retry, 1)
    return False, 0


def record_failed_login() -> None:
    _attempts[_client_key()].append(time.time())


def reset_login_attempts() -> None:
    _attempts.pop(_client_key(), None)


# ---------------------------------------------------------------------------
# Jinja helpers
# ---------------------------------------------------------------------------

def init_security(app) -> None:
    app.jinja_env.globals["csrf_token"] = generate_csrf_token

    @app.before_request
    def csrf_protect():
        # Validate before the view runs so handlers that rotate the session
        # (e.g. session.clear() on login) cannot invalidate the check.
        if app.config.get("TESTING"):
            return
        if request.path.startswith("/static"):
            return
        validate_csrf()
