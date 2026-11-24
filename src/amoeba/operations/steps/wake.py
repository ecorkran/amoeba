"""The wake wrapper's steps, hub side (262 D4, D8, D11).

``wake_read`` hands a machine the command of its own unended wake with no pid yet;
``wake_set_pid`` and ``wake_finish`` record it. None loads a config: the deadline is in
the row, and a broken config must not stop a wake's end from being recorded.
"""

from __future__ import annotations

from amoeba.operations.steps.context import StepContext
from amoeba.operations.steps.models_wake import (
    WakeFinishReply,
    WakeFinishRequest,
    WakeReadReply,
    WakeReadRequest,
    WakeSetPidReply,
    WakeSetPidRequest,
    WakeToRun,
)
from amoeba.store.machines import acting_machine_id
from amoeba.store.wakes import finish_wake, get_wake, set_command_pid


def wake_read(context: StepContext, request: WakeReadRequest) -> WakeReadReply:
    """The wake to run, or why none can: no such row, not this machine's, already
    ended, no checkout, or a command already running."""
    transaction = context.transaction
    wake = get_wake(transaction, request.wake_id)
    if wake is None:
        return WakeReadReply(problem=f"there is no wake {request.wake_id!r}")
    if wake.machine_id != acting_machine_id(transaction):
        return WakeReadReply(
            problem=f"wake {request.wake_id!r} belongs to another machine"
        )
    if wake.ended_at is not None:
        return WakeReadReply(problem=f"wake {request.wake_id!r} has already ended")
    if wake.directory is None:
        return WakeReadReply(
            problem=f"wake {request.wake_id!r} has no checkout to run in"
        )
    if wake.command_pid is not None:
        return WakeReadReply(
            problem=f"wake {request.wake_id!r} already has a command running"
        )
    seconds_left = max(0.0, (wake.deadline_at - context.now).total_seconds())
    return WakeReadReply(
        wake=WakeToRun(
            directory=wake.directory, command=wake.command, seconds_left=seconds_left
        )
    )


def wake_set_pid(context: StepContext, request: WakeSetPidRequest) -> WakeSetPidReply:
    """Record the command's pid, once: only the first run of a wake records one."""
    recorded = set_command_pid(context.transaction, request.wake_id, request.pid)
    return WakeSetPidReply(recorded=recorded)


def wake_finish(context: StepContext, request: WakeFinishRequest) -> WakeFinishReply:
    """End the row once; a row that already ended keeps its record."""
    ended = finish_wake(
        context.transaction,
        request.wake_id,
        request.outcome,
        request.exit_code,
        request.detail,
        context.now,
    )
    return WakeFinishReply(ended=ended)
