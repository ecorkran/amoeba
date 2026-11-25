"""Work and answers through a session's ticks (slice 263, 8.4, D1, D7, D9, D12).

Both machines run in this process against one in-process hub (``two_homes``). A
session on ``alpha`` is the real tick and after-step; nothing else runs on ``alpha``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp_server.presence_rig import (
    FAST,
    RecordingOutbound,
    eventually,
    make_connection,
)
from operations.handle_rig import KEY, PAUSE, QUESTION, RUNNING_DOC
from operations.status_support import CfAnswer, FakeCf
from store.decision_support import CORE, LINT

from amoeba import wiring
from amoeba.answering.values import DeclineReason
from amoeba.mcp.after_runner import AfterRunner
from amoeba.mcp.in_process import run_in_process
from amoeba.mcp.presence import PresenceDeps, PresenceState
from amoeba.mcp.tick import run_ticks
from amoeba.mcp.tools import TOOLS
from amoeba.operations.answer import AnswerOutcome, AnswerResult
from amoeba.operations.decisions import DecisionsResult
from amoeba.operations.names import Door, OperationName
from amoeba.operations.resume_run import RESUME_RUN_COMMAND
from amoeba.store.questions import NewQuestion, insert_question
from amoeba.wire.times import TICK_TIMES
from amoeba.wiring_steps import steps_for
from hub.two_homes import ALPHA, BETA, Machine, TwoHomes, two_homes

CLIENT = "claude-code"
ANSWER_TOOL = next(spec for spec in TOOLS if spec.name is OperationName.ANSWER)
#: One slow poll of the resumed run, so a resume outlasts the cut-off below.
SLOW_POLL_SECONDS = 0.5
CLIENT_GIVES_UP_SECONDS = 1.0


@pytest.fixture
def homes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TwoHomes]:
    with two_homes(tmp_path, monkeypatch, (CORE, LINT)) as both:
        both.hub.rig.config = lambda: FAST
        yield both


def _paused_question(homes: TwoHomes, machine: str) -> None:
    checkout = str(homes.machines[machine].directory)
    with homes.seeded(machine) as store, store.write() as transaction:
        insert_question(
            transaction,
            NewQuestion(
                key=KEY,
                member_id=CORE,
                question=QUESTION,
                checkout=checkout,
                slice_label=None,
                source_commit=None,
                passages=None,
                answering_run_id=None,
                waiting_reason=DeclineReason.ANSWER_LIMIT_REACHED,
                waiting_detail="needs the PM",
            ),
            now=homes.clock(),
        )


def _answer_from_beta(homes: TwoHomes) -> None:
    homes.use(BETA)
    answered = wiring.invoke(
        OperationName.ANSWER, {"run_id": KEY.run_id, "text": "300"}, None, Door.CLI
    )
    assert isinstance(answered, AnswerResult)
    assert answered.outcome is AnswerOutcome.RECORDED


def _presence(homes: TwoHomes, machine: Machine, cf: object) -> PresenceDeps:
    layout = homes.layout(machine.name)
    return PresenceDeps(
        open_steps=lambda last, identity: steps_for(
            layout, last, lambda: FAST, TICK_TIMES, identity
        ),
        cf_run=cf,  # pyright: ignore[reportArgumentType]
        clock=homes.clock,
        after_deps=lambda: machine.deps,
    )


async def _sessions(
    deps: PresenceDeps,
    states: list[PresenceState],
    outbound: RecordingOutbound,
    scenario: Callable[[], Awaitable[None]],
) -> None:
    """Each state ticking with its own after-runner, whose work runs in the group."""
    async with anyio.create_task_group() as group:
        for state in states:
            runner = AfterRunner(deps, group.start_soon)
            group.start_soon(
                run_ticks, make_connection(outbound), state, deps, CLIENT, runner
            )
        await scenario()
        group.cancel_scope.cancel()


def _resumes(machine: Machine) -> list[tuple[str, ...]]:
    return [argv for argv in machine.spawned if RESUME_RUN_COMMAND in argv]


@pytest.mark.parametrize("sessions", [1, 3], ids=["one-session", "three-sessions"])
def test_a_pause_on_alpha_answered_from_beta_resumes_on_alpha_from_open_sessions(
    homes: TwoHomes, sessions: int
) -> None:
    _paused_question(homes, ALPHA)
    _answer_from_beta(homes)
    alpha = homes.use(ALPHA)
    states = [
        member_state_at(homes, alpha.directory, index) for index in range(sessions)
    ]
    deps = _presence(homes, alpha, alpha.deps.cf_run)

    async def scenario() -> None:
        await eventually(lambda: bool(_resumes(alpha)), "the resume to start")
        await anyio.sleep(1.0)
        # Every session ticked more than once: the claim was still one.
        assert all(state.as_of_seq is not None for state in states)

    anyio.run(_sessions, deps, states, RecordingOutbound(), scenario)

    assert len(_resumes(alpha)) == 1


def member_state_at(homes: TwoHomes, directory: Path, index: int = 0) -> PresenceState:
    state = PresenceState(started_at=homes.clock())
    state.directory = str(directory)
    state.session_id = f"{index:032x}"
    return state


def test_a_session_in_no_member_directory_writes_no_row_and_still_starts_the_work(
    homes: TwoHomes,
) -> None:
    _paused_question(homes, ALPHA)
    _answer_from_beta(homes)
    alpha = homes.use(ALPHA)
    elsewhere = alpha.home / "elsewhere"
    elsewhere.mkdir()
    state = member_state_at(homes, elsewhere)
    outbound = RecordingOutbound()
    deps = _presence(homes, alpha, FakeCf({elsewhere: CfAnswer.NOT_A_PROJECT}))

    async def scenario() -> None:
        await eventually(lambda: bool(_resumes(alpha)), "the resume to start")
        assert state.member_id is None

    anyio.run(_sessions, deps, [state], outbound, scenario)

    assert homes.hub.rig.rows("SELECT COUNT(*) FROM sessions") == [(0,)]
    assert outbound.sent == []


def test_an_mcp_answer_for_a_run_on_the_sessions_own_machine_returns_the_resume(
    homes: TwoHomes,
) -> None:
    _paused_question(homes, ALPHA)
    alpha = homes.use(ALPHA)
    alpha.polls[KEY.run_id] = [PAUSE, PAUSE, RUNNING_DOC]

    async def answer() -> dict[str, Any]:
        return await run_in_process(
            ANSWER_TOOL,
            {"run_id": KEY.run_id, "text": "300"},
            None,
        )

    result = anyio.run(answer)

    assert result["outcome"] == "recorded"
    assert result["resume"]["outcome"] == "resumed"
    assert _resumes(alpha) == []


def test_an_answer_the_client_cut_off_is_still_recorded_with_its_resume_outcome(
    homes: TwoHomes,
) -> None:
    _paused_question(homes, ALPHA)
    alpha = homes.use(ALPHA)
    alpha.polls[KEY.run_id] = [PAUSE, PAUSE, RUNNING_DOC]
    fast_poll = alpha.deps.poll_run

    def slow_poll(run_id: str) -> Any:
        time.sleep(SLOW_POLL_SECONDS)
        return fast_poll(run_id)

    alpha.rig = replace(alpha.rig, deps=replace(alpha.deps, poll_run=slow_poll))

    async def cut_off() -> None:
        with anyio.move_on_after(CLIENT_GIVES_UP_SECONDS) as scope:
            await run_in_process(
                ANSWER_TOOL, {"run_id": KEY.run_id, "text": "300"}, None
            )
        assert scope.cancelled_caught, "the answer finished inside the cut-off"
        await eventually(
            lambda: (
                homes.hub.rig.rows("SELECT resume_outcome FROM answers")
                == [("resumed",)]
            ),
            "the abandoned worker to record the resume outcome",
        )

    anyio.run(cut_off)

    decided = wiring.invoke(OperationName.DECISIONS, {}, None, Door.CLI)
    assert isinstance(decided, DecisionsResult)
    (record,) = decided.records
    assert record.answer == "300"
    assert record.resume is not None
