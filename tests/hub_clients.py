"""What each client machine of the two-machine fixture has of its own (slice 261, D15).

Every client home gets a ``bin`` directory first on its ``PATH`` with a stub ``cf`` and
a stub ``sq``, so one repo has a different Context Forge project id on each machine
(the way two machines' Context Forge data directories do), and a helper clones a repo
into a home with a chosen ``origin``. The real ``git`` is used. The hub's ``PATH`` holds
none of ``cf``, ``sq`` or ``git`` (``hub_fixture.hub_path``).

The ``cf`` stub reads ``cf-projects.json`` in the home: a directory (or any directory
below it) to the project there. A directory in none is Context Forge's own "not a
project" answer, from its recording.
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path
from typing import Final

from cf_fixtures import DEFAULT_WORKTREE, OUTSIDE_ANY_PROJECT, fixture_document
from git_repo import git, make_repo

PROJECTS_FILE: Final = "cf-projects.json"
RUNS_FILE: Final = "sq-runs.json"
BIN_DIRECTORY: Final = "bin"
#: The origin forms of one repo: what each machine's clone says (D3).
SSH_ORIGIN: Final = "git@github.com:org/shared-repo.git"
HTTPS_ORIGIN: Final = "https://github.com/org/shared-repo"

_CF_SCRIPT: Final = """#!{python}
import json, os, sys
from pathlib import Path

home = Path({home!r})
args = sys.argv[1:]
if args[:1] != ["get"]:
    sys.stderr.write("stub cf: unexpected command " + " ".join(args) + "\\n")
    sys.exit(1)
table_path = home / {projects!r}
table = json.loads(table_path.read_text()) if table_path.exists() else {{}}
here = Path(os.getcwd()).resolve()
for directory in (here, *here.parents):
    found = table.get(str(directory))
    if found is not None:
        print(json.dumps(found))
        sys.exit(0)
sys.stderr.write({missing!r})
sys.exit(1)
"""

_SQ_SCRIPT: Final = """#!{python}
import sys
from pathlib import Path

args = sys.argv[1:]
if args[:2] != ["runs", "list"]:
    sys.stderr.write("stub sq: unexpected command " + " ".join(args) + "\\n")
    sys.exit(1)
runs = Path({home!r}) / {runs!r}
print(runs.read_text() if runs.exists() else "[]")
"""


def _write_script(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def install_client_tools(home: Path) -> Path:
    """Write the stub ``cf`` and ``sq`` into ``home/bin``; returns that directory."""
    bin_dir = home / BIN_DIRECTORY
    bin_dir.mkdir(parents=True, exist_ok=True)
    missing = json.dumps(fixture_document(OUTSIDE_ANY_PROJECT))
    _write_script(
        bin_dir / "cf",
        _CF_SCRIPT.format(
            python=sys.executable,
            home=str(home),
            projects=PROJECTS_FILE,
            missing=missing,
        ),
    )
    _write_script(
        bin_dir / "sq",
        _SQ_SCRIPT.format(python=sys.executable, home=str(home), runs=RUNS_FILE),
    )
    return bin_dir


def register_project(
    home: Path, directory: Path, project_id: str, name: str, project_path: Path
) -> None:
    """Make the stub ``cf`` of ``home`` answer ``project_id`` for ``directory``."""
    table_path = home / PROJECTS_FILE
    table: dict[str, object] = (
        json.loads(table_path.read_text(encoding="utf-8"))
        if table_path.exists()
        else {}
    )
    document = {
        **fixture_document(DEFAULT_WORKTREE),
        "id": project_id,
        "name": name,
        "projectPath": str(project_path),
    }
    table[str(directory.resolve())] = document
    table_path.write_text(json.dumps(table), encoding="utf-8")


def clone_repo(
    home: Path,
    name: str,
    origin: str | None,
    project_id: str,
    project_name: str | None = None,
) -> Path:
    """A git repo ``home/repos/<name>`` with ``origin`` (none when ``None``) that the
    stub ``cf`` of ``home`` knows as ``project_id``. Returns the repo's path."""
    repo = make_repo(home / "repos" / name).resolve()
    if origin is not None:
        git(repo, "remote", "add", "origin", origin)
    register_project(home, repo, project_id, project_name or name, repo)
    return repo


def add_worktree(home: Path, repo: Path, name: str) -> Path:
    """A linked worktree of ``repo``: its own directory, the same project id, and its
    own directory as the project's path (Context Forge says so, 261 D7)."""
    tree = (home / "repos" / name).resolve()
    git(repo, "worktree", "add", "-q", "-b", f"{name}-branch", str(tree))
    table = json.loads((home / PROJECTS_FILE).read_text(encoding="utf-8"))
    known = table[str(repo.resolve())]
    register_project(home, tree, str(known["id"]), str(known["name"]), tree)
    return tree


def set_runs(home: Path, runs: list[dict[str, object]]) -> None:
    """What the stub ``sq runs list --json --all`` prints in ``home``."""
    (home / RUNS_FILE).write_text(json.dumps(runs), encoding="utf-8")
