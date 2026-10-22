"""The ``sq runs wait`` outcome reader (slice 120, D2).

Unit tests patch ``subprocess.run`` for every outcome and failure path. The
integration tests run the stub ``sq`` on ``PATH`` under a temporary ``HOME``, so
the real subprocess path is exercised without Squadron.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sq_stub import STUB_EXIT_CODES, write_outcome_document, write_sq_stub

from amoeba.process.sq_outcome import (
    OUTCOME_EXIT_CODES,
    PollFailure,
    RunOutcome,
    RunOutcomeDocument,
    poll_run,
)

RUN_ID = "run-20261022-p5-aaaa1111"
TIMEOUT_SECONDS = 5.0
PAUSED_AT = "2026-10-21T10:00:00+00:00"


def _state_document(outcome: RunOutcome, **extra: Any) -> dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "outcome": outcome.value,
        "status": outcome.value,
        "pipeline": "p5",
        "started_at": "2026-10-21T09:00:00+00:00",
        "updated_at": "2026-10-21T10:00:00+00:00",
        "checkpoint": None,
        **extra,
    }


def _patch_run(
    monkeypatch: pytest.MonkeyPatch, *, code: int, stdout: str = "", stderr: str = ""
) -> None:
    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, code, stdout, stderr)

    monkeypatch.setattr("amoeba.process.sq_outcome.subprocess.run", fake_run)


def _patch_raise(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        raise error

    monkeypatch.setattr("amoeba.process.sq_outcome.subprocess.run", fake_run)


def _failure(poll: object) -> str:
    assert isinstance(poll, PollFailure)
    return poll.reason


# 1. One test per outcome ---------------------------------------------------


@pytest.mark.parametrize("outcome", list(RunOutcome))
def test_each_outcome_parses_with_its_exit_code(
    monkeypatch: pytest.MonkeyPatch, outcome: RunOutcome
) -> None:
    document = _state_document(outcome)
    _patch_run(
        monkeypatch, code=OUTCOME_EXIT_CODES[outcome], stdout=json.dumps(document)
    )

    poll = poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS)

    assert isinstance(poll, RunOutcomeDocument)
    assert poll.outcome is outcome
    assert poll.run_id == RUN_ID
    assert poll.pipeline == "p5"
    assert poll.updated_at == datetime(2026, 10, 21, 10, 0, tzinfo=UTC)


def test_the_command_is_the_documented_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run(
        command: list[str], **options: Any
    ) -> subprocess.CompletedProcess[str]:
        seen["command"] = command
        seen["options"] = options
        return subprocess.CompletedProcess(
            command, 5, json.dumps({"run_id": RUN_ID, "outcome": "not_found"}), ""
        )

    monkeypatch.setattr("amoeba.process.sq_outcome.subprocess.run", fake_run)

    poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS)

    assert seen["command"] == ["sq", "runs", "wait", RUN_ID, "--timeout", "0", "--json"]
    assert seen["options"] == {
        "stdin": subprocess.DEVNULL,
        "capture_output": True,
        "text": True,
        "timeout": TIMEOUT_SECONDS,
        "check": False,
    }


# 2. Documents with only run_id and outcome ---------------------------------


@pytest.mark.parametrize("outcome", [RunOutcome.NOT_FOUND, RunOutcome.UNREADABLE])
def test_minimal_documents_leave_other_fields_unknown(
    monkeypatch: pytest.MonkeyPatch, outcome: RunOutcome
) -> None:
    document = {"run_id": RUN_ID, "outcome": outcome.value}
    _patch_run(
        monkeypatch, code=OUTCOME_EXIT_CODES[outcome], stdout=json.dumps(document)
    )

    poll = poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS)

    assert isinstance(poll, RunOutcomeDocument)
    assert poll.outcome is outcome
    assert poll.status is None
    assert poll.pipeline is None
    assert poll.started_at is None
    assert poll.updated_at is None
    assert poll.checkpoint is None


# 3. Extra keys, null paused_at ---------------------------------------------


def test_unknown_keys_are_ignored_and_null_paused_at_stays_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _state_document(
        RunOutcome.PAUSED,
        checkpoint={"paused_at": None, "kind": "gate", "added_later": [1, 2]},
        failure=None,
        reviews=[],
        added_later={"x": 1},
    )
    _patch_run(monkeypatch, code=3, stdout=json.dumps(document))

    poll = poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS)

    assert isinstance(poll, RunOutcomeDocument)
    assert poll.checkpoint is not None
    assert poll.checkpoint.paused_at is None


def test_a_paused_at_is_parsed_with_its_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _state_document(RunOutcome.PAUSED, checkpoint={"paused_at": PAUSED_AT})
    _patch_run(monkeypatch, code=3, stdout=json.dumps(document))

    poll = poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS)

    assert isinstance(poll, RunOutcomeDocument)
    assert poll.checkpoint is not None
    assert poll.checkpoint.paused_at == datetime(2026, 10, 21, 10, 0, tzinfo=UTC)


# 4. One test per PollFailure case ------------------------------------------


def test_missing_sq_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_raise(monkeypatch, FileNotFoundError("sq"))

    reason = _failure(poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS))

    assert "not found on PATH" in reason
    assert RUN_ID in reason


def test_timeout_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_raise(monkeypatch, subprocess.TimeoutExpired("sq", TIMEOUT_SECONDS))

    reason = _failure(poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS))

    assert "did not finish within" in reason
    assert RUN_ID in reason


def test_other_oserror_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_raise(monkeypatch, PermissionError("denied"))

    reason = _failure(poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS))

    assert "could not be run" in reason
    assert "denied" in reason
    assert RUN_ID in reason


def test_usage_error_exit_two_carries_the_stderr_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_run(monkeypatch, code=2, stderr="usage: sq runs wait <id>\n")

    reason = _failure(poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS))

    assert "exited 2" in reason
    assert "usage: sq runs wait <id>" in reason
    assert RUN_ID in reason


def test_unmapped_exit_code_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run(monkeypatch, code=99, stderr="boom")

    reason = _failure(poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS))

    assert "exited 99" in reason
    assert "boom" in reason


def test_non_json_output_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run(monkeypatch, code=0, stdout="not json at all")

    reason = _failure(poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS))

    assert "did not print JSON" in reason
    assert RUN_ID in reason


@pytest.mark.parametrize(
    "document",
    [
        {"run_id": RUN_ID},
        {"run_id": RUN_ID, "outcome": "exploded"},
        {"run_id": RUN_ID, "outcome": "completed", "updated_at": "yesterday"},
        ["not", "an", "object"],
    ],
)
def test_invalid_document_is_a_failure(
    monkeypatch: pytest.MonkeyPatch, document: object
) -> None:
    _patch_run(monkeypatch, code=0, stdout=json.dumps(document))

    reason = _failure(poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS))

    assert "invalid document" in reason
    assert RUN_ID in reason


def test_outcome_that_disagrees_with_the_exit_code_is_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_run(
        monkeypatch, code=0, stdout=json.dumps(_state_document(RunOutcome.FAILED))
    )

    reason = _failure(poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS))

    assert "completed" in reason
    assert "failed" in reason


def test_a_document_for_another_run_is_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other = _state_document(RunOutcome.COMPLETED, run_id="run-other")
    _patch_run(monkeypatch, code=0, stdout=json.dumps(other))

    reason = _failure(poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS))

    assert "run-other" in reason
    assert RUN_ID in reason


# 5. The exit-code table ----------------------------------------------------


def test_exit_codes_cover_every_outcome_with_distinct_codes() -> None:
    assert set(OUTCOME_EXIT_CODES) == set(RunOutcome)
    codes = list(OUTCOME_EXIT_CODES.values())
    assert len(set(codes)) == len(codes)
    assert 2 not in codes  # usage errors


def test_the_stub_copy_of_the_table_matches() -> None:
    assert {
        outcome.value: code for outcome, code in OUTCOME_EXIT_CODES.items()
    } == dict(STUB_EXIT_CODES)


# Integration: the stub on PATH ---------------------------------------------


@pytest.fixture
def stub_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = write_sq_stub(tmp_path / "bin")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return home


def test_a_written_paused_document_round_trips(stub_home: Path) -> None:
    write_outcome_document(
        stub_home,
        _state_document(RunOutcome.PAUSED, checkpoint={"paused_at": PAUSED_AT}),
    )

    poll = poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS)

    assert isinstance(poll, RunOutcomeDocument)
    assert poll.outcome is RunOutcome.PAUSED
    assert poll.checkpoint is not None
    assert poll.checkpoint.paused_at == datetime(2026, 10, 21, 10, 0, tzinfo=UTC)


def test_a_missing_id_is_not_found(stub_home: Path) -> None:
    poll = poll_run("run-never-written", timeout_seconds=TIMEOUT_SECONDS)

    assert isinstance(poll, RunOutcomeDocument)
    assert poll.outcome is RunOutcome.NOT_FOUND
    assert poll.run_id == "run-never-written"


@pytest.mark.parametrize("outcome", list(RunOutcome))
def test_the_stub_answers_every_outcome_through_the_real_subprocess(
    stub_home: Path, outcome: RunOutcome
) -> None:
    write_outcome_document(stub_home, _state_document(outcome))

    result = poll_run(RUN_ID, timeout_seconds=TIMEOUT_SECONDS)

    assert isinstance(result, RunOutcomeDocument)
    assert result.outcome is outcome
