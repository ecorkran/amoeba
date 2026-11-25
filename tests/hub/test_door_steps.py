"""``DoorSteps`` against an in-process hub, and joined machines running the commands
(262 D3, D10, D11)."""

from __future__ import annotations

import shutil
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from operations.handle_rig import RUN, world
from operations.pause_support import FakeChild, build_deps
from operations.ways import DOOR
from store.decision_support import CORE, FIRST, automatic_answer
from store.question_support import ANSWERING_RUN, claimed_question

from amoeba import wiring, wiring_steps
from amoeba.cli.main import EXIT_ERROR, main
from amoeba.client.client_file import ClientFile
from amoeba.client.errors import ClientFileError, HubRefusedError, HubUnreachableError
from amoeba.config.home import StateLayout, config_path, state_layout
from amoeba.config.user_config import ConfigError, UserConfig
from amoeba.operations.deps import Deps
from amoeba.operations.handle_pause import HandlePauseOutcome
from amoeba.operations.here_document import HereNotAProject
from amoeba.operations.list_registry import MembersView
from amoeba.operations.names import Door, OperationName
from amoeba.operations.steps.models import (
    CLAIM_WORK,
    OPEN_RUNS,
    QUESTION_REPLACE_CLAIM,
    RESUME_READ,
    WAKE_FINISH,
    Step,
    StepModel,
)
from amoeba.operations.steps.models_pause import QuestionReplaceClaimRequest
from amoeba.operations.steps.models_resume import ResumeReadRequest
from amoeba.operations.steps.models_runs import OpenRunsRequest
from amoeba.operations.steps.models_session import (
    SESSION_END,
    SESSION_TICK,
    SessionEndRequest,
    SessionTickRequest,
)
from amoeba.operations.steps.models_wake import WakeFinishRequest
from amoeba.operations.steps.models_work import ClaimWorkRequest, ResumeItem
from amoeba.operations.store_steps import LocalSteps
from amoeba.store.errors import LocalStoreClosedError
from amoeba.store.questions import insert_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import WakeOutcome
from amoeba.wire.protocol import STEP_ADVICE, RefusalCode, SessionIdentity
from amoeba.wire.times import TICK_TIMES, DoorTimes
from amoeba.wiring_door import join
from amoeba.wiring_pause import handle_pause_in
from amoeba.wiring_steps import DoorSteps, LastReply, StepReplyError, steps_for
from hub.call_support import ALPHA_TOKEN, NOW
from hub.in_process_hub import InProcessHub
from hub.join_support import client_layout, line_for, make_local_store

LOGS = "/machine/logs"
FAST = DoorTimes(
    connect_seconds=0.2, read_seconds=0.2, retry_seconds=0.6, retry_pause_seconds=0.1
)


@pytest.fixture
def hub(tmp_path: Path) -> Iterator[InProcessHub]:
    with InProcessHub(tmp_path / "hub") as serving:
        join(line_for(serving), set_aside_local=False)
        yield serving


def _seed(hub: InProcessHub, seed: object) -> None:
    with hub.rig.open_store() as store:
        alpha = hub.rig.machine(ALPHA_TOKEN)
        assert alpha is not None
        store.act_as(alpha)
        assert callable(seed)
        seed(store)


def _answered(store: Store) -> None:
    automatic_answer(store, FIRST, CORE, 1)


def test_the_steps_no_command_path_reaches_here_run_through_their_models(
    hub: InProcessHub,
) -> None:
    """``open_runs``, ``claim_work``, ``resume_read`` and ``question_replace_claim``;
    the pause, resume and wake tests run the rest through the door both ways."""
    _seed(hub, _answered)
    steps = DoorSteps(LastReply())

    runs = steps.run(OPEN_RUNS, OpenRunsRequest())
    claimed = steps.run(CLAIM_WORK, ClaimWorkRequest(logs_dir=LOGS))
    (item,) = claimed.items
    assert isinstance(item, ResumeItem)
    read = steps.run(
        RESUME_READ,
        ResumeReadRequest(answer_seq=item.answer_seq, claim_id=item.claim_id),
    )

    assert runs.prune_after_days > 0
    assert read.claim is not None
    assert read.claim.claim_id == item.claim_id


def test_question_replace_claim_runs_through_the_door(hub: InProcessHub) -> None:
    def seed(store: Store) -> None:
        with store.write() as transaction:
            insert_question(
                transaction, claimed_question(FIRST, member_id=CORE), now=NOW
            )

    _seed(hub, seed)

    reply = DoorSteps(LastReply()).run(
        QUESTION_REPLACE_CLAIM,
        QuestionReplaceClaimRequest(
            run_id=FIRST.run_id,
            paused_at=FIRST.paused_at,
            old_answering_run_id=ANSWERING_RUN,
            new_answering_run_id="amoeba-new",
            passages=(),
        ),
    )

    assert reply.applied is True
    assert hub.rig.rows("SELECT answering_run_id FROM questions") == [("amoeba-new",)]


