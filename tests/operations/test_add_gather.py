"""The client part of ``add``: what is gathered, and when (slice 261, D5)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run
from git_repo import git, make_repo

from amoeba.operations.add_gather import gather_add
from amoeba.operations.errors import ContextForgeError
from amoeba.operations.here_document import HereCheckout, HereNotAProject
from amoeba.operations.set_up_models import SetUpOutcome, SetUpResult
from amoeba.store.vocabulary import Door
from amoeba.upstream.context_forge.cli_call import CfRun

CHECKOUT_ID = "project_1_a"


def _cf_for(path: Path) -> CfRun:
    def run(argv: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        document = {"id": CHECKOUT_ID, "name": "forge", "projectPath": str(path)}
        return subprocess.CompletedProcess(list(argv), 0, json.dumps(document), "")

    return run


def _must_not_run(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("no cf or git call was expected")


@pytest.mark.parametrize(
    "document",
    [
        {"project": "forge", "rules_paths": ["CLAUDE.md"]},
        {
            "bulk": {
                "program": "demo",
                "members": [{"project": "forge"}, {"project": "lib"}],
            }
        },
    ],
    ids=["--project", "an all-named bulk file"],
)
def test_a_call_that_names_every_member_makes_no_cf_call(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    gathered = gather_add(document, tmp_path, _must_not_run, _must_not_run, Door.CLI)

    assert gathered is None


def test_a_bare_add_gathers_the_checkout(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    git(repo, "remote", "add", "origin", "git@github.com:org/Forge.git")

    gathered = gather_add({}, repo, _cf_for(repo), subprocess.run, Door.CLI)

    assert gathered == HereCheckout(
        project_id=CHECKOUT_ID,
        name="forge",
        path=str(repo),
        origin="github.com/org/forge",
    )


@pytest.mark.parametrize(
    "document",
    [{"bulk": {"program": "demo", "members": [{}, {"project": "lib"}]}}],
    ids=["a bulk entry with no member"],
)
def test_each_way_an_entry_names_no_member_gathers_the_checkout(
    tmp_path: Path, document: dict[str, Any]
) -> None:
    repo = make_repo(tmp_path / "repo")

    gathered = gather_add(document, repo, _cf_for(repo), subprocess.run, Door.CLI)

    assert isinstance(gathered, HereCheckout)


def test_not_a_project_is_a_gathered_value(tmp_path: Path) -> None:
    gathered = gather_add(
        {}, tmp_path, fake_cf_run(OUTSIDE_ANY_PROJECT), _must_not_run, Door.CLI
    )

    assert isinstance(gathered, HereNotAProject)


def test_an_mcp_add_with_a_wake_command_is_refused_before_any_gather(
    tmp_path: Path,
) -> None:
    refused = gather_add(
        {"wake_command": "agent"}, tmp_path, _must_not_run, _must_not_run, Door.MCP
    )

    assert isinstance(refused, SetUpResult)
    assert refused.outcome is SetUpOutcome.REJECTED


def test_a_document_that_does_not_parse_gathers_nothing(tmp_path: Path) -> None:
    assert (
        gather_add({"unknown": 1}, tmp_path, _must_not_run, _must_not_run, Door.CLI)
        is None
    )


def test_a_cf_failure_raises(tmp_path: Path) -> None:
    with pytest.raises(ContextForgeError):
        gather_add({}, tmp_path, fake_cf_run(None), _must_not_run, Door.CLI)
