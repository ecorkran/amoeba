"""Replay recorded ``cf get --json`` output: a fake ``CfRun`` and a fake ``cf`` script.

The recordings in ``tests/fixtures/context_forge`` are real Context Forge output.
Like Context Forge, a replayed error document (``"error": true``) goes to stderr
with a non-zero exit, and any other document goes to stdout with exit 0.
"""

from __future__ import annotations

import json
import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from amoeba.upstream.context_forge.cli_call import CfRun

FIXTURES = Path(__file__).parent / "fixtures" / "context_forge"

DEFAULT_WORKTREE = "default_worktree"
NON_DEFAULT_WORKTREE = "non_default_worktree"
SUBDIRECTORY = "subdirectory"
OUTSIDE_ANY_PROJECT = "outside_any_project"

#: What a replayed failure prints: a non-zero exit with no JSON document.
FAILURE_MESSAGE = "cf: simulated failure"
FAILURE_EXIT_CODE = 1


def fixture_text(name: str) -> str:
    """The recorded document called ``name``, exactly as captured."""
    return (FIXTURES / f"{name}.json").read_text(encoding="utf-8")


def fixture_document(name: str) -> dict[str, Any]:
    """The recorded document called ``name``, parsed."""
    document: dict[str, Any] = json.loads(fixture_text(name))
    return document


def replay(argv: Sequence[str], name: str) -> subprocess.CompletedProcess[str]:
    """The process ``cf`` would have returned for the recorded document ``name``."""
    text = fixture_text(name)
    if fixture_document(name).get("error") is True:
        return subprocess.CompletedProcess(list(argv), FAILURE_EXIT_CODE, "", text)
    return subprocess.CompletedProcess(list(argv), 0, text, "")


def failure(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """A ``cf`` that exits non-zero printing no JSON."""
    return subprocess.CompletedProcess(
        list(argv), FAILURE_EXIT_CODE, "", FAILURE_MESSAGE
    )


def fake_cf_run(fixture: str | None) -> CfRun:
    """A ``CfRun`` replaying the recording ``fixture``; ``None`` replays a failure."""

    def run(argv: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return failure(argv) if fixture is None else replay(argv, fixture)

    return run


def write_fake_cf(bin_dir: Path, fixture: str | None) -> Path:
    """Write an executable ``cf`` into ``bin_dir`` for a ``PATH`` entry.

    One mode per script: replay the recording ``fixture``, or with ``None`` exit
    non-zero printing no JSON. Returns the script's path.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    if fixture is None:
        body = f"echo '{FAILURE_MESSAGE}' >&2\nexit {FAILURE_EXIT_CODE}\n"
    elif fixture_document(fixture).get("error") is True:
        path = FIXTURES / f"{fixture}.json"
        body = f"cat '{path}' >&2\nexit {FAILURE_EXIT_CODE}\n"
    else:
        body = f"cat '{FIXTURES / f'{fixture}.json'}'\n"
    script = bin_dir / "cf"
    script.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script
