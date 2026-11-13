"""``wiring``: the one place both doors place operation arguments (slice 226, D4).

Every in-process operation is run against the autouse throwaway ``AMOEBA_HOME`` with
a request that the operation refuses (``rejected``) before it reaches ``sq`` or
``cf``, so the result type and the store's lifetime are what is checked.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest
from user_configs import example_config_text

from amoeba import wiring
from amoeba.cli import main as cli
from amoeba.config.home import AmoebaHomeError, config_path, state_layout
from amoeba.config.user_config import ConfigError
from amoeba.operations.answer import AnswerResult
from amoeba.operations.decisions import DecisionsResult
from amoeba.operations.dismiss import DismissResult
from amoeba.operations.mark_read import MarkReadResult
from amoeba.operations.members import ContextForgeError
from amoeba.operations.names import Door, OperationName
from amoeba.operations.retract import RetractResult
from amoeba.operations.set_up_models import SetUpResult
from amoeba.operations.status import StatusResult
from amoeba.store.errors import StoreBusyError, StoreError
from amoeba.store.store import Store
from amoeba.upstream.squadron.errors import SquadronError

#: For each in-process operation, a document it refuses and the result type it gives.
REFUSED: dict[OperationName, tuple[object, type]] = {
    OperationName.SET_UP: ({}, SetUpResult),
    OperationName.ANSWER: ({}, AnswerResult),
    OperationName.STATUS: ({"bogus": 1}, StatusResult),
    OperationName.DECISIONS: ({"since": "not a time"}, DecisionsResult),
    OperationName.MARK_READ: ({}, MarkReadResult),
    OperationName.DISMISS: ({}, DismissResult),
    OperationName.RETRACT: ({}, RetractResult),
}


@pytest.fixture(autouse=True)
def _config() -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(example_config_text(), encoding="utf-8")


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[Store]:
    """Every store ``invoke`` opens, so a test can ask whether it was closed."""
    stores: list[Store] = []
    real_open: Callable[..., Store] = wiring.open_store

    def recording_open(layout: object) -> Store:
        store = real_open(layout)
        stores.append(store)
        return store

    monkeypatch.setattr(wiring, "open_store", recording_open)
    return stores


def _is_closed(store: Store) -> bool:
    try:
        with store.read():
            return False
    except StoreError:
        # Expected: the store wraps SQLite's "Cannot operate on a closed database".
        return True


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

    monkeypatch.setattr(cli, "invoke", raising)

    code = cli.main(["mark_read", "--through", "0"])

    assert code == cli.EXIT_ERROR
    assert capsys.readouterr().err == f"error: {type(error).__name__}: {error}\n"


@pytest.mark.parametrize("name", list(REFUSED), ids=lambda name: name.value)
def test_invoke_returns_the_result_type_the_cli_prints(
    name: OperationName, tmp_path: Path, opened: list[Store]
) -> None:
    document, result_type = REFUSED[name]

    result = wiring.invoke(name, document, tmp_path, Door.CLI)

    assert isinstance(result, result_type)
    assert wiring.is_rejected(result)
    assert wiring.result_document(result)["outcome"] == "rejected"
    (store,) = opened
    assert _is_closed(store)


def test_invoke_closes_the_store_when_the_operation_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, opened: list[Store]
) -> None:
    def raising(*_arguments: object, **_keywords: object) -> object:
        raise SquadronError("sq down")

    monkeypatch.setattr(wiring, "mark_read", raising)

    with pytest.raises(SquadronError):
        wiring.invoke(OperationName.MARK_READ, {"through": 0}, None, Door.MCP)

    (store,) = opened
    assert _is_closed(store)


def test_invoke_refuses_handle_pause_naming_it(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="handle_pause"):
        wiring.invoke(OperationName.HANDLE_PAUSE, {}, tmp_path, Door.CLI)


@pytest.mark.parametrize("name", [OperationName.SET_UP, OperationName.STATUS])
def test_invoke_requires_a_directory_for_the_directory_operations(
    name: OperationName,
) -> None:
    with pytest.raises(ValueError, match=name.value):
        wiring.invoke(name, {}, None, Door.CLI)
