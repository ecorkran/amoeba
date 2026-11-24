"""`join` and `leave` against the in-process hub (slice 260, D3, D4)."""

from __future__ import annotations

import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
from store.decision_support import CORE
from store.question_support import KEY, NOW, waiting_question

from amoeba import wiring
from amoeba.cli.main import EXIT_ERROR, EXIT_OK, main
from amoeba.client.client_file import load_client_file
from amoeba.client.errors import (
    ClientFileError,
    HubRefusedError,
    HubUnreachableError,
)
from amoeba.operations.answer import AnswerOutcome, AnswerResult
from amoeba.operations.names import Door, OperationName
from amoeba.operations.prune import PRUNE_MARKER_NAME
from amoeba.store.machines import hash_token, machine_for_token
from amoeba.store.questions import insert_question
from amoeba.wire.join_line import JoinError
from amoeba.wire.protocol import RefusalCode
from amoeba.wiring_door import NotServedError, join, join_address, leave
from hub.call_support import ALPHA_TOKEN, BETA_TOKEN
from hub.in_process_hub import InProcessHub
from hub.join_support import (
    client_layout,
    files_of,
    line_for,
    make_local_store,
    program_ids,
)
from hub.tls_server import RecordingTlsServer


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[InProcessHub]:
    with InProcessHub(tmp_path) as running:
        yield running


def test_join_writes_a_0600_client_file_named_by_hello_and_saves_the_certificate(
    hub: InProcessHub,
) -> None:
    layout = client_layout()

    report = join(line_for(hub), set_aside_local=False)

    assert report.machine == "alpha"
    assert stat.S_IMODE(layout.client_file.stat().st_mode) == 0o600
    loaded = load_client_file(layout.client_file, layout.pinned_cert)
    assert (loaded.address, loaded.machine, loaded.token) == (
        hub.address,
        "alpha",
        ALPHA_TOKEN,
    )
    assert layout.pinned_cert.read_text(encoding="utf-8") == hub.cert_path.read_text(
        encoding="utf-8"
    )


def test_a_wrong_fingerprint_names_both_saves_nothing_and_sends_no_bytes(
    hub: InProcessHub, tmp_path: Path
) -> None:
    from amoeba.hub.certificate import make_certificate

    cert, key = tmp_path / "x-cert.pem", tmp_path / "x-key.pem"
    make_certificate(cert, key)
    layout = client_layout()
    before = files_of(layout.state_home)
    with RecordingTlsServer(cert, key) as other:
        wrong = line_for(hub).replace(hub.address, other.address)

        with pytest.raises(JoinError) as raised:
            join(wrong, set_aside_local=False)

    assert bytes(other.received) == b""
    assert "fingerprint" in str(raised.value)
    assert ALPHA_TOKEN not in str(raised.value)
    assert files_of(layout.state_home) == before


def test_nothing_listening_is_unreachable_and_saves_nothing(hub: InProcessHub) -> None:
    line = line_for(hub)
    hub.stop()
    layout = client_layout()
    before = files_of(layout.state_home)

    with pytest.raises(HubUnreachableError, match=str(hub.port)):
        join(line, set_aside_local=False)

    assert files_of(layout.state_home) == before


def test_a_refused_hello_saves_nothing(hub: InProcessHub) -> None:
    layout = client_layout()
    before = files_of(layout.state_home)

    with pytest.raises(HubRefusedError) as raised:
        join(line_for(hub, "a-token-the-hub-does-not-know"), set_aside_local=False)

    assert raised.value.code is RefusalCode.BAD_TOKEN
    assert files_of(layout.state_home) == before


