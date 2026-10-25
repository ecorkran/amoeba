"""``amoeba inspect routing-decisions``, as a subprocess.

Covers what is specific to this listing: oldest-first order across nodes,
``--node``, and the ``recomputes`` column's three states.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cli_harness import run_cli
from evidence_harness import PROJECT, seed_node
from runner.routing.inputs_support import make_inputs
from runner.routing.table_support import table_text

from amoeba.cli.main import ExitCode
from amoeba.inspection.routing import (
    RECOMPUTES_ERROR_PREFIX,
    RECOMPUTES_NO,
    RECOMPUTES_YES,
    ROUTING_DECISION_COLUMNS,
    SHORT_VERSION_LENGTH,
)
from amoeba.runner.routing.table import parse_table
from amoeba.store import Route, RoutingDecisionInput, RoutingTableVersion, Store

ADVANCE_RULE = """\
- id: advance-completed
  when: {outcome: completed}
  route: advance
"""

#: A stored table written under a grammar this code does not read.
UNSUPPORTED_TABLE = table_text(ADVANCE_RULE).replace("format: 1", "format: 99")

LONG_VERSION = "sha256:" + "ab" * 20


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


def _record(
    store: Store,
    node_id: str,
    *,
    content: str,
    version: str,
    rule_id: str = "advance-completed",
    route: Route = Route.ADVANCE,
) -> None:
    store.record_routing_decision(
        RoutingDecisionInput(
            project_id=PROJECT,
            node_id=node_id,
            inputs=make_inputs(attempt=1).to_record(),
            rule_id=rule_id,
            table_version=version,
            amoeba_version="0.0.0-test",
            route=route,
            route_parameters={},
        ),
        table=RoutingTableVersion(version, content),
        effect=None,
        attempt_step="slice_design",
    )


@pytest.fixture
def seeded(supervisor_dir: Path) -> tuple[Path, str, str]:
    """Two nodes; first, second and third decisions in time order across them."""
    good = table_text(ADVANCE_RULE)
    version = parse_table(good).version
    with Store.open(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        first, second = seed_node(store), seed_node(store)
        _record(store, second, content=good, version=version)
        _record(store, first, content=good, version=version)
        _record(store, first, content=good, version=version, rule_id="other-rule")
    return supervisor_dir, first, second


def _rows(supervisor_dir: Path, *arguments: str) -> list[dict[str, object]]:
    result = run_cli(
        ["inspect", "routing-decisions", "--project", PROJECT, *arguments, "--json"],
        supervisor_dir,
    )
    assert result.returncode == ExitCode.OK, result.stderr
    rows: list[dict[str, object]] = json.loads(result.stdout)
    return rows


def test_rows_are_oldest_first_across_nodes(seeded: tuple[Path, str, str]) -> None:
    supervisor_dir, first, second = seeded
    rows = _rows(supervisor_dir)
    assert [row["node_id"] for row in rows] == [second, first, first]
    assert [row["decided_at"] for row in rows] == sorted(
        str(row["decided_at"]) for row in rows
    )


def test_json_rows_carry_every_column_and_the_full_version(
    seeded: tuple[Path, str, str],
) -> None:
    rows = _rows(seeded[0])
    assert tuple(rows[0]) == ROUTING_DECISION_COLUMNS
    assert len(str(rows[0]["table_version"])) > SHORT_VERSION_LENGTH
    assert rows[0]["step"] == "slice_design"
    assert rows[0]["attempt"] == 1


def test_node_narrows_to_one_node(seeded: tuple[Path, str, str]) -> None:
    supervisor_dir, first, _ = seeded
    rows = _rows(supervisor_dir, "--node", first)
    assert [row["node_id"] for row in rows] == [first, first]


def test_the_table_form_shortens_the_version(seeded: tuple[Path, str, str]) -> None:
    result = run_cli(["inspect", "routing-decisions", "--project", PROJECT], seeded[0])
    assert result.returncode == ExitCode.OK, result.stderr
    full = str(_rows(seeded[0])[0]["table_version"])
    assert full[:SHORT_VERSION_LENGTH] in result.stdout
    assert full not in result.stdout


def test_a_decision_the_table_reproduces_shows_yes(
    seeded: tuple[Path, str, str],
) -> None:
    assert _rows(seeded[0])[0]["recomputes"] == RECOMPUTES_YES


def test_a_decision_the_table_would_now_decide_differently_shows_no(
    seeded: tuple[Path, str, str],
) -> None:
    # The two decisions on the first node: the second names a rule the table lacks.
    assert _rows(seeded[0])[2]["recomputes"] == RECOMPUTES_NO


def test_an_unsupported_stored_format_shows_an_error_not_no(
    supervisor_dir: Path,
) -> None:
    with Store.open(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        node = seed_node(store)
        _record(store, node, content=UNSUPPORTED_TABLE, version=LONG_VERSION)
    recomputes = str(_rows(supervisor_dir)[0]["recomputes"])
    assert recomputes.startswith(RECOMPUTES_ERROR_PREFIX)
    assert "format" in recomputes


def test_an_empty_project_lists_no_rows(supervisor_dir: Path) -> None:
    with Store.open(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        seed_node(store)
    assert _rows(supervisor_dir) == []
