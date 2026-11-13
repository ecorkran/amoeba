"""``HandlePauseCall``: a run id and its absolute checkout (slice 226, D6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from amoeba.operations.handle_pause_call import HandlePauseCall


def test_a_run_id_starting_with_a_dash_is_accepted() -> None:
    call = HandlePauseCall.model_validate({"run_id": "-x", "directory": "/tmp/repo"})

    assert call.run_id == "-x"
    assert call.directory == Path("/tmp/repo")


def test_a_relative_directory_is_refused_naming_the_field() -> None:
    with pytest.raises(ValidationError, match="directory"):
        HandlePauseCall.model_validate({"run_id": "r", "directory": "repo"})


@pytest.mark.parametrize(
    "document",
    [
        {"directory": "/tmp/repo"},
        {"run_id": "r"},
        {"run_id": 5, "directory": "/tmp/repo"},
        {"run_id": "r", "directory": "/tmp/repo", "extra": 1},
    ],
    ids=["no-run-id", "no-directory", "run-id-not-a-string", "unknown-key"],
)
def test_a_document_that_is_not_a_run_and_a_directory_is_refused(
    document: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        HandlePauseCall.model_validate(document)
