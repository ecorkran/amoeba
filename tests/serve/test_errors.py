"""The API error vocabulary: one status per code, and the exception table."""

from __future__ import annotations

import json

import pytest

from amoeba.inbox import SubmissionWriteError
from amoeba.inspection.evidence import VerdictNotComparableError
from amoeba.serve.errors import (
    CODE_BY_EXCEPTION,
    RETRY_AFTER_CODES,
    RETRY_AFTER_SECONDS,
    STATUS_BY_CODE,
    ApiError,
    ApiErrorCode,
    error_body,
    error_response,
)
from amoeba.store import (
    StoreBusyError,
    StoreCorruptError,
    StorePermissionError,
    StoreSchemaError,
    VerdictNotFoundError,
)


def test_every_code_has_a_status() -> None:
    assert set(STATUS_BY_CODE) == set(ApiErrorCode)


@pytest.mark.parametrize(
    ("exception", "code", "status"),
    [
        (StoreBusyError, ApiErrorCode.STORE_BUSY, 503),
        (StoreSchemaError, ApiErrorCode.STORE_SCHEMA_MISMATCH, 503),
        (StorePermissionError, ApiErrorCode.STORE_UNREADABLE, 503),
        (StoreCorruptError, ApiErrorCode.STORE_UNREADABLE, 503),
        (VerdictNotFoundError, ApiErrorCode.NOT_FOUND, 404),
        (VerdictNotComparableError, ApiErrorCode.NOT_COMPARABLE, 422),
        (SubmissionWriteError, ApiErrorCode.SUBMISSION_WRITE_FAILED, 503),
    ],
)
def test_each_exception_maps_to_its_code_and_status(
    exception: type[Exception], code: ApiErrorCode, status: int
) -> None:
    assert CODE_BY_EXCEPTION[exception] is code
    assert STATUS_BY_CODE[code] == status


def test_the_exception_table_has_exactly_these_entries() -> None:
    assert len(CODE_BY_EXCEPTION) == 7


def test_unauthorized_carries_a_bearer_challenge() -> None:
    response = error_response(ApiErrorCode.UNAUTHORIZED, "missing or wrong token")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "retry-after" not in response.headers


@pytest.mark.parametrize("code", sorted(RETRY_AFTER_CODES))
def test_retry_codes_carry_retry_after(code: ApiErrorCode) -> None:
    response = error_response(code, "later")

    assert response.headers["retry-after"] == str(RETRY_AFTER_SECONDS)
    assert "www-authenticate" not in response.headers


def test_retry_after_is_only_for_store_busy_and_stream_limit() -> None:
    assert RETRY_AFTER_CODES == {
        ApiErrorCode.STORE_BUSY,
        ApiErrorCode.STREAM_LIMIT_REACHED,
    }


def test_a_plain_error_body_is_exactly_error_and_detail() -> None:
    response = error_response(ApiErrorCode.UNKNOWN_LISTING, "no such listing")

    assert json.loads(bytes(response.body)) == {
        "error": "unknown_listing",
        "detail": "no such listing",
    }


def test_an_invalid_submission_body_adds_reason() -> None:
    body = error_body(ApiErrorCode.INVALID_SUBMISSION, "bad", reason="schema")

    assert body == {"error": "invalid_submission", "detail": "bad", "reason": "schema"}


def test_reason_is_refused_for_another_code() -> None:
    with pytest.raises(ValueError, match="reason"):
        error_body(ApiErrorCode.INVALID_BODY, "bad", reason="schema")


def test_invalid_submission_without_a_reason_is_refused() -> None:
    with pytest.raises(ValueError, match="reason"):
        error_body(ApiErrorCode.INVALID_SUBMISSION, "bad")


def test_api_error_carries_its_code_and_detail() -> None:
    error = ApiError(ApiErrorCode.MISSING_PROJECT, "project is required")

    assert error.code is ApiErrorCode.MISSING_PROJECT
    assert error.detail == "project is required"
    assert error.reason is None
