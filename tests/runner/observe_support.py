"""Fakes shared by the observe tests: clocks, a scripted poll, a journal entry."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from amoeba.process import (
    PollFailure,
    RunOutcome,
    RunOutcomeDocument,
    RunPoll,
)
from amoeba.runner.budget import TickBudget
from amoeba.runner.faults import NodeContext, TickFaults
from amoeba.runner.launch import (
    LAUNCH_LOGS_DIRNAME,
    PARAM_PARAMS,
    PARAM_PIPELINE,
    LaunchTracker,
    log_paths,
)
from amoeba.runner.observe import RunObserver
from amoeba.runner.resolutions.confirm import ResumedFrom
from amoeba.store import PARAM_RUN_ID, CommandKind, JournalEntry

NOW = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
GRACE = 60.0

#: The Amoeba package version a test tenant is given; not a real release.
TEST_AMOEBA_VERSION = "0.0.0-test"
INTERVAL = 15.0


class Clock:
    """One clock for both the wall and the monotonic reading."""

    def __init__(self) -> None:
        self.seconds = 0.0

    def monotonic(self) -> float:
        return self.seconds

    def wall(self) -> datetime:
        return NOW + timedelta(seconds=self.seconds)


class Child:
    def __init__(self, exit_code: int | None = None) -> None:
        self.exit_code = exit_code

    def poll(self) -> int | None:
        return self.exit_code


class Host:
    stop_requested = False


class ScriptedPoll:
    """Answers each poll from a queue, recording what was asked."""

    def __init__(self, *answers: RunPoll) -> None:
        self.answers = list(answers)
        self.asked: list[str] = []
        self.on_call: Any = None

    def __call__(self, run_id: str) -> RunPoll:
        self.asked.append(run_id)
        if self.on_call is not None:
            self.on_call()
        return self.answers.pop(0)


@dataclass
class CfReply:
    """One canned answer to a ``cf`` command."""

    stdout: str = ""
    returncode: int = 0
    stderr: str = ""


def command_key(argv: list[str]) -> str:
    """``status``, ``list initiatives`` or ``list slices <index>``."""
    if argv[1] == "status":
        return "status"
    return " ".join(argv[1:3] if argv[2] == "initiatives" else argv[1:4])


class FakeCf:
    """A ``cf`` runner answering the probe commands, or whatever it is told.

    ``replies`` maps a command key (see :func:`command_key`), optionally suffixed
    ``@<cf project id>`` for one link, to a :class:`CfReply` or an exception to
    raise. ``stdout`` maps the first word (``status``, ``list``) to output, as the
    probe tests set it.
    """

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.stdout: dict[str, str] = {}
        self.replies: dict[str, CfReply | BaseException] = {}
        self.returncode = 0
        self.error: BaseException | None = None
        self.on_call: Any = None

    def __call__(
        self, argv: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        if self.on_call is not None:
            self.on_call()
        if self.error is not None:
            raise self.error
        key = command_key(argv)
        reply = self.replies.get(f"{key}@{argv[-1]}", self.replies.get(key))
        if isinstance(reply, BaseException):
            raise reply
        if reply is not None:
            return subprocess.CompletedProcess(
                argv, reply.returncode, reply.stdout, reply.stderr
            )
        command = argv[1]
        default = '{"project": "stub"}' if command == "status" else "[]"
        return subprocess.CompletedProcess(
            argv, self.returncode, self.stdout.get(command, default), ""
        )


def document(run_id: str, outcome: RunOutcome) -> RunOutcomeDocument:
    return RunOutcomeDocument(run_id=run_id, outcome=outcome, status=outcome.value)


def failure(reason: str = "sq missing") -> PollFailure:
    return PollFailure(reason)


def entry(index: int = 1, issued_ago: float = 0.0) -> JournalEntry:
    return JournalEntry(
        id=f"entry-{index}",
        project_id="demo",
        node_id=f"node-{index}",
        kind=CommandKind.SQ_RUN,
        parameters={
            PARAM_PIPELINE: "P4",
            PARAM_PARAMS: {},
            PARAM_RUN_ID: f"run-{index}",
        },
        issued_at=NOW - timedelta(seconds=issued_ago),
    )


class Rig:
    """An observer over a temporary supervisor directory."""

    def __init__(self, tmp_path: Path, *answers: RunPoll) -> None:
        self.supervisor_dir = tmp_path
        (tmp_path / LAUNCH_LOGS_DIRNAME).mkdir()
        self.clock = Clock()
        self.poll = ScriptedPoll(*answers)
        self.tracker = LaunchTracker()
        self.faults = TickFaults()
        self.context = NodeContext()
        #: Entry id to the pause a resume was decided on (slice 127, D6).
        self.resumed_from: dict[str, ResumedFrom | None] = {}
        self.deadline = 1_000_000.0
        self.observer = RunObserver(
            supervisor_dir=tmp_path,
            tracker=self.tracker,
            poll=self.poll,
            now=self.clock.wall,
            monotonic=self.clock.monotonic,
            launch_grace_seconds=GRACE,
            run_poll_interval_seconds=INTERVAL,
        )

    def budget(self) -> TickBudget:
        return TickBudget(self.deadline, Host(), self.clock.monotonic)

    def launch(self, e: object, child: Child, stderr: str | None = None) -> None:
        assert isinstance(e, JournalEntry)
        self.tracker.track(e.id, child)
        if stderr is not None:
            log_paths(self.supervisor_dir, e.id).stderr.write_text(stderr)
        else:
            log_paths(self.supervisor_dir, e.id).stderr.touch()

    def observe(self, *entries: JournalEntry):  # noqa: ANN201
        return self.observer.observe(
            entries, self.budget(), self.faults, self.context, self.resumed_from
        )
