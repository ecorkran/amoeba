"""``project_of`` parses the recorded ``cf get --json`` output (slice 222, D6, D11)."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from cf_fixtures import (
    DEFAULT_WORKTREE,
    NON_DEFAULT_WORKTREE,
    OUTSIDE_ANY_PROJECT,
    SUBDIRECTORY,
    fake_cf_run,
    fixture_document,
)

from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.project_of import (
    CFProject,
    CFProjectNotFound,
    project_of,
)

DIRECTORY = Path("/work/checkout")


def _project(fixture: str) -> CFProject:
    result = project_of(directory=DIRECTORY, run=fake_cf_run(fixture))
    assert isinstance(result, CFProject)
    return result


def test_the_default_worktree_gives_its_project() -> None:
    document = fixture_document(DEFAULT_WORKTREE)

    assert _project(DEFAULT_WORKTREE) == CFProject(
        id=document["id"], name=document["name"], project_path=document["projectPath"]
    )


def test_default_and_non_default_worktrees_have_the_same_id() -> None:
    default = _project(DEFAULT_WORKTREE)
    other = _project(NON_DEFAULT_WORKTREE)

    assert other.id == default.id
    assert other.project_path != default.project_path


def test_a_subdirectory_gives_the_roots_id() -> None:
    assert _project(SUBDIRECTORY).id == _project(DEFAULT_WORKTREE).id


def test_outside_any_project_gives_cfs_message() -> None:
    result = project_of(directory=DIRECTORY, run=fake_cf_run(OUTSIDE_ANY_PROJECT))

    assert result == CFProjectNotFound(
        message=fixture_document(OUTSIDE_ANY_PROJECT)["message"]
    )


@pytest.mark.parametrize("fixture", [None])
def test_a_failure_with_no_document_is_a_call_failure(fixture: str | None) -> None:
    result = project_of(directory=DIRECTORY, run=fake_cf_run(fixture))

    assert isinstance(result, CfCallFailed)
    assert "exited 1" in result.detail


def test_garbage_output_is_a_call_failure_quoting_it() -> None:
    def garbage(argv: Sequence[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(argv), 0, "<html>oops</html>", "")

    result = project_of(directory=DIRECTORY, run=garbage)

    assert isinstance(result, CfCallFailed)
    assert "<html>oops</html>" in result.detail


def test_a_document_without_an_id_is_a_call_failure() -> None:
    def partial_document(
        argv: Sequence[str], **_: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(argv), 0, '{"name": "x"}', "")

    assert isinstance(
        project_of(directory=DIRECTORY, run=partial_document), CfCallFailed
    )


def test_a_missing_executable_is_a_call_failure() -> None:
    def missing(argv: Sequence[str], **_: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("cf")

    assert isinstance(project_of(directory=DIRECTORY, run=missing), CfCallFailed)


def test_a_reference_passes_dash_p_and_the_reference() -> None:
    seen: list[tuple[list[str], dict[str, object]]] = []
    replay = fake_cf_run(DEFAULT_WORKTREE)

    def recording(argv: Sequence[str], **kwargs: object) -> object:
        seen.append((list(argv), kwargs))
        return replay(argv, **kwargs)

    result = project_of(reference="amoeba", run=recording)  # type: ignore[arg-type]

    assert isinstance(result, CFProject)
    argv, kwargs = seen[0]
    assert argv[argv.index("-p") + 1] == "amoeba"
    assert "cwd" not in kwargs


def test_a_directory_is_the_working_directory_of_the_call() -> None:
    seen: list[dict[str, object]] = []
    replay = fake_cf_run(DEFAULT_WORKTREE)

    def recording(argv: Sequence[str], **kwargs: object) -> object:
        seen.append(kwargs)
        return replay(argv, **kwargs)

    project_of(directory=DIRECTORY, run=recording)  # type: ignore[arg-type]

    assert seen[0]["cwd"] == DIRECTORY
    assert "-p" not in fake_cf_argv(DIRECTORY)


def fake_cf_argv(directory: Path) -> list[str]:
    captured: list[str] = []

    def run(argv: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.extend(argv)
        return fake_cf_run(DEFAULT_WORKTREE)(argv, **kwargs)

    project_of(directory=directory, run=run)
    return captured


def test_exactly_one_of_directory_and_reference_is_required() -> None:
    run = fake_cf_run(DEFAULT_WORKTREE)

    with pytest.raises(ValueError):
        project_of(run=run)
    with pytest.raises(ValueError):
        project_of(directory=DIRECTORY, reference="amoeba", run=run)
