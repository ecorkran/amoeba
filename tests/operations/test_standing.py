"""``standing``: give a ruling, safely repeated (slice 230, D2, D10)."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager
from datetime import timedelta
from pathlib import Path

import pytest
from cf_fixtures import fake_cf_run

from amoeba.operations.members import ContextForgeError
from amoeba.operations.standing import standing
from amoeba.operations.standing_models import (
    StandingOutcome,
    StandingRejection,
    StandingResult,
)
from amoeba.store.standing import list_standing
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import StandingReach
from operations.standing_support import (
    MAX_CHARS,
    NOW,
    RecordingCf,
    seeded_store,
    standing_count,
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from seeded_store(tmp_path / "amoeba.sqlite3")


def _give(
    store: Store, document: object, cf: RecordingCf | None = None
) -> StandingResult:
    return standing(
        store, document, max_chars=MAX_CHARS, run=cf or RecordingCf(), now=NOW
    )


@pytest.mark.parametrize(
    ("document", "reach", "program", "member"),
    [
        ({"text": "rule"}, StandingReach.ALL, None, None),
        ({"text": "rule", "program": "demo"}, StandingReach.PROGRAM, "demo", None),
        ({"text": "rule", "member": "alpha"}, StandingReach.MEMBER, None, "alpha-id"),
        ({"text": "rule", "member": "beta-id"}, StandingReach.MEMBER, None, "beta-id"),
    ],
)
def test_each_reach_gives_a_row_with_the_right_fields(
    store: Store,
    document: dict[str, str],
    reach: StandingReach,
    program: str | None,
    member: str | None,
) -> None:
    result = _give(store, document)

    with store.read() as transaction:
        (row,) = list_standing(transaction, include_withdrawn=False)
    assert result.outcome is StandingOutcome.GIVEN
    assert (result.standing_id, result.reach, result.program, result.member) == (
        row.standing_id,
        reach,
        program,
        member,
    )
    assert (row.text, row.reach, row.program_id, row.member_id, row.given_at) == (
        "rule",
        reach,
        program,
        member,
        NOW,
    )


def test_a_repeat_is_unchanged_with_the_same_id(store: Store) -> None:
    first = _give(store, {"text": "rule", "member": "alpha"})
    second = standing(
        store,
        {"text": "rule", "member": "alpha-id"},
        max_chars=MAX_CHARS,
        run=RecordingCf(),
        now=NOW + timedelta(hours=1),
    )

    assert second.outcome is StandingOutcome.UNCHANGED
    assert second.standing_id == first.standing_id
    assert standing_count(store) == 1


@pytest.mark.parametrize(
    ("document", "rejection"),
    [
        ({"text": "r", "program": "nope"}, StandingRejection.NO_SUCH_PROGRAM),
        ({"text": "r", "member": "unknown"}, StandingRejection.NO_SUCH_MEMBER),
        ({"text": "r", "member": "gone"}, StandingRejection.NO_SUCH_MEMBER),
        ({"text": "r", "member": "stranger"}, StandingRejection.NO_SUCH_MEMBER),
        (
            {"text": "r", "program": "demo", "member": "alpha"},
            StandingRejection.MALFORMED,
        ),
        ({"text": "   "}, StandingRejection.MALFORMED),
        ({"text": "r", "extra": 1}, StandingRejection.MALFORMED),
    ],
)
def test_a_rejection_writes_nothing(
    store: Store, document: dict[str, object], rejection: StandingRejection
) -> None:
    result = _give(store, document)

    assert (result.outcome, result.rejection) == (StandingOutcome.REJECTED, rejection)
    assert result.problems
    assert result.standing_id is None
    assert standing_count(store) == 0


def test_both_flags_names_both_fields(store: Store) -> None:
    result = _give(store, {"text": "r", "program": "demo", "member": "alpha"})

    assert any("program" in p and "member" in p for p in result.problems)


def test_a_cf_failure_raises_and_writes_nothing(store: Store) -> None:
    with pytest.raises(ContextForgeError):
        standing(
            store,
            {"text": "r", "member": "alpha"},
            max_chars=MAX_CHARS,
            run=fake_cf_run(None),
            now=NOW,
        )

    assert standing_count(store) == 0


def test_the_member_lookup_runs_cf_with_no_working_directory(store: Store) -> None:
    cf = RecordingCf()

    _give(store, {"text": "r", "member": "alpha"}, cf)

    assert len(cf.calls) == 1
    assert all("cwd" not in keywords for keywords in cf.keywords)


def test_no_member_means_no_cf_call(store: Store) -> None:
    cf = RecordingCf()

    _give(store, {"text": "r", "program": "demo"}, cf)

    assert cf.calls == []


def test_a_committed_give_whose_result_is_dropped_repeats_as_unchanged(
    store: Store,
) -> None:
    document = {"text": "rule", "program": "demo"}
    _give(store, document)  # committed; the caller never saw the result (D10)

    repeated = _give(store, document)

    with store.read() as transaction:
        (row,) = list_standing(transaction, include_withdrawn=True)
    assert repeated.outcome is StandingOutcome.UNCHANGED
    assert repeated.standing_id == row.standing_id


def test_the_member_lookup_runs_before_the_write_lock_is_taken(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ``cf`` subprocess runs while ``standing`` holds the store's write lock."""
    events: list[str] = []
    cf = RecordingCf()
    original_write = Store.write

    def recording_write(self: Store) -> AbstractContextManager[Transaction]:
        events.append("write")
        return original_write(self)

    def recording_cf(
        argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        events.append("cf")
        return cf(argv, **kwargs)

    monkeypatch.setattr(Store, "write", recording_write)

    standing(
        store,
        {"text": "r", "member": "alpha"},
        max_chars=MAX_CHARS,
        run=recording_cf,
        now=NOW,
    )

    assert events == ["cf", "write"]


def test_a_row_taking_a_reached_members_standing_answers_past_the_cap_is_too_long(
    store: Store,
) -> None:
    """The rendered share counts, with the active rows already reaching the member."""
    first = _give(store, {"text": "x" * 600, "member": "alpha"})
    over = _give(store, {"text": "y" * 400})

    assert first.outcome is StandingOutcome.GIVEN
    assert (over.outcome, over.rejection) == (
        StandingOutcome.REJECTED,
        StandingRejection.TOO_LONG,
    )
    assert "reaching alpha-id" in over.problems[0]
    assert f"passages_max_chars is {MAX_CHARS}" in over.problems[0]
    assert standing_count(store) == 1


def test_the_rendered_passage_counts_not_only_the_raw_text(store: Store) -> None:
    result = _give(store, {"text": "z" * MAX_CHARS})

    assert result.rejection is StandingRejection.TOO_LONG
    assert standing_count(store) == 0


def test_a_row_whose_reach_misses_the_full_member_is_given(store: Store) -> None:
    _give(store, {"text": "x" * 600, "member": "alpha"})

    other = _give(store, {"text": "y" * 400, "program": "second"})

    assert other.outcome is StandingOutcome.GIVEN
    assert standing_count(store) == 2
