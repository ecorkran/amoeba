"""``wake-run`` when a step gets no reply or is refused: D11's rows (slice 262)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from process_containment import contained_popen
from store.message_support import NOW

from amoeba.client.errors import HubRefusedError, HubUnreachableError
from amoeba.operations.processes import WaitableChild
from amoeba.operations.steps.model_base import Step, StepModel
from amoeba.operations.steps.models import WAKE_FINISH, WAKE_READ, WAKE_SET_PID
from amoeba.operations.store_steps import LocalSteps
from amoeba.operations.wake_run import run_wake
from amoeba.store.vocabulary import WakeOutcome
from amoeba.wire.protocol import RefusalCode
from operations.message_support import message_deps
from operations.release_support import SettableClock
from operations.wake_run_support import (
    WAKE_ID,
    claimed_store,
    local_steps,
    probe_command,
    process_is_gone,
    stored_row,
    wait_until,
)


class FaultySteps:
    """``Steps`` that fail the named step as a hub would, and run the rest locally."""

    def __init__(self, inner: LocalSteps, failing: dict[str, Exception]) -> None:
        self._inner = inner
        self._failing = failing

    def run[Request: StepModel, Reply: StepModel](
        self, step: Step[Request, Reply], request: Request
    ) -> Reply:
        failure = self._failing.get(step.name)
        if failure is not None:
            raise failure
        return self._inner.run(step, request)


def _clock() -> SettableClock:
    clock = SettableClock()
    clock.now = NOW
    return clock


def _steps(tmp_path: Path, failing: dict[str, Exception], command: str) -> FaultySteps:
    store, _ = claimed_store(tmp_path, command)
    return FaultySteps(local_steps(store, message_deps(tmp_path, _clock())), failing)


REFUSED = HubRefusedError("the machine was removed", RefusalCode.BAD_TOKEN)
UNREACHABLE = HubUnreachableError("no reply")


@pytest.mark.parametrize("failure", [UNREACHABLE, REFUSED], ids=["no_reply", "refused"])
def test_wake_read_failing_starts_nothing(tmp_path: Path, failure: Exception) -> None:
    steps = _steps(tmp_path, {WAKE_READ.name: failure}, probe_command(tmp_path))

    with pytest.raises(type(failure)):
        run_wake(steps, WAKE_ID, popen=contained_popen)

    assert not (tmp_path / "seen.json").exists()
    assert stored_row(tmp_path).command_pid is None


def test_wake_set_pid_with_no_reply_is_a_warning_and_the_wake_goes_on(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    steps = _steps(tmp_path, {WAKE_SET_PID.name: UNREACHABLE}, probe_command(tmp_path))
    caplog.set_level(logging.WARNING)

    outcome = run_wake(steps, WAKE_ID, popen=contained_popen)

    row = stored_row(tmp_path)
    assert outcome is WakeOutcome.EXITED
    assert row.command_pid is None  # the row shows no pid; wake_finish still ended it
    assert row.outcome is WakeOutcome.EXITED
    assert "could not record the command pid" in caplog.text


def test_wake_set_pid_refused_stops_the_commands_process_group(
    tmp_path: Path,
) -> None:
    started: list[int] = []

    def recording_popen(*args: object, **kwargs: object) -> WaitableChild:
        child: WaitableChild = contained_popen(*args, **kwargs)  # type: ignore[arg-type]
        started.append(child.pid)
        return child

    steps = _steps(
        tmp_path,
        {WAKE_SET_PID.name: REFUSED},
        probe_command(tmp_path, mode="sleep"),
    )

    with pytest.raises(HubRefusedError):
        run_wake(steps, WAKE_ID, popen=recording_popen)

    (pid,) = started
    assert wait_until(lambda: process_is_gone(pid))
    assert stored_row(tmp_path).ended_at is None


@pytest.mark.parametrize("failure", [UNREACHABLE, REFUSED], ids=["no_reply", "refused"])
def test_wake_finish_failing_raises_after_the_command_ended(
    tmp_path: Path, failure: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    steps = _steps(tmp_path, {WAKE_FINISH.name: failure}, probe_command(tmp_path))
    caplog.set_level(logging.ERROR)

    with pytest.raises(type(failure)):
        run_wake(steps, WAKE_ID, popen=contained_popen)

    row = stored_row(tmp_path)
    assert (row.ended_at, row.outcome) == (None, None)  # unended until its deadline
    assert row.command_pid is not None
    assert "could not record how it ended" in caplog.text
