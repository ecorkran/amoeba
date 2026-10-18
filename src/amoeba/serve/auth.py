"""The request guard: Origin, Host, token, and content type (LLD D2).

A pure ASGI middleware rather than Starlette's ``BaseHTTPMiddleware``, which
wraps the response body and so sits badly in front of an SSE stream. It refuses
before routing, in a fixed order, and never logs a header.
"""

from __future__ import annotations

import hmac
from typing import Final

from starlette.types import ASGIApp, Receive, Scope, Send

from amoeba.serve.errors import ApiErrorCode, error_response
from amoeba.serve.reads import JSON_MEDIA_TYPE

#: The ``Host`` names a loopback bind accepts, with any port.
LOOPBACK_HOST_NAMES: Final = frozenset({"localhost", "127.0.0.1", "::1"})

_HTTP_SCOPE: Final = "http"
_POST: Final = "POST"
_BEARER_PREFIX: Final = b"Bearer "
_ORIGIN: Final = b"origin"
_HOST: Final = b"host"
_AUTHORIZATION: Final = b"authorization"
_CONTENT_TYPE: Final = b"content-type"


def host_name(host: str) -> str:
    """The name in a ``Host`` header, port stripped, ``[::1]`` brackets removed."""
    if host.startswith("["):
        return host[1 : host.find("]")] if "]" in host else host
    if host.count(":") == 1:
        return host.split(":", 1)[0]
    return host


def media_type(content_type: str) -> str:
    """The media type of a ``content-type`` value, without parameters (charset)."""
    return content_type.split(";", 1)[0].strip().lower()


class RequestGuardMiddleware:
    """Refuses a request that fails D2's checks; passes every other scope through.

    Order: ``Origin`` (403), then ``Host`` on a loopback bind (421), then the
    token (401), then a POST's content type (415).
    """

    def __init__(self, app: ASGIApp, *, token: str | None, loopback: bool) -> None:
        self._app = app
        self._expected = None if token is None else _BEARER_PREFIX + token.encode()
        self._loopback = loopback

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != _HTTP_SCOPE:
            await self._app(scope, receive, send)
            return
        refusal = self._refusal(scope)
        if refusal is None:
            await self._app(scope, receive, send)
            return
        code, detail = refusal
        await error_response(code, detail)(scope, receive, send)

    def _refusal(self, scope: Scope) -> tuple[ApiErrorCode, str] | None:
        headers = _headers(scope)
        if _ORIGIN in headers:
            return ApiErrorCode.ORIGIN_NOT_ALLOWED, "browser requests are not served"
        if self._loopback:
            name = host_name(headers.get(_HOST, b"").decode("latin-1")).lower()
            if name not in LOOPBACK_HOST_NAMES:
                return ApiErrorCode.HOST_NOT_ALLOWED, "host is not a loopback name"
        if self._expected is not None:
            provided = headers.get(_AUTHORIZATION, b"")
            if not hmac.compare_digest(provided, self._expected):
                return ApiErrorCode.UNAUTHORIZED, "a valid bearer token is required"
        if scope["method"] == _POST:
            content_type = headers.get(_CONTENT_TYPE, b"").decode("latin-1")
            if media_type(content_type) != JSON_MEDIA_TYPE:
                return (
                    ApiErrorCode.UNSUPPORTED_MEDIA_TYPE,
                    f"a request body must be {JSON_MEDIA_TYPE}",
                )
        return None


def _headers(scope: Scope) -> dict[bytes, bytes]:
    """Header names lowercased (ASGI already does); a repeated header keeps its last."""
    return {name.lower(): value for name, value in scope["headers"]}