def test_a_rejoin_that_fails_puts_the_previous_certificate_back(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    join(line_for(hub), set_aside_local=False)
    layout.pinned_cert.write_text("the previous certificate", encoding="utf-8")

    with pytest.raises(HubRefusedError):
        join(line_for(hub, "a-token-the-hub-does-not-know"), set_aside_local=False)

    assert layout.pinned_cert.read_text(encoding="utf-8") == "the previous certificate"
    assert layout.client_file.exists()


def test_a_rejoin_replaces_the_token(hub: InProcessHub) -> None:
    layout = client_layout()
    join(line_for(hub), set_aside_local=False)

    report = join(line_for(hub, BETA_TOKEN), set_aside_local=False)

    assert report.machine == "beta"
    loaded = load_client_file(layout.client_file, layout.pinned_cert)
    assert (loaded.machine, loaded.token) == ("beta", BETA_TOKEN)


def test_a_local_store_without_the_flag_is_refused_naming_it(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    store = make_local_store(layout, "demo")

    with pytest.raises(JoinError) as raised:
        join(line_for(hub), set_aside_local=False)

    assert str(store) in str(raised.value)
    assert "--set-aside-local" in str(raised.value)
    assert not layout.client_file.exists()
    assert program_ids(store) == ["demo"]


def test_address_changes_only_the_address_with_the_hub_stopped(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    join(line_for(hub), set_aside_local=False)
    hub.stop()

    changed = join_address("new-host.example:9999")

    loaded = load_client_file(layout.client_file, layout.pinned_cert)
    assert loaded.address == "new-host.example:9999"
    assert (loaded.machine, loaded.token) == (changed.machine, ALPHA_TOKEN)


def test_address_with_no_client_file_says_the_machine_is_not_joined() -> None:
    with pytest.raises(JoinError, match="not joined"):
        join_address("new-host.example:9999")


@pytest.mark.parametrize(
    "argv",
    [
        ["join", "only,two"],
        ["join", "a,b,c,d"],
        ["join", "--address", "no-port"],
        ["join", "--address", "host:1"],
    ],
)
def test_each_join_error_exits_3_through_the_cli_and_saves_nothing(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    layout = client_layout()
    before = files_of(layout.state_home)

    code = main(argv)

    assert code == EXIT_ERROR
    assert "JoinError" in capsys.readouterr().err
    assert files_of(layout.state_home) == before


@pytest.mark.parametrize("flag", [False, True])
def test_a_hub_home_refuses_join_and_leaves_its_store_unmarked(
    hub: InProcessHub, flag: bool
) -> None:
    layout = client_layout()
    store = make_local_store(layout, "hub-data")
    layout.hub_file.write_text("bind: x\n", encoding="utf-8")
    before = files_of(layout.state_home)

    with pytest.raises(JoinError, match="hub.yaml"):
        join(line_for(hub), set_aside_local=flag)

    assert files_of(layout.state_home) == before
    assert program_ids(store) == ["hub-data"]
    assert not layout.client_file.exists()


def test_leave_in_a_hub_home_is_refused_and_touches_no_file() -> None:
    layout = client_layout()
    store = make_local_store(layout, "hub-data")
    layout.hub_file.write_text("bind: x\n", encoding="utf-8")
    # Files a missing store leaves beside it must stay: they may hold the hub's rows.
    wal = Path(f"{store}-wal")
    store.unlink()
    wal.write_bytes(b"rows the hub may need")
    before = files_of(layout.state_home)

    with pytest.raises(JoinError, match="hub.yaml"):
        leave()

    assert files_of(layout.state_home) == before
    assert wal.read_bytes() == b"rows the hub may need"


def test_leave_in_a_home_that_is_not_joined_exits_0_and_creates_no_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    layout = client_layout()
    before = files_of(layout.state_home)

    code = main(["leave"])

    assert code == EXIT_OK
    assert "nothing to do" in capsys.readouterr().out
    assert files_of(layout.state_home) == before
    assert leave().removed == []


def test_a_client_file_with_no_certificate_fails_a_call_and_leave_still_works(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    join(line_for(hub), set_aside_local=False)
    layout.pinned_cert.unlink()

    with pytest.raises(ClientFileError, match="pinned-hub-cert"):
        wiring.invoke(OperationName.DECISIONS, {}, None, Door.CLI)
    report = leave()

    assert report.removed == [layout.client_file]
    assert not layout.client_file.exists()


def test_the_cli_joins_and_leaves(
    hub: InProcessHub, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["join", line_for(hub), "-j"]) == EXIT_OK
    assert '"machine": "alpha"' in capsys.readouterr().out

    assert main(["leave", "-j"]) == EXIT_OK
    assert '"removed"' in capsys.readouterr().out


def _question_on_beta(hub: InProcessHub) -> None:
    """A question whose run is on ``beta``, seeded in the hub store."""
    with hub.rig.open_store() as store:
        with store.read() as transaction:
            beta = machine_for_token(transaction, hash_token(BETA_TOKEN))
        assert beta is not None
        store.act_as(beta)
        with store.write() as transaction:
            insert_question(transaction, waiting_question(member_id=CORE), now=NOW)


def test_a_joined_machine_serves_the_served_operations_through_the_hub_and_no_other(
    hub: InProcessHub,
) -> None:
    layout = client_layout()
    join(line_for(hub), set_aside_local=False)
    _question_on_beta(hub)
    before = files_of(layout.state_home)

    listed = wiring.invoke(OperationName.DECISIONS, {}, None, Door.CLI)
    answered = wiring.invoke(
        OperationName.ANSWER,
        {"run_id": KEY.run_id, "text": "300 lines"},
        Path("/anywhere"),
        Door.CLI,
    )
    with pytest.raises(NotServedError, match="does not serve handle_pause"):
        wiring.invoke(OperationName.HANDLE_PAUSE, {}, Path("/anywhere"), Door.CLI)

    assert getattr(listed, "outcome").value == "listed"  # noqa: B009
    assert isinstance(answered, AnswerResult)
    assert answered.outcome is AnswerOutcome.RECORDED
    assert answered.resume is None
    assert answered.waiting_on_machine is not None
    assert answered.waiting_on_machine.machine == "beta"
    assert hub.rig.rows("SELECT via FROM answers") == [("cli",)]
    # The after-step's file clean-up writes its marker; nothing else is local.
    assert [f for f in files_of(layout.state_home) if f != PRUNE_MARKER_NAME] == before
    assert not layout.store_path.exists()
