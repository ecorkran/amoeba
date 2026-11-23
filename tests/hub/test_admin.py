"""The hub's admin commands through the CLI (slice 260, D13)."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from amoeba.cli.hub_commands import hub_config_loader
from amoeba.cli.main import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, main
from amoeba.config.home import StateLayout, layout_under, state_layout
from amoeba.config.user_config import IMAGE_CONTRACT_DOC, ConfigError
from amoeba.hub.admin import machines
from amoeba.hub.start import prepare_start
from amoeba.hub.store_open import open_hub_store
from amoeba.store import sql
from amoeba.store.machines import hash_token, machine_for_token
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, read_schema_version
from amoeba.wire.fingerprint import fingerprint
from amoeba.wire.join_line import parse_join_line
from amoeba.wiring import open_store
from hub.call_support import NOW
from hub.start_support import complete_state, free_port, tree, write_hub_yaml


@pytest.fixture
def hub_home(tmp_path: Path) -> StateLayout:
    """The AMOEBA_HOME as a started hub: store, pair and ``hub.yaml``."""
    layout = state_layout()
    backups = tmp_path / "backups"
    backups.mkdir()
    write_hub_yaml(layout, backups, free_port())
    complete_state(layout)
    return layout


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _invite(capsys: pytest.CaptureFixture[str], name: str) -> dict[str, object]:
    code, out, _err = _run(capsys, "hub", "invite", name, "-j")
    assert code == EXIT_OK
    document: dict[str, object] = json.loads(out)
    return document


def test_invite_prints_a_line_the_parser_reads_with_the_hubs_fingerprint(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    document = _invite(capsys, "alpha")

    line = parse_join_line(str(document["join_line"]))
    assert line.fingerprint == fingerprint(
        hub_home.hub_cert.read_text(encoding="utf-8")
    )
    assert line.address.startswith("127.0.0.1:")
    assert document["new"] is True


def test_a_reinvite_ends_the_old_token(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    first = parse_join_line(str(_invite(capsys, "alpha")["join_line"]))
    second = parse_join_line(str(_invite(capsys, "alpha")["join_line"]))

    assert first.token != second.token
    names = [row.name for row in machines(hub_home)]
    assert names == ["alpha"]

    with open_hub_store(hub_home) as store, store.read() as transaction:
        assert machine_for_token(transaction, hash_token(first.token)) is None
        assert machine_for_token(transaction, hash_token(second.token)) is not None


def test_machines_lists_name_token_call_time_and_client_version(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    _invite(capsys, "alpha")
    _invite(capsys, "beta")

    code, out, _err = _run(capsys, "hub", "machines", "-j")

    rows = json.loads(out)
    assert code == EXIT_OK
    assert [row["name"] for row in rows] == ["alpha", "beta"]
    assert all(row["has_token"] for row in rows)
    assert rows[0]["last_called_at"] is None and rows[0]["client_version"] is None


def test_rm_machine_of_an_unknown_name_exits_1(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _out, err = _run(capsys, "hub", "rm-machine", "nobody")

    assert code == EXIT_REJECTED
    assert "nobody" in err


def test_rm_machine_removes_it(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    _invite(capsys, "alpha")

    assert _run(capsys, "hub", "rm-machine", "alpha")[0] == EXIT_OK
    assert json.loads(_run(capsys, "hub", "machines", "-j")[1]) == []


def test_a_malformed_name_exits_1(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _out, err = _run(capsys, "hub", "invite", "Not A Name")

    assert code == EXIT_REJECTED
    assert "machine name" in err
    assert json.loads(_run(capsys, "hub", "machines", "-j")[1]) == []


def test_invite_with_no_hub_yaml_exits_3_naming_it_and_adds_no_machine(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    hub_home.hub_file.unlink()

    code, _out, err = _run(capsys, "hub", "invite", "alpha")

    assert code == EXIT_ERROR
    assert "hub config" in err
    assert machines(hub_home) == []


def test_invite_with_no_certificate_exits_3_naming_it_and_adds_no_machine(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    hub_home.hub_cert.unlink()

    code, _out, err = _run(capsys, "hub", "invite", "alpha")

    assert code == EXIT_ERROR
    assert "hub-cert.pem" in err
    assert "amoeba hub serve" in err
    assert machines(hub_home) == []


def test_backup_prints_a_timed_path(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _err = _run(capsys, "hub", "backup", "-j")

    path = Path(json.loads(out)["path"])
    assert code == EXIT_OK
    assert path.parent.name == "timed"
    assert {p.name for p in path.iterdir()} == {
        "amoeba.sqlite3",
        "hub-cert.pem",
        "hub-key.pem",
    }


@pytest.mark.parametrize(
    "argv",
    [
        ["hub", "invite", "alpha"],
        ["hub", "machines"],
        ["hub", "rm-machine", "alpha"],
        ["hub", "backup"],
    ],
)
def test_before_the_first_serve_each_admin_command_fails_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    layout = state_layout()
    backups = tmp_path / "backups"
    backups.mkdir()
    write_hub_yaml(layout, backups, free_port())
    before = tree(layout.state_home)

    code, _out, err = _run(capsys, *argv)

    assert code == EXIT_ERROR
    assert "HubStoreMissingError" in err
    assert tree(layout.state_home) == before
    assert not layout.store_path.exists()

    prepared = prepare_start(layout, now=NOW, start_log=lambda _c: None)
    prepared.listener.close()
    assert layout.store_path.exists() and layout.hub_cert.exists()


def test_a_hub_with_no_config_yaml_is_not_told_to_run_init(tmp_path: Path) -> None:
    # `amoeba init` fails in a hub home, so the message must point at the contract.
    layout = layout_under(tmp_path, tmp_path, None)

    with pytest.raises(ConfigError) as raised:
        hub_config_loader(layout)()

    assert "amoeba init" not in str(raised.value)
    assert IMAGE_CONTRACT_DOC in str(raised.value)


ADMIN_COMMANDS = [
    ["hub", "invite", "alpha"],
    ["hub", "machines"],
    ["hub", "rm-machine", "local"],
    ["hub", "backup"],
]


def _schema_version(layout: StateLayout) -> int:
    with closing(sqlite3.connect(layout.store_path)) as connection:
        return read_schema_version(connection)


def _sessions_and_machines(layout: StateLayout) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(layout.store_path)) as connection:
        return list(connection.execute("SELECT name FROM machines ORDER BY name"))


@pytest.mark.parametrize("argv", ADMIN_COMMANDS)
def test_admin_commands_refuse_a_home_that_is_not_a_hubs_and_leave_its_store_alone(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    """A laptop's own store, with no ``hub.yaml``: nothing of it is opened."""
    layout = state_layout()
    with open_store(layout):
        pass
    machines_before = _sessions_and_machines(layout)
    assert machines_before  # the laptop's own machine row is there to lose

    code, _out, err = _run(capsys, *argv)

    assert code == EXIT_ERROR
    assert "NotAHubHomeError" in err
    assert _sessions_and_machines(layout) == machines_before


@pytest.mark.parametrize("argv", ADMIN_COMMANDS)
def test_admin_commands_refuse_a_hub_store_that_needs_migrating(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    """Only ``amoeba hub serve`` migrates, after its backup; an admin command never."""
    older = EXPECTED_SCHEMA_VERSION - 1
    with closing(sqlite3.connect(hub_home.store_path)) as connection:
        connection.execute(
            "UPDATE schema_meta SET version = ? WHERE id = ?",
            (older, sql.SCHEMA_META_ROW_ID),
        )
        connection.commit()

    code, _out, err = _run(capsys, *argv)

    assert code == EXIT_ERROR
    assert "HubStoreBehindError" in err
    assert "amoeba hub serve" in err
    assert _schema_version(hub_home) == older
