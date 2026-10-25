"""D2, D1: journal and run the pointer write in the checkout, then read it back."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from cf_stub import (
    GET_MODE_ENV,
    GET_QUIRK_ENV,
    SET_MODE_ENV,
    GetQuirk,
    PointerMode,
    write_cf_state,
)

from amoeba.runner.dispatch.checkout import Checkout
from amoeba.runner.dispatch.pointer import (
    PARAM_EXPECTED,
    PARAM_EXPECTED_WORKTREE_ID,
    PARAM_PROJECT,
    Confirmed,
    Mismatch,
    PointerReadFailed,
    PointerUnknown,
    SetCutOff,
    SetDone,
    SetFailed,
    issue_pointer_write,
    read_back,
)
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_EXPECTED_SLICE_INDEX,
    PARAM_RESOLUTION,
    CommandKind,
    Store,
)
from runner.dispatch.pointer_support import (
    CF_ID,
    PROJECT,
    TIMEOUT,
    Rig,
    budget_allowing,
    generous_budget,
)


@pytest.fixture
def rig(tmp_path: Path, store: Store) -> Iterator[Rig]:
    yield Rig(tmp_path, store)


def test_a_write_is_confirmed_by_the_read_back(rig: Rig) -> None:
    attempt = issue_pointer_write(
        rig.store, rig.action(), rig.run(), TIMEOUT, generous_budget()
    )

    assert attempt is not None
    assert isinstance(attempt.set_result, SetDone)
    assert isinstance(attempt.answer, Confirmed)
    assert (attempt.answer.stem.index, attempt.answer.stem.name) == (
        125,
        "run-dispatch-and-outcome-ingestion",
    )


def test_the_write_is_journaled_with_the_checkout_and_the_index(rig: Rig) -> None:
    attempt = issue_pointer_write(
        rig.store, rig.action(), rig.run(), TIMEOUT, generous_budget()
    )

    assert attempt is not None
    entry = rig.store.journal_entry(attempt.entry.id)
    assert entry is not None and entry.kind is CommandKind.CF_WRITE
    assert not entry.is_resolved, "issuing resolves nothing"
    assert entry.parameters == {
        PARAM_PROJECT: CF_ID,
        PARAM_CHECKOUT: str(rig.root),
        PARAM_EXPECTED: {},
        PARAM_EXPECTED_SLICE_INDEX: 125,
        PARAM_EXPECTED_WORKTREE_ID: "wt_a",
    }


def test_the_second_worktree_is_written_and_read_in_its_own_directory(rig: Rig) -> None:
    attempt = issue_pointer_write(
        rig.store, rig.action(225, "second"), rig.run(), TIMEOUT, generous_budget()
    )

    assert attempt is not None and isinstance(attempt.answer, Confirmed)
    assert attempt.answer.result["worktree_id"] == "wt_b"


def test_a_failed_set_is_reported_and_not_read_back(rig: Rig) -> None:
    run = rig.run({SET_MODE_ENV: PointerMode.FAIL.value})

    attempt = issue_pointer_write(
        rig.store, rig.action(), run, TIMEOUT, generous_budget()
    )

    assert attempt is not None
    assert (
        isinstance(attempt.set_result, SetFailed) and attempt.set_result.exit_code == 1
    )
    assert "set failed" in attempt.set_result.detail
    assert attempt.answer is None


def test_an_index_with_no_slice_fails_with_the_head_of_cf_output(rig: Rig) -> None:
    attempt = issue_pointer_write(
        rig.store, rig.action(999), rig.run(), TIMEOUT, generous_budget()
    )

    assert attempt is not None and isinstance(attempt.set_result, SetFailed)
    assert "ARTIFACT_NOT_FOUND" in attempt.set_result.detail


def test_a_set_that_times_out_is_a_cut_off_and_not_read_back(rig: Rig) -> None:
    def hang(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(argv, 1.0)

    attempt = issue_pointer_write(
        rig.store, rig.action(), hang, TIMEOUT, generous_budget()
    )

    assert attempt is not None
    assert isinstance(attempt.set_result, SetCutOff)
    assert "timed out" in attempt.set_result.detail
    assert attempt.answer is None


def test_another_index_is_a_mismatch(rig: Rig) -> None:
    write_cf_state(
        rig.state_path,
        cf_project_id=CF_ID,
        project_path=rig.root,
        worktrees=[Rig.worktree_entry("wt_a", rig.root, 100, 199)],
        slices={125: "126-slice.the-wrong-one"},
    )

    attempt = issue_pointer_write(
        rig.store, rig.action(), rig.run(), TIMEOUT, generous_budget()
    )

    assert attempt is not None and isinstance(attempt.answer, Mismatch)


@pytest.mark.parametrize(
    ("quirk", "fragment"),
    [
        (GetQuirk.OTHER_PROJECT_PATH, "answered for"),
        (GetQuirk.OTHER_WORKTREE_ID, "worktree"),
    ],
)
def test_a_path_or_worktree_mismatch_is_a_mismatch(
    rig: Rig, quirk: GetQuirk, fragment: str
) -> None:
    run = rig.run({GET_QUIRK_ENV: quirk.value})

    attempt = issue_pointer_write(
        rig.store, rig.action(), run, TIMEOUT, generous_budget()
    )

    assert attempt is not None and isinstance(attempt.answer, Mismatch)
    assert fragment in attempt.answer.reason


def test_a_record_without_file_slice_is_unknown(rig: Rig) -> None:
    run = rig.run({GET_QUIRK_ENV: GetQuirk.OMIT_FILE_SLICE.value})

    attempt = issue_pointer_write(
        rig.store, rig.action(), run, TIMEOUT, generous_budget()
    )

    assert attempt is not None and isinstance(attempt.answer, PointerUnknown)


def test_a_get_that_fails_is_a_failed_read(rig: Rig) -> None:
    run = rig.run({GET_MODE_ENV: PointerMode.FAIL.value})

    attempt = issue_pointer_write(
        rig.store, rig.action(), run, TIMEOUT, generous_budget()
    )

    assert attempt is not None
    assert isinstance(attempt.set_result, SetDone)
    assert isinstance(attempt.answer, PointerReadFailed)


def test_read_back_alone_judges_an_existing_entry(rig: Rig) -> None:
    attempt = issue_pointer_write(
        rig.store, rig.action(), rig.run(), TIMEOUT, generous_budget()
    )
    assert attempt is not None

    answer = read_back(attempt.entry, Checkout(rig.root, "wt_a"), rig.run(), TIMEOUT)

    assert isinstance(answer, Confirmed)


def test_a_budget_that_refuses_the_first_call_does_nothing(rig: Rig) -> None:
    calls: list[list[str]] = []

    def record(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    attempt = issue_pointer_write(
        rig.store, rig.action(), record, TIMEOUT, budget_allowing(0)
    )

    assert attempt is None
    assert calls == []
    assert rig.store.journal_entries(PROJECT) == []


def test_a_budget_that_refuses_the_read_back_leaves_it_for_the_next_tick(
    rig: Rig,
) -> None:
    calls: list[list[str]] = []
    real = rig.run()

    def record(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return real(argv, **kwargs)

    attempt = issue_pointer_write(
        rig.store, rig.action(), record, TIMEOUT, budget_allowing(1)
    )

    assert attempt is not None
    assert isinstance(attempt.set_result, SetDone) and attempt.answer is None
    assert [argv[1] for argv in calls] == ["set"], "one call, the read-back waits"
    assert not attempt.entry.is_resolved


def test_a_write_carrying_a_resolution_names_it_on_the_entry(rig: Rig) -> None:
    action = replace(rig.action(), resolution="blocked-1")

    attempt = issue_pointer_write(
        rig.store, action, rig.run(), TIMEOUT, generous_budget()
    )

    assert attempt is not None
    assert attempt.entry.parameters[PARAM_RESOLUTION] == "blocked-1"


def test_a_write_with_no_resolution_has_no_key(rig: Rig) -> None:
    attempt = issue_pointer_write(
        rig.store, rig.action(), rig.run(), TIMEOUT, generous_budget()
    )

    assert attempt is not None
    assert PARAM_RESOLUTION not in attempt.entry.parameters
