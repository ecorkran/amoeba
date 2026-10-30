"""Rig helpers for the dispatch-check tests: a real git checkout and config knobs.

They build the pieces the stub ``cf`` reads (``tests/cf_stub_gates.py``) and return the
environment knobs a ``CfWorld.run`` / ``DispatchRig.use_world`` call takes.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from cf_stub_gates import CONFIG_ENV, write_config_values

from runner.git_repo import commit_file, make_repo

RIG_GITIGNORE = "*\n!.gitignore\n!README.md\n"


def rig_checkout(path: Path) -> Path:
    """A clean git repository on ``main`` that stays clean as a rig writes into it.

    Runs write review files and logs into a checkout; Squadron commits its own output,
    so a real checkout would stay clean. Ignoring everything but ``README.md`` keeps
    these ones clean too. A test that wants a dirty tree edits ``README.md``.
    """
    repo = make_repo(path)
    commit_file(repo, ".gitignore", RIG_GITIGNORE, "ignore rig output")
    return repo


def git_checkout(checkout: Path, branch: str = "main") -> Path:
    """Make ``checkout`` a real git repository on ``branch`` with one commit.

    A directory that already is one (a dispatch rig's checkout) is left as it is.
    """
    if (checkout / ".git").exists():
        return checkout
    return make_repo(checkout, branch)


def config_knobs(tmp_path: Path, values: Mapping[str, str]) -> dict[str, str]:
    """The knob that sets what ``cf config get`` answers for each key."""
    return {CONFIG_ENV: str(write_config_values(tmp_path / "config.json", values))}