def _replying(result: dict[str, object]) -> object:
    def reply(*_args: object, **_kwargs: object) -> dict[str, object]:
        return dict(result)

    return reply


def test_a_reply_that_does_not_fit_raises_step_reply_error_naming_the_step(
    hub: InProcessHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wiring_steps, "call", _replying({"wrong": 1}))

    with pytest.raises(StepReplyError) as raised:
        DoorSteps(LastReply()).run(CLAIM_WORK, ClaimWorkRequest(logs_dir=LOGS))

    assert "claim_work" in str(raised.value)
    assert "items" in str(raised.value)
    assert "applied" in str(raised.value)


def test_a_reply_that_does_not_fit_exits_3(
    hub: InProcessHub,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(wiring_steps, "call", _replying({"claim": "not a payload"}))

    code = main(["resume-run", "1", "claim-1"])

    assert code == EXIT_ERROR
    assert "StepReplyError" in capsys.readouterr().err


def test_a_step_failing_on_the_hub_with_an_operation_error_is_hub_error(
    hub: InProcessHub,
) -> None:
    def broken() -> UserConfig:
        raise ConfigError("config.yaml: prune_after_days: not a number")

    hub.rig.config = broken

    with pytest.raises(HubRefusedError) as raised:
        DoorSteps(LastReply()).run(OPEN_RUNS, OpenRunsRequest())

    assert raised.value.code is RefusalCode.HUB_ERROR
    assert HubRefusedError in wiring.OPERATIONAL_ERRORS


def test_a_command_that_started_local_fails_its_next_step_once_the_machine_joins(
    tmp_path: Path,
) -> None:
    layout = state_layout()

    with InProcessHub(tmp_path / "hub") as serving:
        with steps_for(layout, LastReply(), _no_config) as steps:
            assert isinstance(steps, LocalSteps)
            join(line_for(serving), set_aside_local=True)
            finish = WakeFinishRequest(
                wake_id="wake-1", outcome=WakeOutcome.EXITED, exit_code=0, detail=None
            )
            with pytest.raises(LocalStoreClosedError):
                steps.run(WAKE_FINISH, finish)


def _no_config() -> UserConfig:
    raise AssertionError("no step here loads the config")


def test_a_client_file_removed_partway_fails_the_next_step_and_opens_no_local_store(
    tmp_path: Path,
) -> None:
    layout = client_layout()
    make_local_store(layout, "trading")
    with InProcessHub(tmp_path / "hub") as serving:
        join(line_for(serving), set_aside_local=True)
        steps = DoorSteps(LastReply())
        steps.run(OPEN_RUNS, OpenRunsRequest())
        _put_the_set_aside_store_back(layout)
        kept = layout.store_path.read_bytes()
        layout.client_file.unlink()

        with pytest.raises(ClientFileError, match=str(layout.client_file)):
            steps.run(OPEN_RUNS, OpenRunsRequest())

    assert layout.store_path.read_bytes() == kept


def _put_the_set_aside_store_back(layout: StateLayout) -> None:
    (set_aside,) = [
        p
        for p in layout.store_path.parent.iterdir()
        if p.name != "amoeba.sqlite3" and p.name.startswith("amoeba.sqlite3")
    ]
    shutil.move(set_aside, layout.store_path)


def test_with_the_hub_stopped_a_step_stops_in_one_bound_and_the_after_step_calls_none(
    hub: InProcessHub, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hub.stop()
    names: list[str] = []
    real_call = wiring_steps.call

    def counted(*args: object, **kwargs: object) -> dict[str, object]:
        names.append(str(args[2]))
        return real_call(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(wiring_steps, "call", counted)
    last = LastReply()
    steps = DoorSteps(last, FAST)
    deps = build_deps(tmp_path, polls={}, spawns=[]).deps

    started = time.monotonic()
    with pytest.raises(Exception, match="no reply|unreachable|not answering"):
        steps.run(OPEN_RUNS, OpenRunsRequest())
    wiring_steps.after_call(steps, lambda: deps, last, prunes=True)
    elapsed = time.monotonic() - started

    assert last.unreachable is True
    assert names == ["open_runs"]
    assert elapsed < FAST.retry_seconds + FAST.connect_seconds + FAST.read_seconds + 1


def test_a_served_call_whose_reply_has_work_claims_once_and_starts_what_it_gets(
    hub: InProcessHub, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _seed(hub, _answered)
    rig = build_deps(tmp_path / "client", polls={}, spawns=[FakeChild(exit_code=None)])
    deps = replace(rig.deps, amoeba_script=lambda: Path("/installed/bin/amoeba"))

    def client_deps(_layout: StateLayout) -> Deps:
        return deps

    monkeypatch.setattr(wiring, "default_deps", client_deps)
    names: list[str] = []
    real_call = wiring_steps.call

    def counted(*args: object, **kwargs: object) -> dict[str, object]:
        names.append(str(args[2]))
        return real_call(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(wiring_steps, "call", counted)

    listed = wiring.invoke(OperationName.LIST, {"subject": "members"}, None, Door.CLI)

    assert isinstance(listed, MembersView)
    assert names.count("claim_work") == 1
    (spawned,) = rig.spawner.calls
    assert spawned.argv[1] == "resume-run"


def test_handle_pause_on_a_joined_machine_reads_no_local_config(
    tmp_path: Path,
) -> None:
    """The body itself runs both ways in the pause tests; here the command's own
    entry, ``handle_pause_in``, never asks for the config on a joined machine."""
    with world(tmp_path, way=DOOR) as w:
        result = handle_pause_in(
            state_layout(), _no_config, RUN, directory=w.directory, deps=w.deps
        )

    assert result.outcome is HandlePauseOutcome.RESUMED, result
    assert not config_path().exists()


def test_a_writing_step_with_no_reply_says_its_outcome_is_unknown_and_what_follows(
    hub: InProcessHub,
) -> None:
    hub.stop()

    with pytest.raises(HubUnreachableError) as raised:
        DoorSteps(LastReply(), FAST).run(CLAIM_WORK, ClaimWorkRequest(logs_dir=LOGS))

    assert "outcome of this call is unknown" in str(raised.value)
    assert STEP_ADVICE in str(raised.value)


def _recording_call(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, SessionIdentity | None, DoorTimes]]:
    """Replace the door call with one that records the step, the identity and the times
    it got, then reports no reply; the client file is made up."""
    seen: list[tuple[str, SessionIdentity | None, DoorTimes]] = []

    def record(*args: object, **kwargs: object) -> dict[str, object]:
        identity = kwargs["identity"]
        assert identity is None or isinstance(identity, SessionIdentity)
        times = args[4]
        assert isinstance(times, DoorTimes)
        seen.append((str(args[2]), identity, times))
        raise HubUnreachableError("no reply")

    monkeypatch.setattr(wiring_steps, "call", record)

    def made_up(_path: Path, _cert: Path) -> ClientFile:
        return ClientFile(address="hub.example:8443", machine="a", token="t")

    monkeypatch.setattr(wiring_steps, "load_client_file", made_up)
    return seen


def test_the_session_headers_go_on_the_two_session_steps_and_no_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _recording_call(monkeypatch)
    identity = SessionIdentity("cd" * 16, "proj", "claude-code", "/work")
    steps = DoorSteps(LastReply(), TICK_TIMES, identity)

    requests: list[tuple[Step[Any, Any], StepModel]] = [
        (
            SESSION_TICK,
            SessionTickRequest(
                here=HereNotAProject(not_a_project="not a project"),
                session_id=identity.session_id,
                client="claude-code",
                directory="/work",
                last_seen=None,
                push_confirmed=False,
            ),
        ),
        (SESSION_END, SessionEndRequest(session_id=identity.session_id)),
        (OPEN_RUNS, OpenRunsRequest()),
        (CLAIM_WORK, ClaimWorkRequest(logs_dir=LOGS)),
    ]
    for step, request in requests:
        with pytest.raises(HubUnreachableError):
            steps.run(step, request)

    assert [(name, given) for name, given, _ in seen] == [
        ("session_tick", identity),
        ("session_end", identity),
        ("open_runs", None),
        ("claim_work", None),
    ]
    assert {times for _, _, times in seen} == {TICK_TIMES}


def test_the_session_source_gives_a_session_call_one_attempt_after_step_its_retry(
    hub: InProcessHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _recording_call(monkeypatch)
    layout = state_layout()
    identity = SessionIdentity("ef" * 16, None, "claude-code", "/work")
    source = wiring.session_step_source(layout)

    with source(LastReply(), identity) as steps:
        with pytest.raises(HubUnreachableError):
            steps.run(SESSION_END, SessionEndRequest(session_id=identity.session_id))
    with source(LastReply(), None) as steps:
        with pytest.raises(HubUnreachableError):
            steps.run(OPEN_RUNS, OpenRunsRequest())

    assert [times for _, _, times in seen] == [TICK_TIMES, DoorTimes()]
