"""D9: reissue a launch recovery found never started (issue #9)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.process import PollFailure, RunOutcome
from amoeba.runner.dispatch.reissue import REASON_STARTED_BEFORE_CRASH
from amoeba.runner.ingest.outcome import PAYLOAD_REASON, PAYLOAD_RUN_ID
from amoeba.runner.launch import (
    PARAM_PARAMS,
    PARAM_PIPELINE,
    PARAM_REISSUE_OF,
    log_paths,
)
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_RUN_ID,
    Channel,
    CommandKind,
    JournalEntry,
    JournalOutcome,
    JournalResolver,
    Node,
    NodeStatus,
    Store,
)
from runner.dispatch.tick_rig import DispatchRig
from runner.observe_support import document

PROJECT = "demo"
OLD_RUN_ID = "amoeba-20261024T000000Z-aaaaaaaaaaaa"


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[DispatchRig]:
    yield DispatchRig(tmp_path, store)


def _never_started(
    rig: DispatchRig, extra: dict[str, object] | None = None
) -> tuple[Node, JournalEntry]:
    """A step whose launch recovery resolved ``not_applied``."""
    node = rig.step("reissue", 125)
    old = rig.store.journal_issue(
        node.id,
        kind=CommandKind.SQ_RUN,
        parameters={
            PARAM_PIPELINE: "P4",
            PARAM_PARAMS: {"slice": "125"},
            PARAM_RUN_ID: OLD_RUN_ID,
            PARAM_CHECKOUT: str(rig.world.root),
            **(extra or {}),
        },
    )
    rig.store.journal_resolve(
        old.id,
        outcome=JournalOutcome.NOT_APPLIED,
        result={"reason": "no run state after the grace period"},
        resolved_by=JournalResolver.RECOVERY,
    )
    return node, old


def _nothing_running(rig: DispatchRig) -> None:
    """Squadron has no state for the run id when the reissue polls it."""
    rig.tick_rig.poll.answers.append(document(OLD_RUN_ID, RunOutcome.NOT_FOUND))


def _escalation(rig: DispatchRig) -> dict[str, object]:
    [message] = rig.store.messages(PROJECT, channel=Channel.ESCALATION)
    return dict(message.payload or {})


def test_reissue_with_run_id_line_escalates(
    rig: DispatchRig,
) -> None:
    node, old = _never_started(rig)
    log_paths(rig.tick_rig.supervisor_dir, old.id).stderr.write_text(
        f"run_id={OLD_RUN_ID}\n"
    )

    rig.tick()

    assert rig.popen.argvs == []
    assert len(rig.entries(CommandKind.SQ_RUN, node)) == 1, "no second attempt"
    assert rig.status(node) is NodeStatus.BLOCKED_ON_HUMAN
    payload = _escalation(rig)
    assert payload[PAYLOAD_REASON] == REASON_STARTED_BEFORE_CRASH
    assert payload[PAYLOAD_RUN_ID] == OLD_RUN_ID


def test_an_unreadable_log_blocks_and_launches_nothing(rig: DispatchRig) -> None:
    node, old = _never_started(rig)
    log_paths(rig.tick_rig.supervisor_dir, old.id).stderr.mkdir()  # not a file

    rig.tick()

    assert rig.popen.argvs == []
    assert rig.status(node) is NodeStatus.BLOCKED_ON_HUMAN
    assert "unreadable" in str(_escalation(rig)[PAYLOAD_REASON])


@pytest.mark.parametrize("log", [None, ""], ids=["no log", "a log without the line"])
def test_no_run_id_line_relaunches_once_under_the_same_run_id(
    rig: DispatchRig, log: str | None
) -> None:
    node, old = _never_started(rig)
    if log is not None:
        log_paths(rig.tick_rig.supervisor_dir, old.id).stderr.write_text(log)
    _nothing_running(rig)

    rig.tick()

    [new] = [e for e in rig.entries(CommandKind.SQ_RUN, node) if not e.is_resolved]
    assert new.parameters[PARAM_RUN_ID] == OLD_RUN_ID
    assert new.parameters[PARAM_REISSUE_OF] == old.id
    assert new.parameters[PARAM_PIPELINE] == "P4"
    assert new.parameters[PARAM_PARAMS] == {"slice": "125"}
    assert new.parameters[PARAM_CHECKOUT] == str(rig.world.root)
    [argv] = rig.popen.argvs
    assert argv.count(OLD_RUN_ID) == 1, "one `sq run` for that id"
    assert rig.popen.cwds == [str(rig.world.root)]


def test_a_run_state_that_appeared_meanwhile_is_adopted_without_a_launch(
    rig: DispatchRig,
) -> None:
    node, old = _never_started(rig)
    rig.tick_rig.poll.answers.append(document(OLD_RUN_ID, RunOutcome.TIMED_OUT))

    rig.tick()

    assert rig.popen.argvs == []
    [new] = [e for e in rig.entries(CommandKind.SQ_RUN, node) if not e.is_resolved]
    assert new.parameters[PARAM_RUN_ID] == OLD_RUN_ID
    assert new.parameters[PARAM_REISSUE_OF] == old.id
    assert rig.tick_rig.poll.asked == [OLD_RUN_ID], "polled once"


def test_a_poll_that_failed_still_launches_because_squadron_refuses_a_taken_id(
    rig: DispatchRig,
) -> None:
    node, _ = _never_started(rig)
    rig.tick_rig.poll.answers.append(PollFailure("sq did not answer"))

    rig.tick()

    assert len(rig.popen.argvs) == 1
    assert rig.status(node) is NodeStatus.RUNNABLE
