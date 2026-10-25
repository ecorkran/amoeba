"""The shipped table is read from the package and passes the real parser."""

from __future__ import annotations

from importlib import resources

from amoeba.runner.routing.table import parse_table

DEFAULT_TABLE_RESOURCE = "tables/default.yaml"


def _shipped_text() -> str:
    package = resources.files("amoeba.runner.routing")
    return package.joinpath(DEFAULT_TABLE_RESOURCE).read_text(encoding="utf-8")


def test_the_shipped_table_parses() -> None:
    table = parse_table(_shipped_text())
    assert table.time_bounds_minutes == {"P4": 240, "P5": 240, "P6": 720}


def test_the_shipped_rule_ids_are_in_the_designed_order() -> None:
    table = parse_table(_shipped_text())
    assert [rule.id for rule in table.rules] == [
        "advance-on-stated-pass",
        "advance-on-accepted-review",
        "rerun-new-concerns",
        "escalate-completed-concerns",
        "escalate-everything-else",
    ]
