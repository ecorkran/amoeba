"""Small routing tables for tests, built through the real parser."""

from __future__ import annotations

from textwrap import dedent

from amoeba.runner.lifecycle.steps import PIPELINE_P4, PIPELINE_P5, PIPELINE_P6
from amoeba.runner.routing.table import RoutingTable, parse_table

#: The Amoeba package version a test tenant is given; not a real release.
TEST_AMOEBA_VERSION = "0.0.0-test"

#: Every pipeline a table must bound, with a generous default.
DEFAULT_BOUNDS = {PIPELINE_P4: 240, PIPELINE_P5: 240, PIPELINE_P6: 720}

CATCH_ALL = """\
  - id: catch-all
    when: {}
    route: escalate
    judge_eligible: false
"""


def table_text(
    rules: str = "",
    *,
    bounds: dict[str, int] | None = None,
    catch_all: bool = True,
) -> str:
    """A table file: ``rules`` (indented ``  - id: ...`` items), then a catch-all."""
    bound_lines = "\n".join(
        f"  {pipeline}: {minutes}"
        for pipeline, minutes in (DEFAULT_BOUNDS if bounds is None else bounds).items()
    )
    body = dedent(rules.strip("\n")) if rules else ""
    indented = "\n".join(f"  {line}" if line else line for line in body.splitlines())
    sections = [
        "format: 1",
        f"time_bounds_minutes:\n{bound_lines}",
        "rules:",
        indented,
        CATCH_ALL.rstrip("\n") if catch_all else "",
    ]
    return "\n".join(part for part in sections if part) + "\n"


def small_table(
    rules: str = "",
    *,
    bounds: dict[str, int] | None = None,
    catch_all: bool = True,
) -> RoutingTable:
    """Parse a small table. The catch-all and the pipeline bounds are filled in.

    ``rules`` is written at the top level of the list: each item starts with
    ``- id: ...`` at column 0 and is indented here. Pass ``bounds`` to override
    the defaults, for example a one-minute bound for an overrun test.
    """
    return parse_table(table_text(rules, bounds=bounds, catch_all=catch_all))
