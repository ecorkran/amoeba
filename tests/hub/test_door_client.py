"""The client side of the ten operations: the client part runs here, then one door call
(slice 261, 13.6, D5). A real client against the in-process hub; a ``cf`` stub that
answers for the directory, or fails, and a hub call counter."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import fake_cf_run
from git_repo import git, make_repo
from operations.pause_support import build_deps
from operations.status_support import FakeCf
from store.decision_support import CORE, LINT, NAMES
from store.release_support import FULL_HASH

from amoeba import wiring
from amoeba.cli.main import EXIT_ERROR, main
from amoeba.client import call as client_call
from amoeba.config.home import StateLayout
from amoeba.hub.calls import DoorHooks
from amoeba.operations.deps import Deps
from amoeba.operations.errors import ContextForgeError
from amoeba.operations.list_registry import MembersView
from amoeba.operations.list_view import ListResult
from amoeba.operations.message_results import InboxResult, SendResult
from amoeba.operations.names import Door, OperationName
from amoeba.operations.set_up_models import SetUpResult
from amoeba.operations.status import StatusResult
from amoeba.upstream.squadron.run_list import ListedRun
from amoeba.wiring_door import join
from hub.in_process_hub import InProcessHub
from hub.join_support import client_layout, line_for

SINCE = "2026-01-01T00:00:00+00:00"


class _Counter:
    """How many committed calls the hub has served since ``reset``."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1

    def reset(self) -> None:
        self.calls = 0


@pytest.fixture
def counter() -> _Counter:
    return _Counter()


@pytest.fixture
def hub(tmp_path: Path, counter: _Counter) -> Iterator[InProcessHub]:
    with InProcessHub(tmp_path, hooks=DoorHooks(after_commit=counter)) as running:
        yield running


@pytest.fixture
def layout(hub: InProcessHub, counter: _Counter) -> StateLayout:
    join(line_for(hub), set_aside_local=False)
    counter.reset()
    return client_layout()


def _no_runs() -> list[ListedRun]:
    return []


def _use_deps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cf: object,
) -> None:
    deps = replace(
        build_deps(tmp_path / "client", polls={}, spawns=[]).deps,
        cf_run=cf,  # pyright: ignore[reportArgumentType]
        list_runs=_no_runs,
    )

    def stub(_layout: StateLayout) -> Deps:
        return deps

    monkeypatch.setattr(wiring, "default_deps", stub)


def _directory(tmp_path: Path) -> Path:
    path = tmp_path / "caller"
    path.mkdir()
    return path


