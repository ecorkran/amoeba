"""The one error vocabulary (LLD D8): every code, and the only status numbers.

No route handler writes a status or a code string: handlers raise
:class:`ApiError`, or let a store, inbox, or inspection exception propagate,
and the app maps it here. ``tests/test_import_boundaries.py`` enforces that no
other module in ``amoeba.serve`` spells a code or an error status.

Every error body is ``{"error": <code>, "detail": <str>}``, with ``reason``
added only for ``invalid_submission``.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from http import HTTPStatus
from typing import Final

from starlette.responses import JSONResponse

from amoeba.inbox import SubmissionWriteError
from amoeba.inspection.evidence import VerdictNotComparableError
from amoeba.store import (
    StoreBusyError,
    StoreCorruptError,
    StorePermissionError,
    StoreSchemaError,
    VerdictNotFoundError,
)


class ApiErrorCode(StrEnum):
    """Every error the server returns. Closed: clients may switch on it."""

    # Reads
    UNKNOWN_LISTING = "unknown_listing"
    MISSING_PROJECT = "missing_project"
    UNEXPECTED_PARAMETER = "unexpected_parameter"
    INVALID_OPTION = "invalid_option"
    INVALID_PROJECT_ID = "invalid_project_id"
    UNKNOWN_PROJECT = "unknown_project"
    NOT_FOUND = "not_found"
    NOT_COMPARABLE = "not_comparable"
    # The store, on any endpoint that reads it
    STORE_BUSY = "store_busy"
    STORE_SCHEMA_MISMATCH = "store_schema_mismatch"
    STORE_UNREADABLE = "store_unreadable"
    # Submissions
    REQUEST_TOO_LARGE = "request_too_large"
    INVALID_BODY = "invalid_body"
    SUBMISSION_ID_REQUIRED = "submission_id_required"
    INVALID_SUBMISSION = "invalid_submission"
    SUBMISSION_WRITE_FAILED = "submission_write_failed"
    NOT_APPLIED = "not_applied"
    # The feed
    INVALID_CURSOR = "invalid_cursor"
    STREAM_LIMIT_REACHED = "stream_limit_reached"
    # Every request
    UNAUTHORIZED = "unauthorized"
    ORIGIN_NOT_ALLOWED = "origin_not_allowed"
    HOST_NOT_ALLOWED = "host_not_allowed"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    # The process-boundary handler
    INTERNAL_ERROR = "internal_error"


#: One status per code. The only place an HTTP status is chosen.
STATUS_BY_CODE: Final[Mapping[ApiErrorCode, int]] = {
    ApiErrorCode.UNKNOWN_LISTING: HTTPStatus.NOT_FOUND,
    ApiErrorCode.MISSING_PROJECT: HTTPStatus.BAD_REQUEST,
    ApiErrorCode.UNEXPECTED_PARAMETER: HTTPStatus.BAD_REQUEST,
    ApiErrorCode.INVALID_OPTION: HTTPStatus.BAD_REQUEST,
    ApiErrorCode.INVALID_PROJECT_ID: HTTPStatus.BAD_REQUEST,
    ApiErrorCode.UNKNOWN_PROJECT: HTTPStatus.NOT_FOUND,
    ApiErrorCode.NOT_FOUND: HTTPStatus.NOT_FOUND,
    ApiErrorCode.NOT_COMPARABLE: HTTPStatus.UNPROCESSABLE_ENTITY,
    ApiErrorCode.STORE_BUSY: HTTPStatus.SERVICE_UNAVAILABLE,
    ApiErrorCode.STORE_SCHEMA_MISMATCH: HTTPStatus.SERVICE_UNAVAILABLE,
    ApiErrorCode.STORE_UNREADABLE: HTTPStatus.SERVICE_UNAVAILABLE,
    ApiErrorCode.REQUEST_TOO_LARGE: HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
    ApiErrorCode.INVALID_BODY: HTTPStatus.UNPROCESSABLE_ENTITY,
    ApiErrorCode.SUBMISSION_ID_REQUIRED: HTTPStatus.UNPROCESSABLE_ENTITY,
    ApiErrorCode.INVALID_SUBMISSION: HTTPStatus.UNPROCESSABLE_ENTITY,
    ApiErrorCode.SUBMISSION_WRITE_FAILED: HTTPStatus.SERVICE_UNAVAILABLE,
    ApiErrorCode.NOT_APPLIED: HTTPStatus.NOT_FOUND,
    ApiErrorCode.INVALID_CURSOR: HTTPStatus.BAD_REQUEST,
    ApiErrorCode.STREAM_LIMIT_REACHED: HTTPStatus.SERVICE_UNAVAILABLE,
    ApiErrorCode.UNAUTHORIZED: HTTPStatus.UNAUTHORIZED,
    ApiErrorCode.ORIGIN_NOT_ALLOWED: HTTPStatus.FORBIDDEN,
    ApiErrorCode.HOST_NOT_ALLOWED: HTTPStatus.MISDIRECTED_REQUEST,
    ApiErrorCode.UNSUPPORTED_MEDIA_TYPE: HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
    ApiErrorCode.INTERNAL_ERROR: HTTPStatus.INTERNAL_SERVER_ERROR,
}

#: Codes whose response says when to try again.
RETRY_AFTER_CODES: Final = frozenset(
    {ApiErrorCode.STORE_BUSY, ApiErrorCode.STREAM_LIMIT_REACHED}
)

#: The ``Retry-After`` value, in seconds, for :data:`RETRY_AFTER_CODES`.
RETRY_AFTER_SECONDS: Final = 5

#: The ``WWW-Authenticate`` challenge sent with ``unauthorized``.
AUTH_CHALLENGE: Final = "Bearer"

#: Exceptions raised below the server, by type, and the code each becomes.
#: ``InvalidSubmissionError`` is not here: its handler adds ``reason``.
CODE_BY_EXCEPTION: Final[Mapping[type[Exception], ApiErrorCode]] = {
    StoreBusyError: ApiErrorCode.STORE_BUSY,
    StoreSchemaError: ApiErrorCode.STORE_SCHEMA_MISMATCH,
    StorePermissionError: ApiErrorCode.STORE_UNREADABLE,
    StoreCorruptError: ApiErrorCode.STORE_UNREADABLE,
    VerdictNotFoundError: ApiErrorCode.NOT_FOUND,
    VerdictNotComparableError: ApiErrorCode.NOT_COMPARABLE,
    SubmissionWriteError: ApiErrorCode.SUBMISSION_WRITE_FAILED,
}


def code_for_exception(error: Exception) -> ApiErrorCode:
    """The code for an exception in :data:`CODE_BY_EXCEPTION`, by its class or a base.

    Raises:
        KeyError: If no class in the exception's MRO is in the table.
    """
    for cls in type(error).__mro__:
        if cls in CODE_BY_EXCEPTION:
            return CODE_BY_EXCEPTION[cls]
    raise KeyError(f"{type(error).__name__} is not in CODE_BY_EXCEPTION")


class ApiError(Exception):
    """A request the server refuses. Raised by handlers; mapped by the app."""

    def __init__(
        self, code: ApiErrorCode, detail: str, *, reason: str | None = None
    ) -> None:
        super().__init__(f"{code.value}: {detail}")
        self.code = code
        self.detail = detail
        self.reason = reason


def error_body(
    code: ApiErrorCode, detail: str, reason: str | None = None
) -> dict[str, str]:
    """The JSON body for one error.

    Raises:
        ValueError: If ``reason`` is given for any code but
            ``invalid_submission``, or missing for it.
    """
    if (reason is not None) != (code is ApiErrorCode.INVALID_SUBMISSION):
        raise ValueError(f"reason is required for, and only for, {code.value!r}")
    body = {"error": code.value, "detail": detail}
    if reason is not None:
        body["reason"] = reason
    return body


def error_headers(code: ApiErrorCode) -> dict[str, str]:
    """The headers an error carries: a challenge, or when to retry."""
    headers: dict[str, str] = {}
    if code is ApiErrorCode.UNAUTHORIZED:
        headers["WWW-Authenticate"] = AUTH_CHALLENGE
    if code in RETRY_AFTER_CODES:
        headers["Retry-After"] = str(RETRY_AFTER_SECONDS)
    return headers


def error_response(
    code: ApiErrorCode, detail: str, reason: str | None = None
) -> JSONResponse:
    """The full response for one error."""
    return JSONResponse(
        error_body(code, detail, reason),
        status_code=STATUS_BY_CODE[code],
        headers=error_headers(code),
    )
