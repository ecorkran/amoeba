"""On a joined machine every unserved entry point fails and writes nothing (D2)."""

from __future__ import annotations

import logging
from functools import partial
from pathlib import Path

import anyio
import pytest
from cf_fixtures import DEFAULT_WORKTREE, fake_cf_run
from mcp_server.presence_rig import (
    FAST,
    FakeClock,
    RecordingOutbound,
    eventually,
    make_connection,
    seed_member,
)

from amoeba import wiring
from amoeba.cli.main import EXIT_ERROR, main
from amoeba.client.client_file import ClientFile, write_client_file
from amoeba.config.home import StateLayout, state_layout
from amoeba.mcp import server as mcp_server
from amoeba.mcp.in_process import run_in_process
from amoeba.mcp.presence import PresenceDeps, PresenceState
from amoeba.mcp.presence_task import run_presence
from amoeba.mcp.tools import TOOLS
from amoeba.operations.names import Door, OperationName
from amoeba.wire.protocol import SERVED_OPERATIONS
from amoeba.wiring_door import NotServedError
from amoeba.wiring_steps import steps_for

HUB = "hub.example:8443"
UNSERVED = [name for name in OperationName if name.value not in SERVED_OPERATIONS]


def _join_files(layout: StateLayout) -> None:
    write_client_file(
        layout.client_file, ClientFile(address=HUB, machine="alpha", token="t")
    )
    layout.pinned_cert.write_text("a certificate", encoding="utf-8")


def _tree(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


@pytest.fixture
def joined_home() -> StateLayout:
    layout = state_layout()
    _join_files(layout)
    return layout


@pytest.mark.parametrize("name", UNSERVED, ids=lambda name: name.value)
def test_every_unserved_operation_raises_not_served_and_writes_nothing(
    joined_home: StateLayout, name: OperationName
) -> None:
    before = _tree(joined_home.state_home)

    with pytest.raises(NotServedError, match=HUB):
        wiring.invoke(name, {}, Path("/anywhere"), Door.CLI)

    assert _tree(joined_home.state_home) == before


@pytest.mark.parametrize(
    "argv",
    [
        ["hub", "serve"],
        ["hub", "invite", "alpha"],
        ["hub", "machines"],
        ["hub", "rm-machine", "alpha"],
        ["hub", "backup"],
    ],
)
def test_each_hub_command_raises_local_store_closed_and_writes_nothing(
    joined_home: StateLayout, capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    before = _tree(joined_home.state_home)

    code = main(argv)

    assert code == EXIT_ERROR
    assert "LocalStoreClosedError" in capsys.readouterr().err
    assert _tree(joined_home.state_home) == before


@pytest.mark.parametrize(
    "spec",
    [spec for spec in TOOLS if spec.name in UNSERVED and spec.timeout_advice],
    ids=lambda spec: spec.name.value,
)
def test_every_unserved_in_process_mcp_tool_raises_not_served(
    joined_home: StateLayout, spec: object
) -> None:
    before = _tree(joined_home.state_home)

    async def call() -> None:
        await run_in_process(spec, {}, Path("/anywhere"))  # type: ignore[arg-type]

    with pytest.raises(NotServedError):
        anyio.run(call)

    assert _tree(joined_home.state_home) == before


def test_amoeba_mcp_start_raises_not_served_before_the_state_move(
    joined_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    before = _tree(joined_home.state_home)

    with pytest.raises(SystemExit):
        mcp_server.main()

    assert "NotServedError" in capsys.readouterr().err
    assert _tree(joined_home.state_home) == before


def test_a_running_mcp_server_that_is_then_joined_ticks_on_the_door_and_writes_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    layout = state_layout()
    seed_member(layout.store_path)
    clock = FakeClock()
    deps = PresenceDeps(
        open_steps=lambda last: steps_for(layout, last, lambda: FAST),
        cf_run=fake_cf_run(DEFAULT_WORKTREE),
        clock=clock,
        after_deps=partial(wiring.default_deps, layout),
    )
    state = PresenceState(started_at=clock())
    connection = make_connection(RecordingOutbound())
    connection.initialized.set()

    async def scenario() -> None:
        async def run() -> None:
            await run_presence(connection, state, deps)

        async with anyio.create_task_group() as group:
            group.start_soon(run)
            await eventually(lambda: state.member_id is not None, "the member resolved")
            _join_files(layout)
            before = _tree(layout.state_home)
            await eventually(
                lambda: any(
                    r.getMessage().startswith("tick failed:") for r in caplog.records
                ),
                "a tick to fail on the door",
            )
            assert _tree(layout.state_home) == before
            group.cancel_scope.cancel()

    with caplog.at_level(logging.INFO):
        anyio.run(scenario)

    assert not [r for r in caplog.records if "presence stopped" in r.getMessage()]
