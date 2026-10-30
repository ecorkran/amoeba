"""Tests for ``amoeba inspect``: it reads everything it claims, and writes nothing.

Every listing is exercised in both forms (table and ``--json``), both while the
resident process is running and while it is stopped. The never-migrates and
never-creates properties are checked against the **filesystem**, not merely
against the command's exit status: a command that migrated and then succeeded
would pass an exit-code-only check while having mutated the store.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from cli_harness import await_running, run_cli, start_background
from inspection_harness import FIXTURE_VERDICT, PROJECT, seed_every_listing

from amoeba.cli.main import ExitCode
from amoeba.inspection import LISTINGS, LISTINGS_BY_NAME, PROJECTS_LISTING
from amoeba.inspection.listing import ListingScope
from amoeba.store import Store
from amoeba.store.migrations import (
    EXPECTED_SCHEMA_VERSION,
    migrate,
    read_schema_version,
)

#: Listings that take ``--project``; ``projects`` reads the directory instead.
PROJECT_LISTINGS = tuple(
    listing.name for listing in LISTINGS if listing.scope is ListingScope.PROJECT
)


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    """An empty Squadron runs directory. Never the real one."""
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory


@pytest.fixture
def populated(supervisor_dir: Path) -> Path:
    """A store carrying a row for every listing; returns the store file."""
    return seed_every_listing(supervisor_dir).store_file


@pytest.fixture
def running_supervisor(
    supervisor_dir: Path, runs_dir: Path, populated: Path
) -> Iterator[None]:
    """A real resident process, running for the duration of a test."""
    process = start_background(
        supervisor_dir,
        ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.05"],
    )
    try:
        await_running(supervisor_dir)
        yield
    finally:
        run_cli(["stop"], supervisor_dir)
        process.cleanup()


#: A value in the ``populated`` store for every required flag a listing takes.
_REQUIRED_VALUES: dict[str, str] = {"--verdict": FIXTURE_VERDICT}


def _listing_arguments(name: str, extra: list[str] | None = None) -> list[str]:
    """Build the argument vector for one listing."""
    listing = LISTINGS_BY_NAME[name]
    arguments = ["inspect", name]
    if listing.scope is ListingScope.PROJECT:
        arguments += ["--project", PROJECT]
    for option in listing.value_options:
        if option.required:
            arguments += [option.flag, _REQUIRED_VALUES[option.flag]]
    return arguments + (extra or [])


# --------------------------------------------------------------------------
# Every listing, both forms, stopped
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", [listing.name for listing in LISTINGS])
def test_every_listing_renders_a_table(
    supervisor_dir: Path, populated: Path, name: str
) -> None:
    """Human-readable output for each registered listing."""
    result = run_cli(_listing_arguments(name), supervisor_dir)

    assert result.returncode == ExitCode.OK
    assert result.stdout.strip(), "a listing must print something"


@pytest.mark.parametrize("name", [listing.name for listing in LISTINGS])
def test_every_listing_renders_json(
    supervisor_dir: Path, populated: Path, name: str
) -> None:
    """``--json`` parses, and its rows carry the listing's own columns."""
    result = run_cli(_listing_arguments(name, ["--json"]), supervisor_dir)

    assert result.returncode == ExitCode.OK
    rows = json.loads(result.stdout)
    assert isinstance(rows, list)
    assert rows, f"the {name} listing should not be empty for this fixture"

    for column in LISTINGS_BY_NAME[name].columns:
        assert column in rows[0], f"{name} rows must carry the {column!r} column"


def test_nodes_listing_shows_every_node(supervisor_dir: Path, populated: Path) -> None:
    """Structural assertion, not merely a non-empty check."""
    rows = json.loads(
        run_cli(_listing_arguments("nodes", ["--json"]), supervisor_dir).stdout
    )

    titles = {row["title"] for row in rows}
    assert titles == {"runnable slice", "awaiting review"}


