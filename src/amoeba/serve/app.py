"""``build_app``: the routes, and the mapping from every exception to a response.

The supervisor directory is resolved once by the caller and passed in; the app
never reads the environment.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response

from amoeba.serve import reads
from amoeba.serve.auth import RequestGuardMiddleware
from amoeba.serve.errors import (
    CODE_BY_EXCEPTION,
    ApiError,
    ApiErrorCode,
    error_response,
)
from amoeba.serve.policy import is_loopback
from amoeba.serve.settings import ServeSettings

logger = logging.getLogger(__name__)

type _Handler = Callable[[Request, Exception], Awaitable[Response]]


async def _api_error(request: Request, exc: Exception) -> Response:
    """A refusal a handler raised, already carrying its code."""
    if not isinstance(exc, ApiError):
        raise TypeError(f"_api_error registered for {type(exc).__name__}")
    return error_response(exc.code, exc.detail, exc.reason)


async def _mapped_error(request: Request, exc: Exception) -> Response:
    """A store, inbox, or inspection exception in :data:`CODE_BY_EXCEPTION`."""
    code = next(
        CODE_BY_EXCEPTION[cls] for cls in type(exc).__mro__ if cls in CODE_BY_EXCEPTION
    )
    return error_response(code, str(exc))


async def _internal_error(request: Request, exc: Exception) -> Response:
    """The server's one process-boundary handler: anything not mapped above.

    Logged with the traceback and returned as ``internal_error``, with no detail
    from the exception, which may name internals. Starlette re-raises the
    exception after sending this response, so uvicorn logs it too.
    """
    logger.exception("unhandled error serving %s %s", request.method, request.url.path)
    return error_response(ApiErrorCode.INTERNAL_ERROR, "internal error")


def _exception_handlers() -> Mapping[type[Exception], _Handler]:
    handlers: dict[type[Exception], _Handler] = {ApiError: _api_error}
    handlers.update(dict.fromkeys(CODE_BY_EXCEPTION, _mapped_error))
    handlers[Exception] = _internal_error
    return handlers


def build_app(settings: ServeSettings, token: str | None, store_dir: Path) -> Starlette:
    """The server application over the supervisor directory ``store_dir``.

    Args:
        settings: The serve tunables.
        token: The bearer token, or ``None`` when unset.
        store_dir: The supervisor directory, resolved once by the caller.
    """
    guard = Middleware(
        RequestGuardMiddleware, token=token, loopback=is_loopback(settings.host)
    )
    return Starlette(
        routes=[*reads.routes(store_dir)],
        middleware=[guard],
        exception_handlers=dict(_exception_handlers()),
    )
