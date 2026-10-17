"""Slice 108 end to end, through the real CLI as subprocesses.

A project links the fixture's amoeba entry; a follower and the process run
against a scratch Context Forge directory. A pointer move is written the way CF
writes (temp file, then rename), the process is killed with SIGKILL, the file
moves again while it is down, and a restart picks that move up. The follower and
``inspect cf-snapshots`` must agree, with one change per rewrite and nothing
recorded twice. No working ``cf`` is on ``PATH``: a failing one is first, so the
``unavailable`` label path runs.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from cf_fixture import AMOEBA_ID, DEFAULT_WORKTREE_ID, derived, entry, fixture_bytes
from detection_e2e_harness import ChangeLine, DetectionE2E

PROJECT = "demo"
KIND = "cf_project_changed"
UNAVAILABLE = "unavailable"


@pytest.fixture
def e2e(supervisor_dir: Path, tmp_path: Path) -> Iterator[DetectionE2E]:
    harness = DetectionE2E(supervisor_dir, tmp_path)
    broken_bin = tmp_path / "broken-cf-bin"
    broken_bin.mkdir()
    cf = broken_bin / "cf"
    cf.write_text("#!/bin/sh\nexit 1\n")
    cf.chmod(0o755)
    harness.environment["PATH"] = f"{broken_bin}:{harness.environment['PATH']}"
    yield harness
    harness.cleanup()


@pytest.fixture
def cf_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "context-forge"
    directory.mkdir()
    return directory


def _write(cf_dir: Path, data: bytes) -> None:
    """Replace projects.json the way Context Forge does: temp file, then rename."""
    temporary = cf_dir / "projects.json.tmp"
    temporary.write_bytes(data)
    os.replace(temporary, cf_dir / "projects.json")


def _phase(phase: str) -> bytes:
    def move(entries: list[dict[str, Any]]) -> None:
        worktree = entry(entries, AMOEBA_ID)["worktrees"][0]
        assert worktree["id"] == DEFAULT_WORKTREE_ID
        worktree["developmentPhase"] = phase

    return derived(move)


def _cf_changes(lines: list[ChangeLine]) -> list[ChangeLine]:
    return [line for line in lines if line["kind"] == KIND]


def _at_least(count: int) -> Callable[[list[ChangeLine]], bool]:
    def enough(lines: list[ChangeLine]) -> bool:
        return len(_cf_changes(lines)) >= count

    return enough


def _moved(change: ChangeLine) -> list[dict[str, object]]:
    payload = cast("dict[str, object]", change["payload"])
    return cast("list[dict[str, object]]", payload["changed"])


def test_pointer_moves_survive_a_kill_and_restart_without_double_recording(
    e2e: DetectionE2E, cf_dir: Path
) -> None:
    _write(cf_dir, fixture_bytes())
    flags = ("--cf-data-dir", str(cf_dir))
    process = e2e.start_process(*flags)
    e2e.create_project(PROJECT)
    follower = e2e.start_follower(PROJECT)
    result = e2e.run(
        "submit", "link-cf-project", "--project", PROJECT, "--by", "pm",
        "--cf-project-id", AMOEBA_ID,
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    first = _cf_changes(follower.wait_for(_at_least(1)))[0]
    assert {change["field"] for change in _moved(first)} >= {"activeSlice"}

    _write(cf_dir, _phase("Phase 7: Testing"))
    second = _cf_changes(follower.wait_for(_at_least(2)))[1]
    assert [(c["field"], c["to"]) for c in _moved(second)] == [
        ("developmentPhase", "Phase 7: Testing")
    ]

    process.kill_and_wait()
    _write(cf_dir, _phase("Phase 8: Review"))
    e2e.start_process(*flags)
    lines = follower.wait_for(_at_least(3))

    changes = _cf_changes(lines)
    assert len(changes) == 3  # one per rewrite, nothing twice
    assert [(c["from"], c["to"]) for c in _moved(changes[2])] == [
        ("Phase 7: Testing", "Phase 8: Review")
    ]
    rows = e2e.inspect_json("cf-snapshots", PROJECT)
    assert [str(row["id"]) for row in rows] == [str(c["subject_id"]) for c in changes]
    assert {row["outcome"] for row in rows} == {"observed"}
    assert {row["cf_version_label"] for row in rows} == {UNAVAILABLE}
    assert [row["changed"] for row in rows] == [_moved(c) for c in changes]
    assert len(e2e.inspect_json("cf-links", PROJECT)) == 1