def test_blocked_listing_names_what_each_node_waits_on(
    supervisor_dir: Path, populated: Path
) -> None:
    """ "On whom" is answered without a second call."""
    rows = json.loads(
        run_cli(_listing_arguments("blocked", ["--json"]), supervisor_dir).stdout
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "awaiting review"
    assert rows[0]["blocked_on"] == "judge"
    assert rows[0]["context"] == "needs a verdict"


def test_blocked_listing_carries_the_id_a_resolution_names(
    supervisor_dir: Path, populated: Path
) -> None:
    rows = json.loads(
        run_cli(_listing_arguments("blocked", ["--json"]), supervisor_dir).stdout
    )

    with Store.open_read_only(populated) as store:
        state = store.blocked_state_for(rows[0]["node_id"])
    assert state is not None
    assert rows[0]["blocked_state_id"] == state.id


def test_journal_listing_shows_resolved_and_unresolved(
    supervisor_dir: Path, populated: Path
) -> None:
    """The default listing is the whole history."""
    rows = json.loads(
        run_cli(_listing_arguments("journal", ["--json"]), supervisor_dir).stdout
    )

    outcomes = {row["outcome"] for row in rows}
    assert len(rows) == 2
    assert outcomes == {"completed", ""}


def test_journal_unresolved_returns_only_unresolved_entries(
    supervisor_dir: Path, populated: Path
) -> None:
    """``--unresolved`` is what a human uses to see what is still in flight."""
    rows = json.loads(
        run_cli(
            _listing_arguments("journal", ["--unresolved", "--json"]),
            supervisor_dir,
        ).stdout
    )

    assert len(rows) == 1
    assert rows[0]["outcome"] == ""
    assert rows[0]["kind"] == "cf_write"


def test_journal_listing_shows_the_awaits_routing_flag_in_json(
    supervisor_dir: Path, populated: Path
) -> None:
    """The resolved ``sq_run`` awaits routing; the open ``cf_write`` does not."""
    rows = json.loads(
        run_cli(_listing_arguments("journal", ["--json"]), supervisor_dir).stdout
    )

    assert {row["kind"]: row["awaits_routing"] for row in rows} == {
        "sq_run": True,
        "cf_write": False,
    }


def test_journal_table_spells_the_awaits_routing_flag_as_json_does(
    supervisor_dir: Path, populated: Path
) -> None:
    lines = run_cli(_listing_arguments("journal"), supervisor_dir).stdout.splitlines()
    # Cells can be empty (an unresolved outcome), so read by the header's offsets.
    kind_at = lines[0].index("kind")
    flag_at = lines[0].index("awaits_routing")
    body = {line[kind_at:].split()[0]: line[flag_at:].split()[0] for line in lines[2:]}

    assert body == {"sq_run": "true", "cf_write": "false"}


def test_projects_listing_finds_the_store(
    supervisor_dir: Path, populated: Path
) -> None:
    """``projects`` reads the supervisor directory rather than a store."""
    rows = json.loads(run_cli(["inspect", "projects", "--json"], supervisor_dir).stdout)

    assert [row["project_id"] for row in rows] == [PROJECT]


def test_projects_against_an_empty_directory_returns_empty(
    supervisor_dir: Path,
) -> None:
    """A supervisor that has never run is a valid state, not a failure."""
    result = run_cli(["inspect", "projects", "--json"], supervisor_dir)

    assert result.returncode == ExitCode.OK
    assert json.loads(result.stdout) == []


def test_an_empty_listing_says_so_in_table_form(supervisor_dir: Path) -> None:
    """The table form distinguishes 'no rows' from a broken command."""
    result = run_cli(["inspect", "projects"], supervisor_dir)

    assert result.returncode == ExitCode.OK
    assert result.stdout.strip() == "(none)"


# --------------------------------------------------------------------------
# The same listings, while the process is running
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", [listing.name for listing in LISTINGS])
def test_every_listing_works_while_the_process_is_running(
    supervisor_dir: Path, running_supervisor: None, name: str
) -> None:
    """Inspection reads a live store — the WAL case measured in Task 2.1."""
    result = run_cli(_listing_arguments(name, ["--json"]), supervisor_dir)

    assert result.returncode == ExitCode.OK
    assert isinstance(json.loads(result.stdout), list)


def test_listings_agree_running_and_stopped(
    supervisor_dir: Path, runs_dir: Path, populated: Path
) -> None:
    """The same store reads identically whether or not a writer is alive.

    Compared *after* the process has started and recovered, then again after
    it stops. Comparing across the start itself would be comparing two
    different states rather than two readers: recovery legitimately escalates
    the fixture's unresolved entry and blocks its node.
    """
    process = start_background(
        supervisor_dir, ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.05"]
    )
    try:
        await_running(supervisor_dir)
        while_running = run_cli(
            _listing_arguments("nodes", ["--json"]), supervisor_dir
        ).stdout
    finally:
        run_cli(["stop"], supervisor_dir)
        process.wait()
        process.cleanup()

    while_stopped = run_cli(
        _listing_arguments("nodes", ["--json"]), supervisor_dir
    ).stdout

    assert json.loads(while_running) == json.loads(while_stopped)


# --------------------------------------------------------------------------
# Inspection never writes
# --------------------------------------------------------------------------


def test_inspection_never_migrates(supervisor_dir: Path) -> None:
    """A version-2 store is left at version 2, checked against the file.

    The stamped version is read directly afterward rather than inferred from
    the command's exit status: a command that migrated and then succeeded
    would pass an exit-code-only check.
    """
    project_store_file = supervisor_dir / f"{PROJECT}.sqlite3"
    connection = sqlite3.connect(project_store_file)
    try:
        migrate(connection, expected_version=EXPECTED_SCHEMA_VERSION - 1)
    finally:
        connection.close()

    result = run_cli(_listing_arguments("nodes"), supervisor_dir)

    assert result.returncode != ExitCode.OK, "an unmigrated store cannot be read"

    verifier = sqlite3.connect(project_store_file)
    try:
        assert read_schema_version(verifier) == EXPECTED_SCHEMA_VERSION - 1
    finally:
        verifier.close()


def test_inspection_does_not_create_a_store(supervisor_dir: Path) -> None:
    """Inspecting a project with no store leaves the filesystem alone."""
    result = run_cli(["inspect", "nodes", "--project", "never-existed"], supervisor_dir)

    assert result.returncode != ExitCode.OK
    assert not (supervisor_dir / "never-existed.sqlite3").exists()
    assert list(supervisor_dir.iterdir()) == []


def test_inspection_leaves_a_populated_store_byte_identical(
    supervisor_dir: Path, populated: Path
) -> None:
    """Every listing, run in turn, mutates nothing.

    Compares the store file's bytes before and after, which catches a write
    that a row-level comparison might miss.
    """
    before = populated.read_bytes()

    for listing in LISTINGS:
        run_cli(_listing_arguments(listing.name), supervisor_dir)
        run_cli(_listing_arguments(listing.name, ["--json"]), supervisor_dir)

    assert populated.read_bytes() == before


# --------------------------------------------------------------------------
# The registry is the structural definition
# --------------------------------------------------------------------------


def test_subcommand_names_derive_from_the_registry(supervisor_dir: Path) -> None:
    """Every registered listing is reachable as a subcommand, and only those.

    This is what makes slice 104's addition a registry entry rather than an
    edit to the parser: the names come from the registry, never the reverse.
    """
    from amoeba.cli.main import build_parser

    parser = build_parser()
    help_text = parser.format_help()

    assert "inspect" in help_text

    for listing in LISTINGS:
        result = run_cli(["inspect", listing.name, "--help"], supervisor_dir)
        assert result.returncode == ExitCode.OK


def test_an_unregistered_listing_is_rejected(supervisor_dir: Path) -> None:
    """A subcommand that is not in the registry does not exist."""
    result = run_cli(["inspect", "not-a-listing", "--project", PROJECT], supervisor_dir)

    assert result.returncode != ExitCode.OK
    assert "invalid choice" in result.stderr


def test_the_registered_listings_are_pinned() -> None:
    registered = {listing.name for listing in LISTINGS}

    assert registered == {
        PROJECTS_LISTING,
        "nodes",
        "blocked",
        "journal",
        # Slice 103.
        "inbox",
        "submissions",
        "messages",
        # Slice 104.
        "verdicts",
        "findings",
        "changes",
        # Slice 106.
        "watches",
        "detections",
        # Slice 107.
        "checks",
        "calibration",
        # Slice 108.
        "cf-links",
        "cf-snapshots",
        # Slice 124.
        "desired-states",
    }


def test_only_project_listings_require_a_project(supervisor_dir: Path) -> None:
    """``projects`` takes no ``--project``; the rest require one."""
    assert set(PROJECT_LISTINGS) == {
        "nodes",
        "blocked",
        "journal",
        "submissions",
        "messages",
        "verdicts",
        "findings",
        "changes",
        # Slice 106.
        "watches",
        "detections",
        # Slice 107.
        "checks",
        "calibration",
        # Slice 108.
        "cf-links",
        "cf-snapshots",
        # Slice 124.
        "desired-states",
    }

    missing_project = run_cli(["inspect", "nodes"], supervisor_dir)
    assert missing_project.returncode != ExitCode.OK
