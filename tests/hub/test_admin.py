"""The hub's admin commands through the CLI (slice 260, D13)."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from store.decision_support import CORE, LINT, NAMES, seed_programs
from store.seed import insert_checkout
from user_configs import user_config

from amoeba.cli.hub_commands import hub_config_loader
from amoeba.cli.main import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, main
from amoeba.cli.render.registry import NO_CHECKOUT, render_members
from amoeba.config.home import StateLayout, layout_under, state_layout
from amoeba.config.user_config import IMAGE_CONTRACT_DOC, ConfigError
from amoeba.hub.admin import machines
from amoeba.hub.start import prepare_start
from amoeba.hub.store_open import open_hub_store
from amoeba.operations.list_registry import members_view
from amoeba.store import sql
from amoeba.store.machines import (
    ActingMachine,
    hash_token,
    machine_for_token,
    the_owner,
)
from amoeba.store.migrations import EXPECTED_SCHEMA_VERSION, read_schema_version
from amoeba.wire.fingerprint import fingerprint
from amoeba.wire.join_line import parse_join_line
from amoeba.wire.times import DOOR_VERSION
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


def _machines_with_doors(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    """``current``, ``behind``, ``ahead`` and ``fresh`` (no version recorded)."""
    versions = {
        "current": DOOR_VERSION,
        "behind": DOOR_VERSION - 1,
        "ahead": DOOR_VERSION + 1,
        "fresh": None,
    }
    for name in versions:
        _invite(capsys, name)
    with open_hub_store(hub_home) as store, store.write() as transaction:
        for name, version in versions.items():
            transaction.execute(
                "UPDATE machines SET door_version = ? WHERE name = ?", (version, name)
            )


def test_machines_text_shows_each_door_version_and_which_way_it_differs(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    _machines_with_doors(hub_home, capsys)

    code, out, _err = _run(capsys, "hub", "machines")

    lines = out.splitlines()
    assert code == EXIT_OK
    assert lines[0] == f"hub door version: {DOOR_VERSION}"
    by_name = {line.split()[0]: line for line in lines[1:]}
    assert by_name["current"].endswith(f"door: {DOOR_VERSION}")
    assert by_name["behind"].endswith(f"door: {DOOR_VERSION - 1}  behind")
    assert by_name["ahead"].endswith(f"door: {DOOR_VERSION + 1}  ahead of the hub")
    assert by_name["fresh"].endswith("door: unknown")


def test_machines_json_has_door_version_and_behind(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    _machines_with_doors(hub_home, capsys)

    rows = {
        row["name"]: row for row in json.loads(_run(capsys, "hub", "machines", "-j")[1])
    }

    assert (rows["current"]["door_version"], rows["current"]["behind"]) == (
        DOOR_VERSION,
        False,
    )
    assert rows["behind"]["behind"] is True
    assert (rows["ahead"]["door_version"], rows["ahead"]["behind"]) == (
        DOOR_VERSION + 1,
        True,
    )
    assert (rows["fresh"]["door_version"], rows["fresh"]["behind"]) == (None, None)


def test_machines_with_none_still_names_the_hubs_door_version(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _run(capsys, "hub", "machines")[1]

    assert out.splitlines() == [f"hub door version: {DOOR_VERSION}", "no machines"]


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


def test_rm_machine_deletes_its_checkouts_keeps_the_members_and_marks_one_with_none(
    hub_home: StateLayout, capsys: pytest.CaptureFixture[str]
) -> None:
    """261 D14: the machine's checkouts go in the same transaction; another machine's
    stay; a member left with none is still listed, marked as having no checkout."""
    _invite(capsys, "alpha")
    _invite(capsys, "beta")
    with open_hub_store(hub_home) as store:
        with store.read() as transaction:
            owner = the_owner(transaction)
            ids = {
                str(row[0]): int(row[1])
                for row in transaction.execute("SELECT name, machine_id FROM machines")
            }
        store.act_as(ActingMachine(ids["alpha"], owner))
        seed_programs(store)
        store.act_as(ActingMachine(ids["beta"], owner))
        with store.write() as transaction:
            insert_checkout(
                transaction,
                member_id=CORE,
                cf_project_id="cf-core-on-beta",
                path="/beta/core",
                now=NOW,
            )

    assert _run(capsys, "hub", "rm-machine", "alpha")[0] == EXIT_OK

    with open_hub_store(hub_home) as store:
        with store.read() as transaction:
            remaining = [
                tuple(row)
                for row in transaction.execute(
                    "SELECT member_id, cf_project_id FROM checkouts"
                )
            ]
        store.act_as(ActingMachine(ids["beta"], owner))
        view = members_view(store, user_config(), program=None)
    assert remaining == [(CORE, "cf-core-on-beta")]
    by_name = {row.name: row for row in view.members}
    assert set(by_name) == {NAMES[CORE], NAMES[LINT]}
    assert by_name[NAMES[LINT]].checkouts == ()
    assert [c.machine for c in by_name[NAMES[CORE]].checkouts] == ["beta"]
    assert NO_CHECKOUT in render_members(view)
