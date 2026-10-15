"""``amoeba feed`` through the real CLI as a subprocess."""

from __future__ import annotations

import json
import queue
import signal
import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from cli_harness import COMMAND_TIMEOUT_SECONDS, cli_environment, run_cli

from amoeba.cli.main import ExitCode
from amoeba.store import NodeKind, Store
from amoeba.store.paths import project_store_path

PROJECT = "demo"
CHANGE_KEYS = {
    "seq",
    "project_id",
    "kind",
    "node_id",
    "subject_id",
    "payload",
    "recorded_at",
}
#: How long a running follower may take to print a new change. Generous.
LINE_TIMEOUT_SECONDS = 10.0


class _Follower:
    """``amoeba feed --follow`` in the background, with its stdout as a queue."""

    def __init__(self, supervisor_dir: Path, *arguments: str) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-m", "amoeba.cli.main", "feed", "--follow", *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=cli_environment(supervisor_dir),
        )
        self._lines: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._lines.put(line)

    def next_change(self) -> dict[str, object]:
        return json.loads(self._lines.get(timeout=LINE_TIMEOUT_SECONDS))

    def cleanup(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=COMMAND_TIMEOUT_SECONDS)


@pytest.fixture
def writer(supervisor_dir: Path) -> Iterator[Store]:
    with Store.open(project_store_path(supervisor_dir, PROJECT)) as store:
        yield store


def _add_node(store: Store) -> str:
    return store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n").id


def _lines(stdout: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in stdout.splitlines()]


def _change_count(store: Store) -> int:
    return len(store.changes(PROJECT, limit=10_000))


def test_feed_prints_every_change_as_a_json_line(
    supervisor_dir: Path, writer: Store
) -> None:
    ids = [_add_node(writer) for _ in range(3)]

    result = run_cli(["feed", "--project", PROJECT], supervisor_dir)

    assert result.returncode == ExitCode.OK, result.stderr
    lines = _lines(result.stdout)
    assert [set(line) for line in lines] == [CHANGE_KEYS] * 3
    assert [line["node_id"] for line in lines] == ids
    assert _change_count(writer) == 3


def test_after_prints_only_later_changes(supervisor_dir: Path, writer: Store) -> None:
    for _ in range(4):
        _add_node(writer)
    result = run_cli(["feed", "--project", PROJECT, "--after", "2"], supervisor_dir)
    assert [line["seq"] for line in _lines(result.stdout)] == [3, 4]


def test_an_unknown_project_exits_like_inspect_and_prints_nothing(
    supervisor_dir: Path, writer: Store
) -> None:
    feed = run_cli(["feed", "--project", "nobody"], supervisor_dir)
    inspect = run_cli(["inspect", "nodes", "--project", "nobody"], supervisor_dir)
    assert feed.returncode == inspect.returncode != ExitCode.OK
    assert feed.stdout == ""


def test_a_negative_after_is_refused(supervisor_dir: Path) -> None:
    result = run_cli(["feed", "--project", PROJECT, "--after", "-1"], supervisor_dir)
    assert result.returncode != ExitCode.OK


def test_follow_prints_existing_then_new_changes_and_exits_on_sigterm(
    supervisor_dir: Path, writer: Store
) -> None:
    first = _add_node(writer)
    follower = _Follower(supervisor_dir, "--project", PROJECT)
    try:
        assert follower.next_change()["node_id"] == first
        second = _add_node(writer)
        assert follower.next_change()["node_id"] == second
        follower.process.send_signal(signal.SIGTERM)
        assert follower.process.wait(timeout=COMMAND_TIMEOUT_SECONDS) == ExitCode.OK
    finally:
        follower.cleanup()
    assert _change_count(writer) == 2


def test_a_killed_follower_resumes_with_no_gap_and_no_repeat(
    supervisor_dir: Path, writer: Store
) -> None:
    for _ in range(3):
        _add_node(writer)
    follower = _Follower(supervisor_dir, "--project", PROJECT)
    try:
        seen = [follower.next_change()["seq"] for _ in range(2)]
        follower.process.kill()
    finally:
        follower.cleanup()
    for _ in range(2):
        _add_node(writer)

    rest = run_cli(
        ["feed", "--project", PROJECT, "--after", str(seen[-1])], supervisor_dir
    )

    seqs = seen + [line["seq"] for line in _lines(rest.stdout)]
    assert seqs == [1, 2, 3, 4, 5]
    assert _change_count(writer) == 5
