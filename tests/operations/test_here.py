"""The client part: caller and checkout gathered from a directory (slice 261, D5)."""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run, fixture_document
from git_repo import git, make_repo

from amoeba.operations import here
from amoeba.operations.errors import ContextForgeError
from amoeba.operations.here import gather_caller, gather_checkout, git_root
from amoeba.operations.here_document import (
    HereCaller,
    HereCheckout,
    HereNotAProject,
)
from amoeba.upstream.context_forge.cli_call import CfRun

PROJECT_ID = "project_1_a"
PROJECT_NAME = "forge"
SECRET = "hunter2-secret"


def _cf_for(path: Path) -> CfRun:
    """A ``cf`` whose ``get --json`` names the project at ``path``."""

    def run(argv: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        document = {"id": PROJECT_ID, "name": PROJECT_NAME, "projectPath": str(path)}
        return subprocess.CompletedProcess(list(argv), 0, json.dumps(document), "")

    return run


def _repo_with_origin(tmp_path: Path, address: str | None) -> Path:
    repo = make_repo(tmp_path / "repo")
    if address is not None:
        git(repo, "remote", "add", "origin", address)
    return repo


def _git_that_fails_if_called(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("git must not run")


def test_a_project_gives_the_caller(tmp_path: Path) -> None:
    caller = gather_caller(tmp_path, _cf_for(tmp_path))

    assert caller == HereCaller(project_id=PROJECT_ID)


def test_not_a_project_is_a_value_carrying_cfs_message(tmp_path: Path) -> None:
    caller = gather_caller(tmp_path, fake_cf_run(OUTSIDE_ANY_PROJECT))

    assert isinstance(caller, HereNotAProject)
    assert caller.not_a_project == fixture_document(OUTSIDE_ANY_PROJECT)["message"]


def test_a_cf_failure_raises(tmp_path: Path) -> None:
    with pytest.raises(ContextForgeError):
        gather_caller(tmp_path, fake_cf_run(None))
    with pytest.raises(ContextForgeError):
        gather_checkout(tmp_path, fake_cf_run(None), _git_that_fails_if_called)


@pytest.mark.parametrize(
    ("address", "reduced"),
    [
        ("git@github.com:Org/Forge.git", "github.com/org/forge"),
        ("https://github.com/org/forge/", "github.com/org/forge"),
        ("https://user:secret@host:8443/org/forge.git", "host:8443/org/forge"),
    ],
)
def test_the_checkout_carries_the_reduced_origin(
    tmp_path: Path, address: str, reduced: str
) -> None:
    repo = _repo_with_origin(tmp_path, address)

    checkout = gather_checkout(repo, _cf_for(repo), subprocess.run)

    assert checkout == HereCheckout(
        project_id=PROJECT_ID, name=PROJECT_NAME, path=str(repo), origin=reduced
    )


def test_a_password_is_in_no_field_and_no_log_record(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    repo = _repo_with_origin(tmp_path, f"https://user:{SECRET}@host/org/forge.git")

    with caplog.at_level(logging.DEBUG):
        checkout = gather_checkout(repo, _cf_for(repo), subprocess.run)

    assert isinstance(checkout, HereCheckout)
    assert SECRET not in checkout.model_dump_json()
    assert SECRET not in caplog.text


def test_a_repo_with_no_remote_has_a_null_origin(tmp_path: Path) -> None:
    repo = _repo_with_origin(tmp_path, None)

    checkout = gather_checkout(repo, _cf_for(repo), subprocess.run)

    assert isinstance(checkout, HereCheckout)
    assert checkout.origin is None


def test_an_address_with_no_host_is_a_null_origin(tmp_path: Path) -> None:
    repo = _repo_with_origin(tmp_path, "/srv/git/forge.git")

    checkout = gather_checkout(repo, _cf_for(repo), subprocess.run)

    assert isinstance(checkout, HereCheckout)
    assert checkout.origin is None


def test_a_path_that_is_no_repo_has_a_null_origin_and_runs_no_git(
    tmp_path: Path,
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    checkout = gather_checkout(plain, _cf_for(plain), _git_that_fails_if_called)

    assert isinstance(checkout, HereCheckout)
    assert checkout.origin is None


def _git_exiting(code: int, stderr: str) -> CfRun:
    def run(argv: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(argv), code, "", stderr)

    return run


def _git_timing_out(argv: Sequence[str], **kwargs: object) -> NoReturn:
    raise subprocess.TimeoutExpired(list(argv), float(str(kwargs["timeout"])))


@pytest.mark.parametrize(
    "git_run",
    [
        _git_exiting(128, f"fatal: https://user:{SECRET}@host/org/forge failed"),
        _git_timing_out,
    ],
    ids=["exit 128", "timeout"],
)
def test_a_git_failure_raises_with_no_address_in_the_text_or_the_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, git_run: CfRun
) -> None:
    repo = _repo_with_origin(tmp_path, "https://example.com/org/forge")

    with caplog.at_level(logging.DEBUG), pytest.raises(ContextForgeError) as failed:
        gather_checkout(repo, _cf_for(repo), git_run)

    assert "remote get-url origin" in str(failed.value)
    assert SECRET not in str(failed.value) + caplog.text
    assert "example.com" not in str(failed.value) + caplog.text


def test_a_missing_git_raises(tmp_path: Path) -> None:
    repo = _repo_with_origin(tmp_path, "https://example.com/org/forge")

    def no_git(*_args: object, **_kwargs: object) -> NoReturn:
        raise FileNotFoundError("git")

    with pytest.raises(ContextForgeError, match="could not run"):
        gather_checkout(repo, _cf_for(repo), no_git)


def test_a_git_call_waits_at_most_the_origin_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo_with_origin(tmp_path, "https://example.com/org/forge")
    monkeypatch.setattr(here, "ORIGIN_READ_TIMEOUT_SECONDS", 0.25)
    seen: list[float] = []

    def run(argv: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(float(str(kwargs["timeout"])))
        return subprocess.CompletedProcess(list(argv), 2, "", "")

    gather_checkout(repo, _cf_for(repo), run)

    assert seen == [0.25]


def test_git_root_of_a_repo_and_a_subdirectory(tmp_path: Path) -> None:
    repo = _repo_with_origin(tmp_path, None)
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)

    assert git_root(repo) == repo.resolve()
    assert git_root(nested) == repo.resolve()


def test_git_root_follows_a_symlinked_path(tmp_path: Path) -> None:
    repo = _repo_with_origin(tmp_path, None)
    link = tmp_path / "link"
    link.symlink_to(repo)

    assert git_root(link) == repo.resolve()


def test_git_root_of_a_linked_worktree_is_the_worktree(tmp_path: Path) -> None:
    repo = _repo_with_origin(tmp_path, None)
    worktree = tmp_path / "worktree"
    git(repo, "worktree", "add", "-b", "other", str(worktree))

    assert (worktree / ".git").is_file()
    assert git_root(worktree) == worktree.resolve()


def test_git_root_is_none_outside_any_repo(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    assert git_root(plain) is None
