"""The ``runs`` document: its size limit, its round trip and its parser (261 D11)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from amoeba.operations.errors import MALFORMED_CALL, CallRefused
from amoeba.operations.runs_document import (
    RUNS_DOCUMENT_MAX_BYTES,
    CallLine,
    CompletedRun,
    LookupKind,
    OpenRun,
    RunCheckpoint,
    RunFileFacts,
    RunLookup,
    RunsDocument,
    build_runs_document,
    listing_problem_document,
    parse_runs,
    runs_to_document,
)

NOW = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)


def _run(run_id: str, status: str = "running", *, question: str = "q") -> OpenRun:
    return OpenRun(
        run_id=run_id,
        pipeline="p",
        status=status,
        working_directory="/work/forge",
        checkpoint=RunCheckpoint(
            kind="agent-question", paused_at="t", question=question
        ),
        lookup=RunLookup(kind=LookupKind.PROJECT, project_id="cf-forge"),
    )


def _paused(run_id: str, *, question: str = "q") -> OpenRun:
    return _run(run_id, "paused", question=question).model_copy(
        update={
            "run_file": RunFileFacts(
                params={"slice": "1"}, execution_mode="sdk", working_directory=None
            ),
            "last_call": CallLine(
                at=NOW,
                directory="/work/forge",
                outcome="skipped",
                reason="settled",
                error=None,
                detail=None,
            ),
        }
    )


def test_a_document_round_trips() -> None:
    document = build_runs_document(
        paused=[_paused("a")],
        other_open=[_run("b")],
        completed=[CompletedRun(run_id="c", status="completed")],
        call_problems=["calls log x: cannot read"],
    )

    assert parse_runs(runs_to_document(document)) == document
    assert [run.run_id for run in document.open_runs] == ["a", "b"]
    assert document.left_out.total == 0


def test_an_over_limit_document_is_cut_with_paused_first_and_counts_per_kind() -> None:
    big = "x" * 1000
    paused = [_paused(f"p{n}", question=big) for n in range(3)]
    other = [_run(f"o{n}", question=big) for n in range(5)]
    completed = [CompletedRun(run_id=f"c{n}", status="completed") for n in range(4)]
    limit = 4096 + 3 * 1500 + 1500

    document = build_runs_document(
        paused=paused,
        other_open=other,
        completed=completed,
        call_problems=[],
        max_bytes=limit,
    )

    kept_ids = [run.run_id for run in document.open_runs]
    assert kept_ids[:3] == ["p0", "p1", "p2"]
    assert document.left_out.paused == 0
    assert document.left_out.open == 5 - (len(kept_ids) - 3)
    assert document.left_out.open > 0
    assert len(document.model_dump_json().encode()) <= limit


def test_a_paused_run_is_cut_only_after_the_room_for_it_is_gone() -> None:
    big = "x" * 2000
    paused = [_paused(f"p{n}", question=big) for n in range(4)]

    document = build_runs_document(
        paused=paused,
        other_open=[_run("o")],
        completed=[],
        call_problems=[],
        max_bytes=4096 + 2 * 2600,
    )

    assert [run.run_id for run in document.open_runs] == ["p0", "p1"]
    assert (document.left_out.paused, document.left_out.open) == (2, 1)


def test_the_default_limit_is_under_the_doors_body_limit() -> None:
    assert RUNS_DOCUMENT_MAX_BYTES == 768 * 1024


def test_a_listing_problem_document_holds_only_the_text() -> None:
    document = listing_problem_document("`sq` was not found on PATH")

    assert parse_runs(runs_to_document(document)) == document
    assert (document.open_runs, document.completed_runs) == ((), ())


@pytest.mark.parametrize(
    "value",
    [
        None,
        "text",
        [],
        {"open_runs": "x"},
        {"unknown": 1},
        {"left_out": {"paused": "a"}},
    ],
)
def test_parse_runs_refuses_missing_and_bad_values(value: object) -> None:
    with pytest.raises(CallRefused) as raised:
        parse_runs(value)

    assert raised.value.code == MALFORMED_CALL
    assert "runs" in raised.value.message


def test_a_refusal_names_the_field_and_never_a_value() -> None:
    with pytest.raises(CallRefused) as raised:
        parse_runs({"call_problems": [{"secret": "hunter2"}]})

    assert "hunter2" not in raised.value.message
    assert RunsDocument.model_fields["call_problems"] is not None
