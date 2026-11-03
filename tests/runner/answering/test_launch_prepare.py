"""The pre-journal steps of an answering launch (slice 144, D6, D8)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from answerer_settings import ANSWER_MODEL, CHECK_MODEL, MAX_COST_USD, answerer_settings

from amoeba.runner.answering import launch as launch_module
from amoeba.runner.answering.launch import (
    ANSWERING_DIRNAME,
    LaunchStatus,
    Prepared,
    launch_answering,
    prepare_launch,
)
from amoeba.runner.answering.passages import SourcesProblem, SourcesProblemKind
from amoeba.runner.answering.pipeline_file import (
    CHECK_MODEL_PARAM,
    PIPELINE_FILE_NAME,
    SQUADRON_CONFIG_FILE,
)
from amoeba.store import CommandKind, DeclineReason, QuestionState, Store
from runner.answering.launch_rig import RecordingPopen, budget, build_launch_rig
from runner.answering.sources_repo import CountingBudget


def _prepared(result: Prepared | LaunchStatus) -> Prepared:
    assert isinstance(result, Prepared), result
    return result


def test_the_scratch_directory_holds_the_prepared_inputs(
    store: Store, tmp_path: Path
) -> None:
    rig = build_launch_rig(tmp_path, store)

    prepared = _prepared(prepare_launch(rig.context, rig.record, budget()))

    assert prepared.scratch.parent == rig.supervisor_dir / ANSWERING_DIRNAME
    assert prepared.scratch.name == prepared.launch.run_id
    assert (prepared.scratch / "question.md").is_file()
    assert (prepared.scratch / "passages.md").is_file()
    config = tomllib.loads((prepared.scratch / SQUADRON_CONFIG_FILE).read_text())
    assert MAX_COST_USD in _numbers(config)


def _numbers(value: object) -> list[float]:
    if isinstance(value, dict):
        return [n for item in value.values() for n in _numbers(item)]  # pyright: ignore
    return [float(value)] if isinstance(value, int | float) else []


def test_the_command_line_names_the_pipeline_run_id_and_both_models(
    store: Store, tmp_path: Path
) -> None:
    rig = build_launch_rig(tmp_path, store)

    prepared = _prepared(prepare_launch(rig.context, rig.record, budget()))

    # The answer model is the positional target: Squadron takes a pipeline's first
    # required param only that way, never from -p (squadron 0.24.16).
    assert list(prepared.argv)[1:] == [
        "run",
        str(prepared.launch.parameters["pipeline"]),
        ANSWER_MODEL,
        "--run-id",
        prepared.launch.run_id,
        "-p",
        f"{CHECK_MODEL_PARAM}={CHECK_MODEL}",
    ]
    assert Path(prepared.argv[2]).name == PIPELINE_FILE_NAME


def test_the_launch_records_the_passages_without_their_text(
    store: Store, tmp_path: Path
) -> None:
    rig = build_launch_rig(tmp_path, store)

    prepared = _prepared(prepare_launch(rig.context, rig.record, budget()))

    assert prepared.launch.source_commit
    assert prepared.launch.passages
    assert all(ref.source for ref in prepared.launch.passages)


@pytest.mark.parametrize("kind", list(SourcesProblemKind))
def test_each_sources_problem_declines_with_its_reason_and_makes_nothing(
    store: Store,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: SourcesProblemKind,
) -> None:
    rig = build_launch_rig(tmp_path, store)

    def problem(*_args: object, **_kwargs: object) -> SourcesProblem:
        return SourcesProblem(kind, "the detail")

    monkeypatch.setattr(launch_module, "assemble_sources", problem)

    status = launch_answering(rig.context, rig.record, budget())

    declined = store.question(rig.record.id)
    assert status is LaunchStatus.DECLINED
    assert declined is not None
    assert declined.decline_reason is DeclineReason(kind.value)
    assert declined.decline_detail == "the detail"
    assert not (rig.supervisor_dir / ANSWERING_DIRNAME).exists()
    assert not [
        e
        for e in store.journal_entries(rig.record.project_id)
        if e.kind is CommandKind.SQ_ANSWER
    ]
    assert rig.popen.calls == []


@pytest.mark.parametrize("allowed", [0, 1, 2])
def test_a_budget_refusal_keeps_the_question_pending_and_makes_nothing(
    store: Store, tmp_path: Path, allowed: int
) -> None:
    rig = build_launch_rig(tmp_path, store)

    status = launch_answering(rig.context, rig.record, CountingBudget(allowed))

    pending = store.question(rig.record.id)
    assert status is LaunchStatus.STOPPED
    assert pending is not None and pending.state is QuestionState.PENDING
    assert not (rig.supervisor_dir / ANSWERING_DIRNAME).exists()
    assert rig.popen.calls == []


def test_a_directory_that_cannot_be_made_declines_launch_failed_and_is_not_pending(
    store: Store, tmp_path: Path
) -> None:
    rig = build_launch_rig(tmp_path, store)
    # A file where the answering directory belongs: mkdir raises OSError.
    (rig.supervisor_dir / ANSWERING_DIRNAME).write_text("in the way")

    status = launch_answering(rig.context, rig.record, budget())

    declined = store.question(rig.record.id)
    assert status is LaunchStatus.DECLINED
    assert declined is not None
    assert declined.decline_reason is DeclineReason.ANSWERING_LAUNCH_FAILED
    assert declined.decline_detail
    # It is no longer pending, so no later tick offers it for launch again.
    assert store.pending_questions(rig.record.project_id) == []
    assert rig.popen.calls == []


def test_a_scratch_write_that_fails_declines_launch_failed(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = build_launch_rig(tmp_path, store)

    def broken(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(launch_module, "prepare_scratch", broken)

    status = launch_answering(rig.context, rig.record, budget())

    declined = store.question(rig.record.id)
    assert status is LaunchStatus.DECLINED
    assert declined is not None
    assert declined.decline_reason is DeclineReason.ANSWERING_LAUNCH_FAILED
    assert "disk full" in (declined.decline_detail or "")
    assert rig.popen.calls == []


def test_a_misused_scratch_is_a_programming_error_and_raises(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = build_launch_rig(tmp_path, store)

    def misused(*_args: object, **_kwargs: object) -> None:
        raise ValueError("directory is not empty")

    monkeypatch.setattr(launch_module, "prepare_scratch", misused)

    with pytest.raises(ValueError, match="not empty"):
        prepare_launch(rig.context, rig.record, budget())


def test_settings_other_than_the_default_reach_the_command(
    store: Store, tmp_path: Path
) -> None:
    settings = answerer_settings(
        rules_paths=("CLAUDE.md",),
        passages_max_chars=1_000_000,
        answer_model="glm-flash",
        check_model="ds-flash",
    )
    rig = build_launch_rig(tmp_path, store, settings=settings, popen=RecordingPopen())

    prepared = _prepared(prepare_launch(rig.context, rig.record, budget()))

    assert prepared.argv[3] == "glm-flash"
    assert f"{CHECK_MODEL_PARAM}=ds-flash" in prepared.argv
