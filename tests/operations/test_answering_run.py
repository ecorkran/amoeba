"""Scratch, argv, start and wait of one answering run (slice 223, tasks 5.5, 5.7)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from fake_sq import COMPLETED, PAUSED_AGENT_QUESTION, poll_not_found, poll_result
from process_containment import contained_popen

from amoeba.answering.decide import Declined
from amoeba.answering.inputs import NO_ITEM_BARRED_TEXT, QuestionInput
from amoeba.answering.pipeline_file import answering_pipeline_path
from amoeba.answering.settings import AnswererSettings
from amoeba.answering.values import DeclineReason
from amoeba.operations.answering_run import (
    NO_PAUSE_HOOK_FLAG,
    ScratchFailure,
    answering_argv,
    answering_logs,
    make_scratch,
    scratch_path,
    start,
    wait,
)
from amoeba.operations.processes import start_child, terminate_group
from amoeba.upstream.squadron.faults import LaunchFailure
from amoeba.upstream.squadron.launch import LaunchError, mint_run_id
from amoeba.upstream.squadron.run_outcome import (
    LaunchFailed,
    PollFailure,
    RunEnded,
    RunVanished,
)
from operations.pause_support import START, FakeChild, build_deps

RUN_ID = "amoeba-20261110T120000Z-aaaaaaaaaaaa"
QUESTION = QuestionInput("none", "What is the file length limit?")
SETTINGS = AnswererSettings(
    answer_limit=3,
    reserved_terms=(),
    rules_paths=("CLAUDE.md",),
    passages_max_chars=1000,
    answer_model="answer-alias",
    check_model="check-alias",
    max_cost_usd=0.5,
)


@dataclass(frozen=True)
class _Item:
    key: str
    description: str


# 5.5: run id and scratch


def test_a_minted_id_has_the_designed_format_and_two_differ() -> None:
    first, second = mint_run_id(START), mint_run_id(START)

    assert re.fullmatch(r"amoeba-20261110T120000Z-[0-9a-f]{12}", first)
    assert first != second


def test_the_scratch_holds_the_passages_and_the_members_not_authorized_items(
    tmp_path: Path,
) -> None:
    items = [_Item("push", "pushing to a remote")]

    scratch = make_scratch(tmp_path, RUN_ID, QUESTION, "## P1\n\ntext\n", 0.5, items)

    assert scratch == scratch_path(tmp_path, RUN_ID) == tmp_path / RUN_ID
    assert isinstance(scratch, Path)
    assert (scratch / "passages.md").read_text(encoding="utf-8") == "## P1\n\ntext\n"
    listing = (scratch / "not_authorized.md").read_text(encoding="utf-8")
    assert listing == "- push: pushing to a remote"
    assert NO_ITEM_BARRED_TEXT not in listing


def test_an_empty_member_list_is_stated_explicitly(tmp_path: Path) -> None:
    scratch = make_scratch(tmp_path, RUN_ID, QUESTION, "## P1\n", 0.5, [])

    assert isinstance(scratch, Path)
    assert (scratch / "not_authorized.md").read_text(encoding="utf-8") == (
        NO_ITEM_BARRED_TEXT
    )


def test_an_existing_scratch_directory_is_a_failure_value_and_untouched(
    tmp_path: Path,
) -> None:
    (tmp_path / RUN_ID).mkdir()

    result = make_scratch(tmp_path, RUN_ID, QUESTION, "## P1\n", 0.5, [])

    assert isinstance(result, ScratchFailure)
    assert "FileExistsError" in result.detail
    assert list((tmp_path / RUN_ID).iterdir()) == []


# 5.7: argv, start and wait


def test_the_argv_is_the_designed_command_with_the_opt_out_once() -> None:
    argv = answering_argv(RUN_ID, SETTINGS)

    assert argv == [
        "sq",
        "run",
        str(answering_pipeline_path()),
        "answer-alias",
        "--run-id",
        RUN_ID,
        "-p",
        "check-model=check-alias",
        "--no-pause-hook",
    ]
    assert argv.count(NO_PAUSE_HOOK_FLAG) == 1
    assert NO_PAUSE_HOOK_FLAG == "--no-pause-hook"


def test_the_flag_is_one_constant_in_one_module() -> None:
    source_root = Path(__file__).parents[2] / "src"
    spelled = [
        path.name
        for path in source_root.rglob("*.py")
        if "--no-pause-hook" in path.read_text(encoding="utf-8")
    ]

    assert spelled == ["answering_run.py"]


def test_start_spawns_in_the_scratch_with_logs_named_from_the_run_id(
    tmp_path: Path,
) -> None:
    child = FakeChild(exit_code=0)
    rig = build_deps(tmp_path, polls={}, spawns=[child])
    scratch = tmp_path / "scratch"

    started = start(rig.deps, RUN_ID, scratch, SETTINGS)

    assert started is child
    (call,) = rig.spawner.calls
    assert call.cwd == scratch
    assert call.argv == tuple(answering_argv(RUN_ID, SETTINGS))
    assert call.logs == answering_logs(tmp_path / "logs", RUN_ID)
    assert call.logs.stdout == tmp_path / "logs" / "answering" / f"{RUN_ID}.stdout.log"
    assert call.logs.stderr == tmp_path / "logs" / "answering" / f"{RUN_ID}.stderr.log"


def test_a_spawn_error_is_answering_launch_failed(tmp_path: Path) -> None:
    error = LaunchError(LaunchFailure.SPAWN_ERROR, "OSError: no sq")
    rig = build_deps(tmp_path, polls={}, spawns=[error])

    result = start(rig.deps, RUN_ID, tmp_path, SETTINGS)

    assert isinstance(result, Declined)
    assert result.reason is DeclineReason.ANSWERING_LAUNCH_FAILED
    assert "no sq" in result.detail


def test_a_model_alias_squadron_would_split_is_answering_launch_failed(
    tmp_path: Path,
) -> None:
    broken = SETTINGS.model_copy(update={"check_model": "a,b"})
    rig = build_deps(tmp_path, polls={}, spawns=[FakeChild(0)])

    result = start(rig.deps, RUN_ID, tmp_path, broken)

    assert isinstance(result, Declined)
    assert result.reason is DeclineReason.ANSWERING_LAUNCH_FAILED
    assert rig.spawner.calls == []


def test_a_finished_run_is_read_once_after_the_child_exits(tmp_path: Path) -> None:
    document = poll_result(COMPLETED, RUN_ID)
    rig = build_deps(tmp_path, polls={RUN_ID: [document]}, spawns=[])

    result = wait(rig.deps, FakeChild(exit_code=0), RUN_ID, 30)

    assert result == RunEnded(document)
    assert rig.poller.calls == [RUN_ID]


def test_a_stalled_child_is_stopped_and_is_answering_run_stalled(
    tmp_path: Path,
) -> None:
    rig = build_deps(tmp_path, polls={}, spawns=[])
    spawner = partial(start_child, popen=contained_popen)
    sleeper = ["python3", "-c", "import time; time.sleep(60)"]
    child = spawner(sleeper, tmp_path, answering_logs(tmp_path / "logs", RUN_ID))
    assert not isinstance(child, LaunchError)
    try:
        result = wait(rig.deps, child, RUN_ID, 0.2)
        assert isinstance(result, Declined)
        assert result.reason is DeclineReason.ANSWERING_RUN_STALLED
        assert result.detail == "no result after 0.2 seconds"
        assert child.poll() is not None
        assert rig.poller.calls == []
    finally:
        terminate_group(child)


def test_a_poll_failure_is_answering_run_failed(tmp_path: Path) -> None:
    rig = build_deps(
        tmp_path, polls={RUN_ID: [PollFailure("sq runs wait timed out")]}, spawns=[]
    )

    result = wait(rig.deps, FakeChild(exit_code=0), RUN_ID, 30)

    assert isinstance(result, Declined)
    assert result.reason is DeclineReason.ANSWERING_RUN_FAILED
    assert "timed out" in result.detail


def test_a_child_that_exited_non_zero_with_no_run_is_a_launch_failure_with_its_stderr(
    tmp_path: Path,
) -> None:
    rig = build_deps(tmp_path, polls={RUN_ID: [poll_not_found(RUN_ID)]}, spawns=[])
    log = answering_logs(tmp_path / "logs", RUN_ID).stderr
    log.parent.mkdir(parents=True)
    log.write_text("Error: model alias unknown\n", encoding="utf-8")

    result = wait(rig.deps, FakeChild(exit_code=2), RUN_ID, 30)

    assert isinstance(result, LaunchFailed)
    assert result.failure is LaunchFailure.USAGE_ERROR
    assert "model alias unknown" in result.tail


def test_a_child_that_exited_cleanly_with_no_run_is_a_vanished_run(
    tmp_path: Path,
) -> None:
    rig = build_deps(tmp_path, polls={RUN_ID: [poll_not_found(RUN_ID)]}, spawns=[])

    assert wait(rig.deps, FakeChild(exit_code=0), RUN_ID, 30) == RunVanished()


def test_a_paused_document_is_still_a_run_that_ended(tmp_path: Path) -> None:
    document = poll_result(PAUSED_AGENT_QUESTION, RUN_ID)
    rig = build_deps(tmp_path, polls={RUN_ID: [document]}, spawns=[])

    assert wait(rig.deps, FakeChild(exit_code=0), RUN_ID, 30) == RunEnded(document)
