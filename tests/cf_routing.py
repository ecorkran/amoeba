"""A ``cf`` that knows several projects: ``cf get --json`` routes by working directory
or ``-p`` reference, and ``cf list projects --json`` lists them (slice 240).

The recorded ``cf`` in ``cf_fixtures`` answers every lookup with one project. The
three-repo scenario needs a directory in each repo to be a different member, so this
script keeps a table of projects and answers from it. An unknown directory or reference
replays the recorded ``PROJECT_NOT_FOUND`` document, as the real ``cf`` prints it.
"""

from __future__ import annotations

import json
import stat
import sys
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from cf_fixtures import OUTSIDE_ANY_PROJECT, fixture_document, fixture_text

from amoeba.upstream.context_forge.target_read import CF_PROJECT_FLAG

_SCRIPT = textwrap.dedent(
    """\
    #!{python}
    import json
    import os
    import sys

    table = json.loads({table!r})
    base = json.loads({base!r})
    not_found = {not_found!r}
    arguments = sys.argv[1:]

    if arguments[:1] == ["list"]:
        print(json.dumps([
            {{"id": p["id"], "name": p["name"], "projectPath": p["path"],
              "isActive": False}}
            for p in table
        ]))
        sys.exit(0)
    if arguments[:1] != ["get"]:
        print("routing cf: unexpected arguments", arguments, file=sys.stderr)
        sys.exit(2)
    if {project_flag!r} in arguments:
        reference = arguments[arguments.index({project_flag!r}) + 1]
        found = next((p for p in table if reference in (p["id"], p["name"])), None)
    else:
        here = os.getcwd()
        found = next(
            (p for p in table
             if here == p["path"] or here.startswith(p["path"] + os.sep)),
            None,
        )
    if found is None:
        sys.stderr.write(not_found)
        sys.exit(1)
    print(json.dumps({{**base, "id": found["id"], "name": found["name"],
                      "projectPath": found["path"]}}))
    """
)


@dataclass(frozen=True)
class RoutedProject:
    """A project the routing ``cf`` knows."""

    id: str
    name: str
    path: Path


def write_routing_cf(bin_dir: Path, projects: Sequence[RoutedProject]) -> Path:
    """Write an executable ``cf`` into ``bin_dir`` that answers for ``projects``."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    table = [
        {"id": p.id, "name": p.name, "path": str(p.path.resolve())} for p in projects
    ]
    base = {
        key: value
        for key, value in fixture_document("default_worktree").items()
        if key in ("template", "customData")
    }
    script = bin_dir / "cf"
    script.write_text(
        _SCRIPT.format(
            python=sys.executable,
            table=json.dumps(table),
            base=json.dumps(base),
            not_found=fixture_text(OUTSIDE_ANY_PROJECT),
            project_flag=CF_PROJECT_FLAG,
        ),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script
