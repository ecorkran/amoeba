"""``list_runs`` against the real ``sq runs list --json`` recording (slice 224, 3.2).

The ``sq`` is a fake on ``PATH`` that replays the recording (and its real stderr
warning), so the real subprocess path runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fake_sq import (
    LIST_MIXED,
    RUNS_LIST_FIXTURES,
    FakeListing,
    recorded_listing,
    recorded_warning,
    write_fake_sq,
)

from amoeba.upstream.squadron.run_list import (
    ListedRun,
    RunListProblem,
    list_runs,
)
from amoeba.upstream.squadron.run_outcome import RunCheckpoint

TIMEOUT_SECONDS = 10.0


def _with_sq(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, listing: FakeListing | None
) -> Path:
    fake = write_fake_sq(
        tmp_path / "bin",
        waits={},
        run_exit_code=0,
        run_stderr="",
        runs_list=listing,
    )
    monkeypatch.setenv("PATH", f"{fake.directory}:/usr/bin:/bin")
    return fake.directory


def _listed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, listing: FakeListing
) -> list[ListedRun]:
    _with_sq(monkeypatch, tmp_path, listing)
    result = list_runs(timeout_seconds=TIMEOUT_SECONDS)
    assert isinstance(result, list), result
    return result


def _raw_entries() -> list[dict[str, object]]:
    text = (RUNS_LIST_FIXTURES / LIST_MIXED).read_text(encoding="utf-8")
    entries: list[dict[str, object]] = json.loads(text)
    return entries


def test_the_real_recording_parses_with_its_stderr_warning_and_no_all_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = _with_sq(
        monkeypatch, tmp_path, recorded_listing(stderr=recorded_warning())
    )

    runs = list_runs(timeout_seconds=TIMEOUT_SECONDS)

    assert isinstance(runs, list)
    assert [run.run_id for run in runs] == [
        str(entry["run_id"]) for entry in _raw_entries()
    ]
    calls = (directory / "sq_list_argv.jsonl").read_text(encoding="utf-8")
    assert json.loads(calls.splitlines()[0]) == ["runs", "list", "--json"]


def test_a_run_has_its_id_pipeline_status_directory_and_checkpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runs = {r.run_id: r for r in _listed(monkeypatch, tmp_path, recorded_listing())}

    paused = runs["demo-pause-1"]

    assert paused.pipeline == "asks_question"
    assert paused.status == "paused"
    assert paused.is_paused
    assert paused.working_directory is not None
    assert paused.working_directory.name == "amoeba"
    assert paused.checkpoint is not None
    assert paused.checkpoint.kind == "agent_question"
    assert (paused.checkpoint.question or "").startswith("What is the maximum")
    assert not runs["run-20261111-p6-fe470d63"].is_paused


def test_a_run_with_a_null_directory_has_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runs = {r.run_id: r for r in _listed(monkeypatch, tmp_path, recorded_listing())}

    old = runs["run-20261105-p6-7dc230a3"]

    assert old.working_directory is None
    assert old.checkpoint is not None
    assert old.checkpoint.kind == "awaits_human"
    assert old.checkpoint.question is None


def test_a_run_with_no_checkpoint_has_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runs = {r.run_id: r for r in _listed(monkeypatch, tmp_path, recorded_listing())}

    assert runs["run-20261111-p6-fe470d63"].checkpoint is None


def test_extra_checkpoint_fields_are_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runs = {r.run_id: r for r in _listed(monkeypatch, tmp_path, recorded_listing())}

    interactive = runs["run-20261004-p6-8bc5e634"]

    assert interactive.checkpoint is not None
    assert interactive.checkpoint.kind == "interactive_checkpoint"
    assert set(vars(interactive.checkpoint)) == {"kind", "paused_at", "question"}


def test_paused_at_is_what_the_checkpoint_parser_gives_for_the_same_checkpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runs = _listed(monkeypatch, tmp_path, recorded_listing())

    checked = 0
    for entry, run in zip(_raw_entries(), runs, strict=True):
        raw_checkpoint = entry["checkpoint"]
        if raw_checkpoint is None:
            continue
        expected = RunCheckpoint.model_validate(raw_checkpoint).paused_at_text
        assert run.checkpoint is not None
        assert run.checkpoint.paused_at == expected
        checked += 1
    assert checked >= 5


def test_an_unknown_status_stays_a_raw_string(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entry = {**_raw_entries()[0], "status": "hibernating"}
    listing = FakeListing(stdout=json.dumps([entry]), stderr="", exit_code=0)

    (run,) = _listed(monkeypatch, tmp_path, listing)

    assert run.status == "hibernating"
    assert not run.is_paused


def test_an_empty_listing_is_an_empty_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert _listed(monkeypatch, tmp_path, FakeListing("[]", "", 0)) == []


def _problem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, listing: FakeListing | None
) -> RunListProblem:
    _with_sq(monkeypatch, tmp_path, listing)
    result = list_runs(timeout_seconds=TIMEOUT_SECONDS)
    assert isinstance(result, RunListProblem), result
    return result


def test_a_nonzero_exit_is_a_problem_quoting_the_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    problem = _problem(
        monkeypatch, tmp_path, FakeListing("boom: no store", "", exit_code=1)
    )

    assert "exited 1" in problem.reason
    assert "boom: no store" in problem.reason


def test_an_sq_without_runs_list_is_a_problem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    problem = _problem(monkeypatch, tmp_path, None)

    assert "runs list --json" in problem.reason
    assert "exited 2" in problem.reason


def test_output_that_is_not_json_is_a_problem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    problem = _problem(monkeypatch, tmp_path, FakeListing("Run  Pipeline", "", 0))

    assert "did not print JSON" in problem.reason
    assert "Run  Pipeline" in problem.reason


@pytest.mark.parametrize(
    "missing", ["run_id", "pipeline", "status", "working_directory", "checkpoint"]
)
def test_a_missing_field_is_a_problem_naming_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, missing: str
) -> None:
    entry = {k: v for k, v in _raw_entries()[0].items() if k != missing}
    listing = FakeListing(json.dumps([entry]), "", 0)

    problem = _problem(monkeypatch, tmp_path, listing)

    assert missing in problem.reason


def test_a_document_that_is_not_a_list_is_a_problem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    problem = _problem(monkeypatch, tmp_path, FakeListing('{"runs": []}', "", 0))

    assert "unexpected document" in problem.reason


def test_a_sq_that_does_not_finish_in_time_is_a_problem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = tmp_path / "slow"
    directory.mkdir()
    script = directory / "sq"
    script.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}:/usr/bin:/bin")

    result = list_runs(timeout_seconds=0.3)

    assert isinstance(result, RunListProblem)
    assert "did not finish" in result.reason


def test_a_missing_sq_is_a_problem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    result = list_runs(timeout_seconds=TIMEOUT_SECONDS)

    assert isinstance(result, RunListProblem)
    assert "not found on PATH" in result.reason