def _caller(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A directory whose ``cf`` project is the hub's member ``CORE``."""
    directory = _directory(tmp_path)
    _use_deps(monkeypatch, tmp_path, FakeCf({directory: CORE}))
    return directory


def test_status_and_the_default_list_go_through_the_door_with_here_and_runs(
    layout: StateLayout,
    counter: _Counter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _caller(tmp_path, monkeypatch)

    status = wiring.invoke(OperationName.STATUS, {}, directory, Door.CLI)
    listed = wiring.invoke(OperationName.LIST, {}, directory, Door.CLI)

    assert isinstance(status, StatusResult)
    assert [m.member.name for p in status.programs for m in p.members] == [NAMES[CORE]]
    assert isinstance(listed, ListResult)
    # Each asks ``open_runs`` first, for the runs document (262 D9).
    assert counter.calls == 4


def test_list_members_sends_no_here_and_makes_no_cf_call(
    layout: StateLayout,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_deps(monkeypatch, tmp_path, fake_cf_run(None))

    members = wiring.invoke(
        OperationName.LIST, {"subject": "members"}, Path("/anywhere"), Door.CLI
    )

    assert isinstance(members, MembersView)
    assert {row.name for row in members.members} == set(NAMES.values())


def test_inbox_send_and_report_release_round_trip(
    layout: StateLayout,
    counter: _Counter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _caller(tmp_path, monkeypatch)

    inbox = wiring.invoke(OperationName.INBOX, {}, directory, Door.CLI)
    sent = wiring.invoke(
        OperationName.SEND,
        {"id": "ask", "to": NAMES[LINT], "subject": "s", "body": "b"},
        directory,
        Door.CLI,
    )
    released = wiring.invoke(
        OperationName.REPORT_RELEASE,
        {"commit": FULL_HASH, "changed": "a change", "touched": ["api"]},
        directory,
        Door.CLI,
    )

    assert isinstance(inbox, InboxResult)
    assert isinstance(sent, SendResult)
    assert sent.outcome.value == "sent"
    assert released.outcome.value == "recorded"  # type: ignore[union-attr]
    assert counter.calls == 3


def test_add_by_project_and_rm_by_name_make_no_cf_call_and_return_no_directory(
    layout: StateLayout,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_deps(monkeypatch, tmp_path, fake_cf_run(None))

    added = wiring.invoke(
        OperationName.ADD, {"project": NAMES[LINT]}, Path("/anywhere"), Door.CLI
    )
    removed = wiring.invoke(
        OperationName.RM, {"members": [NAMES[LINT]]}, Path("/anywhere"), Door.CLI
    )

    assert isinstance(added, SetUpResult) and isinstance(removed, SetUpResult)
    assert added.working_directory is None
    assert removed.outcome.value == "applied"
    assert removed.working_directory is None


@pytest.mark.parametrize(
    ("name", "document"),
    [
        (OperationName.ADD, {}),
        (OperationName.SEND, {"id": "x", "to": "y", "subject": "s", "body": "b"}),
        (OperationName.STATUS, {}),
        (OperationName.INBOX, {}),
        (OperationName.CHANGES, {"since": SINCE}),
        (OperationName.LIST, {}),
    ],
    ids=lambda value: getattr(value, "value", ""),
)
def test_a_failing_cf_raises_before_any_hub_call(
    layout: StateLayout,
    counter: _Counter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: OperationName,
    document: object,
) -> None:
    _use_deps(monkeypatch, tmp_path, fake_cf_run(None))

    with pytest.raises(ContextForgeError):
        wiring.invoke(name, document, _directory(tmp_path), Door.CLI)

    assert counter.calls == 0


def test_a_bare_add_through_the_door_creates_the_member_on_the_hub(
    layout: StateLayout,
    counter: _Counter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _directory(tmp_path)
    _use_deps(monkeypatch, tmp_path, FakeCf({directory: "cf-brand-new"}))

    added = wiring.invoke(OperationName.ADD, {}, directory, Door.CLI)

    assert isinstance(added, SetUpResult)
    assert added.outcome.value == "applied"
    assert added.working_directory is not None
    assert counter.calls == 1


def test_a_failing_cf_exits_three_from_the_cli_with_no_hub_call(
    layout: StateLayout,
    counter: _Counter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _use_deps(monkeypatch, tmp_path, fake_cf_run(None))
    monkeypatch.chdir(_directory(tmp_path))

    code = main(["status"])

    assert code == EXIT_ERROR
    assert "ContextForgeError" in capsys.readouterr().err
    assert counter.calls == 0


def test_a_raw_origin_with_a_password_is_in_no_call_body_and_the_hub_records_it_reduced(
    layout: StateLayout,
    hub: InProcessHub,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "hunter2-the-password"
    repo = make_repo(tmp_path / "pw-repo")
    git(repo, "remote", "add", "origin", f"https://user:{secret}@github.com/org/pw.git")
    document = json.dumps({"id": "cf-pw", "name": "pw-repo", "projectPath": str(repo)})

    def cf(argv: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(argv), 0, document, "")

    deps = replace(
        build_deps(tmp_path / "client", polls={}, spawns=[]).deps,
        cf_run=cf,
        git_run=subprocess.run,
        list_runs=_no_runs,
    )

    def stub(_layout: StateLayout) -> Deps:
        return deps

    monkeypatch.setattr(wiring, "default_deps", stub)
    bodies: list[bytes] = []
    real_attempt = getattr(client_call, "_attempt")  # noqa: B009

    def recording(*args: Any) -> Any:
        bodies.append(args[3])
        return real_attempt(*args)

    monkeypatch.setattr(client_call, "_attempt", recording)

    added = wiring.invoke(OperationName.ADD, {}, repo, Door.CLI)

    assert isinstance(added, SetUpResult)
    assert added.outcome.value == "applied"
    assert bodies and not any(secret.encode() in body for body in bodies)
    assert any(b"github.com/org/pw" in body for body in bodies)
    rows = hub.rig.rows("SELECT origin FROM members WHERE name = 'pw-repo'")
    assert rows == [("github.com/org/pw",)]
    stored = "".join(
        str(cell) for row in hub.rig.rows("SELECT * FROM members") for cell in row
    )
    assert secret not in stored
