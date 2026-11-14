"""``wiring``: the one place both doors place operation arguments (slice 226, D4).

Every in-process operation is run against the autouse throwaway ``AMOEBA_HOME`` with
a request that the operation refuses (``rejected``) before it reaches ``sq`` or
``cf``, so the result type and the store's lifetime are what is checked.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from user_configs import example_config_text
from wiring_support import TrackedStore, is_closed, record_opened_stores

from amoeba import wiring, wiring_releases
from amoeba.cli import commands
from amoeba.cli import main as cli
from amoeba.config.home import AmoebaHomeError, config_path, state_layout
from amoeba.config.user_config import ConfigError
from amoeba.operations.answer import AnswerOutcome, AnswerResult
from amoeba.operations.changes_models import (
    ChangesOutcome,
    ChangesResult,
    MemberRef,
    ProviderPair,
)
from amoeba.operations.decisions import DecisionsResult
from amoeba.operations.dismiss import DismissResult
from amoeba.operations.list_view import ListResult
from amoeba.operations.mark_read import MarkReadOutcome, MarkReadResult
from amoeba.operations.members import ContextForgeError
from amoeba.operations.names import Door, OperationName
from amoeba.operations.report_release_models import (
    ReleaseReport,
    ReportOutcome,
    ReportReleaseResult,
)
from amoeba.operations.retract import RetractResult
from amoeba.operations.set_up_models import SetUpResult
from amoeba.operations.status import StatusResult
from amoeba.store.errors import StoreBusyError, StoreError
from amoeba.store.vocabulary import ConsumedMode
from amoeba.upstream.squadron.errors import SquadronError

#: For each in-process operation, a document it refuses and the result type it gives.
REFUSED: dict[OperationName, tuple[object, type]] = {
    OperationName.ADD: ({"bogus": 1}, SetUpResult),
    OperationName.RM: ({"bogus": 1}, SetUpResult),
    OperationName.LIST: ({"bogus": 1}, ListResult),
    OperationName.ANSWER: ({}, AnswerResult),
    OperationName.STATUS: ({"bogus": 1}, StatusResult),
    OperationName.DECISIONS: ({"since": "not a time"}, DecisionsResult),
    OperationName.MARK_READ: ({}, MarkReadResult),
    OperationName.DISMISS: ({}, DismissResult),
    OperationName.RETRACT: ({}, RetractResult),
    OperationName.REPORT_RELEASE: ({"bogus": 1}, ReportReleaseResult),
    OperationName.CHANGES: ({"bogus": 1}, ChangesResult),
}


@pytest.fixture(autouse=True)
def _config() -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(example_config_text(), encoding="utf-8")


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[TrackedStore]:
    """Every store ``invoke`` opens, so a test can ask whether it was closed."""
    return record_opened_stores(monkeypatch)


def test_default_deps_sets_every_field() -> None:
    deps = wiring.default_deps(state_layout())

    # ``legacy_home`` is None by design when ``AMOEBA_HOME`` is set (as in tests).
    unset = [
        field.name
        for field in dataclasses.fields(deps)
        if getattr(deps, field.name) is None
    ]
    assert unset == ["legacy_home"]


def test_the_operational_errors_are_the_five_the_cli_maps_to_exit_three() -> None:
    assert set(wiring.OPERATIONAL_ERRORS) == {
        AmoebaHomeError,
        ConfigError,
        ContextForgeError,
        SquadronError,
        StoreError,
    }


@pytest.mark.parametrize(
    "error",
    [
        AmoebaHomeError("home"),
        ConfigError("config"),
        ContextForgeError("cf"),
        SquadronError("sq"),
        StoreBusyError("busy"),
    ],
    ids=lambda error: type(error).__name__,
)
def test_the_cli_reports_each_operational_error_as_exit_three(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
) -> None:
    def raising(*_arguments: object) -> object:
        raise error

    monkeypatch.setattr(commands, "invoke", raising)

    code = cli.main(["mark-read", "--through", "0"])

    assert code == cli.EXIT_ERROR
    assert capsys.readouterr().err == f"error: {type(error).__name__}: {error}\n"


@pytest.mark.parametrize("name", list(REFUSED), ids=lambda name: name.value)
def test_invoke_returns_the_result_type_the_cli_prints(
    name: OperationName, tmp_path: Path, opened: list[TrackedStore]
) -> None:
    document, result_type = REFUSED[name]

    result = wiring.invoke(name, document, tmp_path, Door.CLI)

    assert isinstance(result, result_type)
    assert wiring.is_rejected(result)
    assert wiring.result_document(result)["outcome"] == "rejected"
    (store,) = opened
    assert is_closed(store)


def test_invoke_closes_the_store_when_the_operation_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, opened: list[TrackedStore]
) -> None:
    def raising(*_arguments: object, **_keywords: object) -> object:
        raise SquadronError("sq down")

    monkeypatch.setattr(wiring, "mark_read", raising)

    with pytest.raises(SquadronError):
        wiring.invoke(OperationName.MARK_READ, {"through": 0}, None, Door.MCP)

    (store,) = opened
    assert is_closed(store)


@pytest.mark.parametrize("door", list(Door), ids=lambda door: door.value)
def test_invoke_gives_the_answer_operation_the_door_that_called(
    monkeypatch: pytest.MonkeyPatch, door: Door
) -> None:
    seen: list[Door] = []

    def recording(*_arguments: object, via: Door, **_keywords: object) -> object:
        seen.append(via)
        return AnswerResult(AnswerOutcome.REJECTED)

    monkeypatch.setattr(wiring, "answer", recording)

    wiring.invoke(OperationName.ANSWER, {}, None, door)

    assert seen == [door]


def test_the_cli_calls_invoke_as_the_cli_door(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    doors: list[Door] = []

    def recording(
        name: OperationName, document: object, directory: Path | None, door: Door
    ) -> MarkReadResult:
        doors.append(door)
        return MarkReadResult(outcome=MarkReadOutcome.UNCHANGED, previous=0, current=0)

    monkeypatch.setattr(commands, "invoke", recording)

    assert cli.main(["mark-read", "--through", "0"]) == cli.EXIT_OK
    capsys.readouterr()

    assert doors == [Door.CLI]


@pytest.mark.parametrize(
    ("name", "operation"),
    [
        (OperationName.REPORT_RELEASE, "report_release"),
        (OperationName.CHANGES, "changes"),
    ],
)
def test_invoke_gives_each_release_operation_the_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    name: OperationName,
    operation: str,
) -> None:
    seen: list[Path] = []

    def recording(
        _store: object, _document: object, *, directory: Path, deps: object
    ) -> object:
        seen.append(directory)
        return _changes_result(ChangesOutcome.LISTED)

    monkeypatch.setattr(wiring_releases, operation, recording)

    wiring.invoke(name, {}, tmp_path, Door.CLI)

    assert seen == [tmp_path]


def test_invoke_refuses_handle_pause_naming_it(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="handle_pause"):
        wiring.invoke(OperationName.HANDLE_PAUSE, {}, tmp_path, Door.CLI)


@pytest.mark.parametrize(
    "name",
    [
        OperationName.ADD,
        OperationName.RM,
        OperationName.LIST,
        OperationName.STATUS,
        OperationName.REPORT_RELEASE,
        OperationName.CHANGES,
    ],
)
def test_invoke_requires_a_directory_for_the_directory_operations(
    name: OperationName,
) -> None:
    with pytest.raises(ValueError, match=name.value):
        wiring.invoke(name, {}, None, Door.CLI)


def _release_report() -> ReleaseReport:
    return ReleaseReport(
        seq=1,
        commit="a" * 40,
        version=None,
        changed="text",
        touched=("one",),
        reported_at="2026-11-09T12:00:00+00:00",
        versioned_at=None,
    )


def _report_release_result(outcome: ReportOutcome) -> ReportReleaseResult:
    return ReportReleaseResult(
        outcome=outcome, member="member", report=_release_report(), problems=()
    )


def _changes_result(outcome: ChangesOutcome) -> ChangesResult:
    return ChangesResult(
        outcome=outcome,
        member=MemberRef(id="member", name=None),
        since="2026-11-09T12:00:00+00:00",
        pairs=(),
        problems=(),
        warnings=(),
    )


@pytest.mark.parametrize(
    "result",
    [
        _report_release_result(ReportOutcome.REJECTED),
        _changes_result(ChangesOutcome.REJECTED),
    ],
    ids=["report_release", "changes"],
)
def test_a_rejected_release_result_is_rejected(result: wiring.OperationResult) -> None:
    assert wiring.is_rejected(result)


@pytest.mark.parametrize(
    "result",
    [
        *(
            _report_release_result(outcome)
            for outcome in ReportOutcome
            if outcome is not ReportOutcome.REJECTED
        ),
        _changes_result(ChangesOutcome.LISTED),
    ],
)
def test_a_release_result_that_is_not_rejected_is_not_rejected(
    result: wiring.OperationResult,
) -> None:
    assert not wiring.is_rejected(result)


def test_the_report_release_document_has_the_designed_shape() -> None:
    document = wiring.result_document(_report_release_result(ReportOutcome.RECORDED))
    assert document == {
        "outcome": "recorded",
        "member": "member",
        "report": {
            "seq": 1,
            "commit": "a" * 40,
            "version": None,
            "changed": "text",
            "touched": ["one"],
            "reported_at": "2026-11-09T12:00:00+00:00",
            "versioned_at": None,
        },
        "problems": [],
    }


def test_the_changes_document_has_the_designed_shape() -> None:
    result = ChangesResult(
        outcome=ChangesOutcome.LISTED,
        member=MemberRef(id="member", name="me"),
        since="2026-11-09T12:00:00+00:00",
        pairs=(
            ProviderPair(
                provider=MemberRef(id="provider", name="core"),
                consumed=ConsumedMode.FROM_RELEASE,
                releases=(_release_report(),),
            ),
        ),
        problems=(),
        warnings=(),
    )
    document = wiring.result_document(result)
    assert list(document) == [
        "outcome",
        "member",
        "since",
        "pairs",
        "problems",
        "warnings",
    ]
    assert document["member"] == {"id": "member", "name": "me"}
    (pair,) = document["pairs"]  # type: ignore[misc]
    assert pair["provider"] == {"id": "provider", "name": "core"}
    assert pair["consumed"] == "from_release"
    assert pair["releases"][0]["touched"] == ["one"]
