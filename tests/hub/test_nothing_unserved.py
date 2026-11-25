"""With a client file every operation but ``handle_pause`` goes to the hub, and the
door has no "not served yet" answer of its own (slice 263, D14)."""

from __future__ import annotations

import re
from pathlib import Path

from amoeba import wiring
from amoeba.client.client_file import ClientFile, write_client_file
from amoeba.config.home import state_layout
from amoeba.operations.names import Door, OperationName
from amoeba.operations.set_up_models import SetUpOutcome
from amoeba.store.machines import list_machines
from amoeba.wire.protocol import SERVED_OPERATIONS
from hub.call_support import ALPHA_TOKEN
from hub.in_process_hub import InProcessHub

SOURCE = Path(__file__).parents[2] / "src"
HANDLE_PAUSE = OperationName.HANDLE_PAUSE


def test_every_operation_but_handle_pause_is_served() -> None:
    unserved = {name for name in OperationName if name.value not in SERVED_OPERATIONS}

    assert unserved == {HANDLE_PAUSE}


def test_no_source_file_names_not_served_error() -> None:
    named = [
        str(path)
        for path in SOURCE.rglob("*.py")
        if re.search(r"NotServedError|refuse_if_joined", path.read_text("utf-8"))
    ]

    assert named == []


def test_an_mcp_add_with_a_wake_command_on_a_joined_machine_is_rejected_unsent(
    tmp_path: Path,
) -> None:
    with InProcessHub(tmp_path / "hub") as hub:
        layout = state_layout()
        layout.pinned_cert.write_bytes(hub.cert_path.read_bytes())
        write_client_file(
            layout.client_file,
            ClientFile(address=hub.address, machine="alpha", token=ALPHA_TOKEN),
        )

        with hub.rig.open_store() as store, store.read() as transaction:
            before = [row.last_called_at for row in list_machines(transaction)]

        result = wiring.invoke(
            OperationName.ADD,
            {"project": "member-core", "wake_command": "claude -p go"},
            tmp_path,
            Door.MCP,
            after_step=False,  # as the MCP door runs it
        )
        with hub.rig.open_store() as store, store.read() as transaction:
            called = [row.last_called_at for row in list_machines(transaction)]

    assert getattr(result, "outcome") is SetUpOutcome.REJECTED  # noqa: B009
    assert called == before
