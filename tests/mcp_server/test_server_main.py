"""``amoeba-mcp``'s ``main()``: start-up checks before it serves (slice 226, D12,
task 5.2)."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest
from hub.call_support import ALPHA_TOKEN
from hub.in_process_hub import InProcessHub
from hub.start_support import complete_state, free_port, write_hub_yaml
from store.relocate_support import seed_store
from user_configs import example_config_text

from amoeba import wiring
from amoeba.client.client_file import ClientFile, write_client_file
from amoeba.config.home import HOME_VARIABLE, StateLayout, config_path, state_layout
from amoeba.mcp import server
from amoeba.mcp.detached import AmoebaScriptMissing
from amoeba.mcp.presence import PresenceDeps
from amoeba.operations.here_document import HereNotAProject
from amoeba.operations.mark_read import MarkReadResult
from amoeba.operations.names import Door, OperationName
from amoeba.operations.steps.models_session import SessionTickRequest
from amoeba.store.errors import StoreRelocateError
from amoeba.wiring_presence import LastReply, SessionIdentity, tick_session
from mcp_server.presence_rig import FAST

SCRIPT = Path("/x/amoeba")
WAITING_SECONDS_LINE = "resume_wait_seconds: 60"


@dataclass(frozen=True)
class LegacyWorld:
    """A ``HOME`` whose ``~/.config/amoeba`` holds a store and the config."""

    legacy_store: Path
    state_store: Path


@pytest.fixture
def legacy_world(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, installed_build: None
) -> LegacyWorld:
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

    def __call__(self, deps: PresenceDeps) -> None:
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

    def recording_serve(deps: PresenceDeps) -> None:
        order.append("serve")
        serve(deps)

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
        assert isinstance(result, MarkReadResult)
        return result.outcome.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            future.result() for future in [pool.submit(call), pool.submit(call)]
        ]

    assert outcomes == ["unchanged", "unchanged"]
    assert capsys.readouterr().err.count("moved state from") == 1
    assert legacy_world.state_store.exists()
    assert not legacy_world.legacy_store.exists()


# --- a machine joined to a hub (slice 263, D8) --------------------------------


def _files(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


def _join_files(hub: InProcessHub, *, certificate: bool = True) -> StateLayout:
    """The client files `amoeba join` writes, and nothing else."""
    layout = state_layout()
    layout.client_file.parent.mkdir(parents=True, exist_ok=True)
    layout.pinned_cert.parent.mkdir(parents=True, exist_ok=True)
    if certificate:
        shutil.copyfile(hub.cert_path, layout.pinned_cert)
    write_client_file(
        layout.client_file,
        ClientFile(address=hub.address, machine="alpha", token=ALPHA_TOKEN),
    )
    return layout


@pytest.fixture
def stopped_hub(tmp_path: Path) -> Iterator[InProcessHub]:
    with InProcessHub(tmp_path / "hub") as serving:
        pass
    yield serving


def test_a_joined_machine_starts_with_the_hub_stopped_and_creates_no_local_file(
    monkeypatch: pytest.MonkeyPatch, stopped_hub: InProcessHub
) -> None:
    layout = _join_files(stopped_hub)
    before = _files(layout.state_home), _files(layout.client_file.parent)
    serve = _Serve()
    monkeypatch.setattr(server, "resolve_amoeba_script", lambda: SCRIPT)
    monkeypatch.setattr(server, "serve", serve)

    server.main()

    assert serve.reached
    assert (_files(layout.state_home), _files(layout.client_file.parent)) == before


def test_a_tool_call_and_a_tick_run_on_a_joined_machine_with_no_local_config(
    tmp_path: Path,
) -> None:
    with InProcessHub(tmp_path / "hub") as hub:
        hub.rig.config = lambda: FAST
        layout = _join_files(hub)
        assert not config_path().exists()
        identity = SessionIdentity("ab" * 16, None, "claude-code", "/work")
        request = SessionTickRequest(
            here=HereNotAProject(not_a_project="not a project"),
            session_id=identity.session_id,
            client=identity.client,
            directory=identity.directory,
            client_version="1.2.3",
            last_seen=None,
            push_confirmed=False,
        )

        listed = wiring.invoke(OperationName.DECISIONS, {}, None, Door.MCP)
        with wiring.session_step_source(layout)(LastReply(), identity) as steps:
            reply = tick_session(steps, request)

    assert getattr(listed, "outcome").value == "listed"  # noqa: B009
    assert reply.member_id is None
    assert not config_path().exists()


def test_a_joined_machine_without_its_certificate_refuses_and_names_the_file(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stopped_hub: InProcessHub,
) -> None:
    layout = _join_files(stopped_hub, certificate=False)
    serve = _Serve()
    monkeypatch.setattr(server, "resolve_amoeba_script", lambda: SCRIPT)
    monkeypatch.setattr(server, "serve", serve)

    assert _main_exit_code() != 0

    err = capsys.readouterr().err
    assert "ClientFileError" in err
    assert str(layout.pinned_cert) in err
    assert not serve.reached


def test_a_hub_home_refuses_to_start_and_its_store_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    layout = state_layout()
    backups = tmp_path / "backups"
    backups.mkdir()
    write_hub_yaml(layout, backups, free_port())
    complete_state(layout)
    before = layout.store_path.read_bytes(), _files(layout.state_home)
    serve = _Serve()
    monkeypatch.setattr(server, "resolve_amoeba_script", lambda: SCRIPT)
    monkeypatch.setattr(server, "serve", serve)

    assert _main_exit_code() != 0

    assert "HubHomeError" in capsys.readouterr().err
    assert (layout.store_path.read_bytes(), _files(layout.state_home)) == before
    assert not serve.reached
