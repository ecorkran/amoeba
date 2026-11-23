"""A password in a remote's address never leaves the client part (slice 261, D3).

``add`` runs the real ``git`` in a real repo whose ``origin`` holds ``user:secret@``,
once with a clean address and once with a malformed one that still holds a password.
The secret is in no stdout, stderr, log file or store byte.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from cf_routing import RoutedProject
from git_repo import git, make_repo

from amoeba.cli.exit_codes import EXIT_OK
from amoeba.config.home import store_path
from cli.cli_support import result_of, run_amoeba, write_config

SECRET = "hunter2-secret-9f3a"
ADDRESSES = [
    f"https://user:{SECRET}@github.com/org/forge.git",
    f"git@host:{SECRET}@:::weird//address",
]


def _every_byte_under_home() -> list[Path]:
    home = Path(os.environ["AMOEBA_HOME"])
    return [path for path in home.rglob("*") if path.is_file()]


@pytest.mark.parametrize("address", ADDRESSES, ids=["https", "malformed"])
def test_the_secret_is_in_no_output_log_or_store_byte(
    tmp_path: Path, address: str
) -> None:
    write_config()
    repo = make_repo(tmp_path / "repos" / "forge")
    git(repo, "remote", "add", "origin", address)
    project = RoutedProject("project-forge-id", "forge", repo)

    completed = run_amoeba(
        tmp_path, "add", "--program", "demo", cwd=repo, routing=[project], real_git=True
    )
    listed = run_amoeba(
        tmp_path, "list", "members", cwd=repo, routing=[project], real_git=True
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    for output in (completed.stdout, completed.stderr, listed.stdout, listed.stderr):
        assert SECRET not in output
    for path in _every_byte_under_home():
        assert SECRET.encode() not in path.read_bytes(), path
    assert store_path().exists()


def test_the_https_form_is_recorded_reduced_with_no_user_or_password(
    tmp_path: Path,
) -> None:
    write_config()
    repo = make_repo(tmp_path / "repos" / "forge")
    git(repo, "remote", "add", "origin", ADDRESSES[0])
    project = RoutedProject("project-forge-id", "forge", repo)
    run_amoeba(
        tmp_path, "add", "--program", "demo", cwd=repo, routing=[project], real_git=True
    )

    members = result_of(
        run_amoeba(
            tmp_path,
            "list",
            "members",
            cwd=repo,
            routing=[project],
            real_git=True,
            as_json=True,
        )
    )["members"]

    assert members[0]["origin"] == "github.com/org/forge"
