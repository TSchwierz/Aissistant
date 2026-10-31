"""Required API key for every HTTP route.

The key is ``PA_API_KEY`` (``Settings.api_key``). Clients send it as
``Authorization: Bearer <key>`` or ``X-API-Token``. Both headers are the same
key. The query string is never consulted. Header values are not logged.
"""

from __future__ import annotations

import hmac
from collections.abc import Iterable

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from server.config import get_settings

_UNAUTHORIZED = {"detail": "Unauthorized"}
_BEARER = b"bearer "


def require_api_key() -> None:
    """Refuse startup when the configured key is missing or blank.

    An empty key is not open access.
    """
    if not get_settings().api_key.strip():
        raise RuntimeError(
            "PA_API_KEY must be set to a non-empty value before the server starts"
        )


def _header_pairs(scope: Scope) -> Iterable[tuple[bytes, bytes]]:
    headers = scope.get("headers") or ()
    return headers


def _is_cors_preflight(scope: Scope) -> bool:
    """Browser preflight carries no API key. It is not a data request."""
    if scope.get("method") != "OPTIONS":
        return False
    for name, _value in _header_pairs(scope):
        if name == b"access-control-request-method":
            return True
    return False


def _presented_tokens(scope: Scope) -> list[bytes]:
    tokens: list[bytes] = []
    for name, value in _header_pairs(scope):
        if name == b"x-api-token":
            tokens.append(value.strip())
        elif name == b"authorization":
            raw = value.strip()
            if len(raw) >= len(_BEARER) and raw[: len(_BEARER)].lower() == _BEARER:
                tokens.append(raw[len(_BEARER) :].strip())
    return tokens


def _matches(presented: bytes, expected: bytes) -> bool:
    try:
        return hmac.compare_digest(presented, expected)
    except Exception:
        return False


def _authorized(scope: Scope) -> bool:
    expected = get_settings().api_key.strip().encode("utf-8")
    if not expected:
        return False
    tokens = _presented_tokens(scope)
    if not tokens:
        return False
    return any(_matches(token, expected) for token in tokens)


class ApiKeyMiddleware:
    """ASGI middleware. Pure ASGI so mounted apps and streamed backups still work."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or _is_cors_preflight(scope):
            await self.app(scope, receive, send)
            return
        if _authorized(scope):
            await self.app(scope, receive, send)
            return
        response = JSONResponse(_UNAUTHORIZED, status_code=401)
        await response(scope, receive, send)


def install_api_key_middleware(app: Starlette) -> None:
    """Install the key check inside later middleware (add CORS after this)."""
    app.add_middleware(ApiKeyMiddleware)
