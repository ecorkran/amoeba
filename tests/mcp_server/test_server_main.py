"""``amoeba-mcp``'s ``main()``: start-up checks before it serves (slice 226, D12,
task 5.2)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest
from store.relocate_support import seed_store
from user_configs import example_config_text

from amoeba import wiring
from amoeba.config.home import HOME_VARIABLE
from amoeba.mcp import server
from amoeba.mcp.detached import AmoebaScriptMissing
from amoeba.operations.names import Door, OperationName
from amoeba.store.errors import StoreRelocateError

SCRIPT = Path("/x/amoeba")
WAITING_SECONDS_LINE = "resume_wait_seconds: 60"


@dataclass(frozen=True)
class LegacyWorld:
    """A ``HOME`` whose ``~/.config/amoeba`` holds a store and the config."""

    legacy_store: Path
    state_store: Path


@pytest.fixture
def legacy_world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> LegacyWorld:
    monkeypatch.delenv(HOME_VARIABLE)
    monkeypatch.setenv("HOME", str(tmp_path))
    legacy = tmp_path / ".config" / "amoeba"
    legacy_store = seed_store(legacy)
    (legacy / "config.yaml").write_text(example_config_text(), encoding="utf-8")
    state_store = tmp_path / ".local" / "state" / "amoeba" / "amoeba.sqlite3"
    return LegacyWorld(legacy_store, state_store)


class _Serve:
    """A stand-in for ``server.serve`` that records that it was reached."""

    def __init__(self, world: LegacyWorld | None = None) -> None:
        self.reached = False
        self.moved_when_reached: bool | None = None
        self._world = world

    def __call__(self) -> None:
        self.reached = True
        if self._world is not None:
            self.moved_when_reached = (
                self._world.state_store.exists()
                and not self._world.legacy_store.exists()
            )


def _main_exit_code() -> int:
    with pytest.raises(SystemExit) as raised:
        server.main()
    code = raised.value.code
    assert isinstance(code, int)
    return code


def test_a_missing_amoeba_script_exits_non_zero_and_serves_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def missing() -> Path:
        raise AmoebaScriptMissing("the amoeba script is not at /nowhere/amoeba")

    serve = _Serve()
    monkeypatch.setattr(server, "resolve_amoeba_script", missing)
    monkeypatch.setattr(server, "serve", serve)

    assert _main_exit_code() != 0

    assert (
        "error: AmoebaScriptMissing: the amoeba script is not at /nowhere/amoeba"
        in capsys.readouterr().err
    )
    assert not serve.reached


def test_the_legacy_state_is_moved_before_the_server_serves(
    monkeypatch: pytest.MonkeyPatch, legacy_world: LegacyWorld
) -> None:
    order: list[str] = []
    real_prepare = wiring.prepare_home
    serve = _Serve(legacy_world)

    def recording_prepare() -> None:
        order.append("prepare")
        real_prepare()

    def recording_serve() -> None:
        order.append("serve")
        serve()

    monkeypatch.setattr(server, "resolve_amoeba_script", lambda: SCRIPT)
    monkeypatch.setattr(wiring, "prepare_home", recording_prepare)
    monkeypatch.setattr(server, "serve", recording_serve)

    server.main()

    assert order == ["prepare", "serve"]
    assert serve.moved_when_reached is True


def test_a_failed_move_exits_non_zero_with_the_clis_text_and_serves_nothing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    legacy_world: LegacyWorld,
) -> None:
    def failing() -> None:
        raise StoreRelocateError("cannot move state")

    serve = _Serve()
    monkeypatch.setattr(server, "resolve_amoeba_script", lambda: SCRIPT)
    monkeypatch.setattr(wiring, "prepare_home", failing)
    monkeypatch.setattr(server, "serve", serve)

    assert _main_exit_code() != 0

    assert "error: StoreRelocateError: cannot move state\n" in capsys.readouterr().err
    assert not serve.reached


def test_a_config_whose_bound_is_not_below_the_deadline_names_the_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    legacy_world: LegacyWorld,
    tmp_path: Path,
) -> None:
    config = tmp_path / ".config" / "amoeba" / "config.yaml"
    text = config.read_text(encoding="utf-8")
    assert WAITING_SECONDS_LINE in text
    config.write_text(
        text.replace(WAITING_SECONDS_LINE, "resume_wait_seconds: 600"),
        encoding="utf-8",
    )
    serve = _Serve()
    monkeypatch.setattr(server, "resolve_amoeba_script", lambda: SCRIPT)
    monkeypatch.setattr(server, "serve", serve)

    assert _main_exit_code() != 0

    assert "resume_wait_seconds" in capsys.readouterr().err
    assert not serve.reached


def test_two_first_calls_at_once_both_succeed_and_the_state_moves_once(
    capsys: pytest.CaptureFixture[str], legacy_world: LegacyWorld
) -> None:
    def call() -> str:
        result = wiring.invoke(OperationName.MARK_READ, {"through": 0}, None, Door.MCP)
        return result.outcome.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            future.result() for future in [pool.submit(call), pool.submit(call)]
        ]

    assert outcomes == ["unchanged", "unchanged"]
    assert capsys.readouterr().err.count("moved state from") == 1
    assert legacy_world.state_store.exists()
    assert not legacy_world.legacy_store.exists()
