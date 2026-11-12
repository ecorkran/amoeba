"""The D3 checks, one test per skip reason (slice 223, task 7.3).

``cf`` is replayed from recordings, ``sq runs wait`` comes from the fake ``sq`` or an
injected poller built from the real recordings, and the store is real.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import replace
from functools import partial
from pathlib import Path

import pytest
from cf_fixtures import (
    DEFAULT_WORKTREE,
    OUTSIDE_ANY_PROJECT,
    fake_cf_run,
    fixture_document,
)
from fake_sq import (
    COMPLETED,
    PAUSED_AGENT_QUESTION,
    PAUSED_INTERACTIVE,
    RUN_FILE,
    RUNNING,
    SQUADRON_FIXTURES,
    poll_result,
    write_fake_sq,
)
from store.question_support import NOW

from amoeba.operations.deps import Deps
from amoeba.operations.members import ContextForgeError
from amoeba.operations.pause_eligibility import Eligible, Skip, check_eligibility
from amoeba.operations.pause_models import SkipReason
from amoeba.store.models import QuestionKey
from amoeba.store.questions import NewQuestion, insert_question
from amoeba.store.store import Store
from amoeba.upstream.squadron.errors import SquadronError
from amoeba.upstream.squadron.run_outcome import PollFailure, RunPoll, poll_run
from operations.pause_support import DepsRig, build_deps, register_member

RUN = "demo-run"
DIRECTORY = Path("/work/checkout")
PROJECT_ID: str = fixture_document(DEFAULT_WORKTREE)["id"]
PAUSE = poll_result(PAUSED_AGENT_QUESTION, RUN)
assert PAUSE.checkpoint is not None
PAUSED_AT = PAUSE.checkpoint.paused_at_text or ""


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _rig(
    tmp_path: Path, poll: RunPoll, *, cf: str | None = DEFAULT_WORKTREE
) -> DepsRig:
    rig = build_deps(tmp_path, polls={RUN: [poll]}, spawns=[])
    return replace(rig, deps=replace(rig.deps, cf_run=fake_cf_run(cf)))


def _with_run_file(tmp_path: Path, *, mode: str | None = None) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    document = json.loads((SQUADRON_FIXTURES / RUN_FILE).read_text(encoding="utf-8"))
    document["working_directory"] = str(DIRECTORY)  # where the run was started
    if mode is not None:
        document["execution_mode"] = mode
    (runs / f"{RUN}.json").write_text(json.dumps(document), encoding="utf-8")


def _check(store: Store, rig_or_deps: DepsRig | Deps) -> Eligible | Skip:
    """``check_eligibility`` on the poll ``handle_pause`` would have made."""
    deps = rig_or_deps.deps if isinstance(rig_or_deps, DepsRig) else rig_or_deps
    polled = deps.poll_run(RUN)
    assert not isinstance(polled, PollFailure), polled
    return check_eligibility(store, RUN, DIRECTORY, deps, polled)


def _skip(result: Eligible | Skip) -> Skip:
    assert isinstance(result, Skip), result
    return result


@pytest.mark.parametrize("name", [COMPLETED, RUNNING])
def test_a_run_that_is_not_paused_is_not_paused(
    tmp_path: Path, store: Store, name: str
) -> None:
    result = _skip(_check(store, _rig(tmp_path, poll_result(name, RUN))))

    assert result.reason is SkipReason.NOT_PAUSED
    assert result.detail is not None


def test_another_checkpoint_kind_is_not_an_agent_question_and_names_the_kind(
    tmp_path: Path, store: Store
) -> None:
    result = _skip(_check(store, _rig(tmp_path, poll_result(PAUSED_INTERACTIVE, RUN))))

    assert result.reason is SkipReason.NOT_AGENT_QUESTION
    assert "interactive_checkpoint" in (result.detail or "")


def test_an_unknown_checkpoint_kind_is_named_raw(tmp_path: Path, store: Store) -> None:
    assert PAUSE.checkpoint is not None
    odd = PAUSE.model_copy(
        update={"checkpoint": PAUSE.checkpoint.model_copy(update={"kind": "new_kind"})}
    )

    result = _skip(_check(store, _rig(tmp_path, odd)))

    assert result.reason is SkipReason.NOT_AGENT_QUESTION
    assert "new_kind" in (result.detail or "")


@pytest.mark.parametrize(
    "change", [{"question": None}, {"question": "  "}, {"paused_at": None}]
)
def test_a_pause_with_no_question_or_no_paused_at_has_no_question_text(
    tmp_path: Path, store: Store, change: dict[str, object]
) -> None:
    assert PAUSE.checkpoint is not None
    broken = PAUSE.model_copy(
        update={"checkpoint": PAUSE.checkpoint.model_copy(update=change)}
    )

    result = _skip(_check(store, _rig(tmp_path, broken)))

    assert result.reason is SkipReason.NO_QUESTION_TEXT


def test_an_answering_run_is_skipped_before_context_forge_is_asked(
    tmp_path: Path, store: Store
) -> None:
    member = register_member(store, PROJECT_ID)
    with store.write() as transaction:
        insert_question(
            transaction,
            NewQuestion(
                key=QuestionKey("other-run", "2026-11-10T09:00:00+00:00"),
                member_id=member.project_id,
                question="q",
                checkout="/c",
                slice_label=None,
                source_commit=None,
                passages=None,
                answering_run_id=RUN,
                waiting_reason=None,
                waiting_detail=None,
            ),
            now=NOW,
        )
    calls: list[Sequence[str]] = []

    def tracking_cf(
        argv: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        raise AssertionError("cf must not be asked for an answering run")

    rig = _rig(tmp_path, PAUSE)
    deps = replace(rig.deps, cf_run=tracking_cf)

    result = _skip(_check(store, deps))

    assert result.reason is SkipReason.ANSWERING_RUN
    assert calls == []


def test_a_directory_outside_every_project_is_not_a_project(
    tmp_path: Path, store: Store
) -> None:
    result = _skip(_check(store, _rig(tmp_path, PAUSE, cf=OUTSIDE_ANY_PROJECT)))

    assert result.reason is SkipReason.NOT_A_PROJECT


def test_a_project_in_no_program_is_not_in_program_and_a_missing_run_file_is_no_error(
    tmp_path: Path, store: Store
) -> None:
    result = _skip(_check(store, _rig(tmp_path, PAUSE)))

    assert result.reason is SkipReason.NOT_IN_PROGRAM
    assert not (tmp_path / "runs").exists()


def test_a_prompt_only_run_is_skipped(tmp_path: Path, store: Store) -> None:
    register_member(store, PROJECT_ID)
    _with_run_file(tmp_path, mode="prompt-only")

    result = _skip(_check(store, _rig(tmp_path, PAUSE)))

    assert result.reason is SkipReason.PROMPT_ONLY


def test_a_run_file_problem_in_a_member_raises(tmp_path: Path, store: Store) -> None:
    register_member(store, PROJECT_ID)

    with pytest.raises(SquadronError, match="does not exist"):
        _check(store, _rig(tmp_path, PAUSE))


def test_a_question_recorded_under_another_member_is_other_member(
    tmp_path: Path, store: Store
) -> None:
    register_member(store, PROJECT_ID)
    register_member(store, "someone-else")
    _with_run_file(tmp_path)
    with store.write() as transaction:
        insert_question(
            transaction,
            NewQuestion(
                key=QuestionKey(RUN, PAUSED_AT),
                member_id="someone-else",
                question="q",
                checkout="/c",
                slice_label=None,
                source_commit=None,
                passages=None,
                answering_run_id="a-1",
                waiting_reason=None,
                waiting_detail=None,
            ),
            now=NOW,
        )

    result = _skip(_check(store, _rig(tmp_path, PAUSE)))

    assert result.reason is SkipReason.OTHER_MEMBER
    assert "someone-else" in (result.detail or "")


def test_an_eligible_pause_carries_the_key_question_member_and_facts(
    tmp_path: Path, store: Store
) -> None:
    member = register_member(store, PROJECT_ID)
    _with_run_file(tmp_path)

    result = _check(store, _rig(tmp_path, PAUSE))

    assert isinstance(result, Eligible)
    assert result.key == QuestionKey(RUN, PAUSED_AT)
    assert PAUSE.checkpoint is not None
    assert result.question == PAUSE.checkpoint.question
    assert result.member == member
    assert result.run_facts.params == {"model": "haiku-xhigh"}
    assert result.existing is None


def test_a_failing_cf_raises_the_operational_error(
    tmp_path: Path, store: Store
) -> None:
    with pytest.raises(ContextForgeError):
        _check(store, _rig(tmp_path, PAUSE, cf=None))


def test_the_checks_work_against_the_fake_sq_executable(
    tmp_path: Path, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = write_fake_sq(
        tmp_path / "bin",
        waits={RUN: PAUSED_AGENT_QUESTION},
        run_exit_code=0,
        run_stderr="",
    )
    monkeypatch.setenv("PATH", f"{fake.directory}:/usr/bin:/bin")
    register_member(store, PROJECT_ID)
    _with_run_file(tmp_path)
    rig = _rig(tmp_path, PAUSE)
    deps = replace(rig.deps, poll_run=partial(poll_run, timeout_seconds=20))

    result = _check(store, deps)

    assert isinstance(result, Eligible)
    assert result.key.paused_at == PAUSED_AT
    assert shutil.which("sq") == str(fake.directory / "sq")
