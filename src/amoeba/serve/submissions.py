"""Submissions: ``POST`` through ``submit()`` with a required id, ``GET`` the outcome.

The server parses only the outer body shape (LLD D5). Everything inside
``payload`` is left to ``submit()``'s envelope check, so a network submission is
refused for exactly the reason a local one would be. A retry with the same id
is safe under 103's first-wins rule, which is why the id is required here.
"""

from __future__ import annotations

from functools import partial
from http import HTTPStatus
from pathlib import Path
from typing import Final

import anyio.to_thread
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from amoeba.inbox import submit
from amoeba.serve.errors import ApiError, ApiErrorCode
from amoeba.serve.reads import validated_project_id
from amoeba.serve.responses import json_response
from amoeba.serve.settings import ServeSettings
from amoeba.store import Store, SubmissionRecord, paths
from amoeba.store.inbox_models import SubmissionKind

#: The one missing field that has its own error code.
_SUBMISSION_ID: Final = "submission_id"


async def read_capped_body(request: Request, max_bytes: int) -> bytes:
    """The body, refused with 413 once it passes ``max_bytes``.

    A declared ``Content-Length`` over the cap is refused before reading.
    Otherwise chunks are read until one takes the total past the cap; no
    further chunk is read. The server does not choose the chunk size, so at
    most the cap plus that one chunk is held.
    """
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
        raise ApiError(
            ApiErrorCode.REQUEST_TOO_LARGE, f"the body may be at most {max_bytes} bytes"
        )
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise ApiError(
                ApiErrorCode.REQUEST_TOO_LARGE,
                f"the body may be at most {max_bytes} bytes",
            )
        chunks.append(chunk)
    return b"".join(chunks)


class SubmissionBody(BaseModel):
    """A POST body whose outer shape passed; ``payload`` is not yet checked."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    kind: SubmissionKind
    submission_id: str
    submitted_by: str
    payload: dict[str, object]


def parse_body(raw: bytes) -> SubmissionBody:
    """The outer shape, checked; ``payload`` is left to ``submit()``.

    Raises:
        ApiError: ``invalid_body`` or ``submission_id_required``.
    """
    try:
        return SubmissionBody.model_validate_json(raw)
    except ValidationError as error:
        problems = error.errors(include_url=False, include_input=False)
        if any(
            problem["loc"] == (_SUBMISSION_ID,) and problem["type"] == "missing"
            for problem in problems
        ):
            raise ApiError(
                ApiErrorCode.SUBMISSION_ID_REQUIRED,
                "a network submission must carry its own submission_id",
            ) from error
        # The input is left out of the detail: it is the client's payload.
        detail = "; ".join(
            f"{'.'.join(str(part) for part in problem['loc']) or 'body'}: "
            f"{problem['msg']}"
            for problem in problems
        )
        raise ApiError(ApiErrorCode.INVALID_BODY, detail) from error


def record_body(record: SubmissionRecord) -> dict[str, object]:
    """The outcome endpoint's fields (LLD D5)."""
    return {
        "id": record.id,
        "kind": record.kind.value,
        "outcome": record.outcome.value,
        "reason": record.reason,
        "submitted_by": record.submitted_by,
        "submitted_at": record.submitted_at.isoformat(),
        "applied_seq": record.applied_seq,
    }


def _lookup(store_dir: Path, project_id: str, submission_id: str) -> SubmissionRecord:
    """Blocking: the store read, on a worker thread. No store is not applied yet."""
    path = paths.project_store_path(store_dir, project_id)
    if path.is_file():
        with Store.open_read_only(path) as store:
            record = store.submission(submission_id)
        if record is not None:
            return record
    raise ApiError(
        ApiErrorCode.NOT_APPLIED, f"submission {submission_id!r} is not applied yet"
    )


def routes(settings: ServeSettings, store_dir: Path) -> list[Route]:
    """The two submission routes, closed over the settings and directory."""

    async def post(request: Request) -> Response:
        project_id = validated_project_id(str(request.path_params["project_id"]))
        body = parse_body(await read_capped_body(request, settings.max_request_bytes))
        submission_id = await anyio.to_thread.run_sync(
            partial(
                submit,
                project_id=project_id,
                kind=body.kind,
                payload=body.payload,
                submitted_by=body.submitted_by,
                submission_id=body.submission_id,
                store_dir=store_dir,
            )
        )
        return json_response({"submission_id": submission_id}, HTTPStatus.ACCEPTED)

    async def get(request: Request) -> Response:
        project_id = validated_project_id(str(request.path_params["project_id"]))
        submission_id = str(request.path_params["submission_id"])
        record = await anyio.to_thread.run_sync(
            partial(_lookup, store_dir, project_id, submission_id)
        )
        return json_response(record_body(record), HTTPStatus.OK)

    base = "/v1/projects/{project_id}/submissions"
    return [
        Route(base, post, methods=["POST"]),
        Route(base + "/{submission_id}", get, methods=["GET"]),
    ]
