"""Release notes: recipients outside D5's table, the body bound, the text (slice 243,
D5). The table itself is ``test_release_notes_match_changes``."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from store.release_support import (
    FULL_HASH,
    OTHER_HASH,
    PROGRAM,
    PROVIDER,
    seed_members,
)
from store.seed import insert_member, insert_pair
from store_open import open_local_store

from amoeba.operations import release_notes
from amoeba.operations.deps import Deps
from amoeba.operations.message_models import MAX_SUBJECT_LENGTH
from amoeba.operations.release_fields import FULL_HASH_LENGTHS, MAX_VERSION_LENGTH
from amoeba.operations.release_notes import (
    MAX_RELEASE_NOTE_BODY_LENGTH,
    NO_VERSION,
    NOTE_OUTCOMES,
    compose_release_note,
)
from amoeba.operations.report_release import report_release
from amoeba.operations.report_release_models import (
    MAX_CHANGED_LENGTH,
    MAX_TOUCHED_ITEM_LENGTH,
    MAX_TOUCHED_ITEMS,
    ReportOutcome,
    ReportReleaseRequest,
    ReportReleaseResult,
)
from amoeba.store import sql
from amoeba.store.programs import upsert_pair
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode
from operations.release_support import (
    PROVIDER_DIR,
    RELEASE_CONSUMER,
    SOURCE_CONSUMER,
    SOURCE_CONSUMER_DIR,
    SettableClock,
    note_rows,
    notified,
    release_deps,
    seed_pairs,
)

LATE_CONSUMER = "late-consumer-id"
LONGEST_HASH = "f" * max(FULL_HASH_LENGTHS)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        seed_pairs(opened)
        yield opened


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def deps(tmp_path: Path, clock: SettableClock) -> Deps:
    return release_deps(tmp_path, clock)


def _report(
    store: Store,
    deps: Deps,
    mode: str = "report",
    *,
    commit: str = FULL_HASH,
    version: str | None = None,
    directory: Path = PROVIDER_DIR,
) -> ReportReleaseResult:
    document: dict[str, object] = {"mode": mode, "commit": commit}
    if mode != "withdraw":
        document.update(changed="what changed", touched=["cli", "store"])
    if version is not None:
        document["version"] = version
    return report_release(store, document, directory=directory, deps=deps)


def _subjects_for(store: Store, member: str) -> list[str]:
    return [row[3] for row in note_rows(store) if row[2] == member]


# --- recipients outside D5's table -----------------------------------------


def test_a_consumer_added_after_the_report_gets_the_correction_and_the_withdrawal(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _report(store, deps)
    with store.write() as transaction:
        insert_member(
            transaction,
            project_id=LATE_CONSUMER,
            program_id=PROGRAM,
            rules_paths=(),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=clock.now,
            updated_at=clock.now,
        )
        insert_pair(
            transaction,
            program_id=PROGRAM,
            provider_id=PROVIDER,
            consumer_id=LATE_CONSUMER,
            consumed=ConsumedMode.FROM_SOURCE,
            registered_at=clock.now,
            updated_at=clock.now,
        )
    assert _subjects_for(store, LATE_CONSUMER) == []

    clock.now += timedelta(hours=1)
    _report(store, deps, "correct")
    clock.now += timedelta(hours=1)
    _report(store, deps, "withdraw")

    subjects = _subjects_for(store, LATE_CONSUMER)
    assert [subject.split(":")[0] for subject in subjects] == [
        f"Release report {ReportOutcome.CORRECTED.value}",
        f"Release report {ReportOutcome.WITHDRAWN.value}",
    ]


def test_a_removed_consumer_gets_no_note(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    stamp = encode_timestamp(clock.now)
    with store.write() as transaction:
        # Only the member row: the active-end rule alone must hide the pair.
        transaction.execute(sql.REMOVE_MEMBER, (stamp, stamp, SOURCE_CONSUMER))

    _report(store, deps, version="tag-one")

    assert notified(store) == [RELEASE_CONSUMER]


def test_a_provider_with_no_consumers_stores_its_report_and_writes_no_note(
    store: Store, deps: Deps
) -> None:
    result = _report(store, deps, directory=SOURCE_CONSUMER_DIR)

    assert result.outcome is ReportOutcome.RECORDED
    assert note_rows(store) == []


# --- D5's two behaviours ---------------------------------------------------


def test_a_consumer_whose_mode_changes_later_gets_no_note_for_an_earlier_report(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _report(store, deps, version="tag-one")
    assert sorted(notified(store)) == sorted([SOURCE_CONSUMER, RELEASE_CONSUMER])

    clock.now += timedelta(hours=1)
    with store.write() as transaction:
        for consumer, mode in (
            (RELEASE_CONSUMER, ConsumedMode.FROM_SOURCE),
            (SOURCE_CONSUMER, ConsumedMode.FROM_RELEASE),
        ):
            upsert_pair(
                transaction,
                program_id=PROGRAM,
                provider_id=PROVIDER,
                consumer_id=consumer,
                consumed=mode,
                now=clock.now,
            )

    assert len(note_rows(store)) == 2


def test_a_second_report_at_the_same_instant_does_not_change_the_first_ones_recipients(
    store: Store, deps: Deps
) -> None:
    """Fixed clock: both reports are written at ``now``; the check is on each
    report's own ``seq``, so the other report's time adds and removes nobody."""
    _report(store, deps, commit=FULL_HASH, version="tag-one")
    _report(store, deps, commit=OTHER_HASH)

    by_commit: dict[str, list[str]] = {FULL_HASH: [], OTHER_HASH: []}
    for _id, _from, to_member, _subject, body in note_rows(store):
        commit = FULL_HASH if FULL_HASH in body else OTHER_HASH
        by_commit[commit].append(to_member)
    assert sorted(by_commit[FULL_HASH]) == sorted([SOURCE_CONSUMER, RELEASE_CONSUMER])
    assert by_commit[OTHER_HASH] == [SOURCE_CONSUMER]


# --- the body bound --------------------------------------------------------


def _largest_request(mode: str) -> ReportReleaseRequest:
    """The largest report, built through the request model so its limits, not this
    test, say what is allowed."""
    return ReportReleaseRequest.model_validate(
        {
            "mode": mode,
            "commit": LONGEST_HASH,
            "version": "v" * MAX_VERSION_LENGTH,
            "changed": "c" * MAX_CHANGED_LENGTH,
            "touched": [
                f"{number:0{MAX_TOUCHED_ITEM_LENGTH}d}"
                for number in range(MAX_TOUCHED_ITEMS)
            ],
        }
    )


def _every_outcome_fits() -> bool:
    request = _largest_request("report")
    assert request.changed is not None and request.touched is not None
    for outcome in NOTE_OUTCOMES:
        subject, body = compose_release_note(
            outcome, request.commit, request.version, request.changed, request.touched
        )
        if (
            len(body) > MAX_RELEASE_NOTE_BODY_LENGTH
            or len(subject) > MAX_SUBJECT_LENGTH
        ):
            return False
    return True


def test_the_report_models_accept_each_limit_and_refuse_one_more() -> None:
    assert _largest_request("report").touched is not None
    for field, value in (
        ("version", "v" * (MAX_VERSION_LENGTH + 1)),
        ("changed", "c" * (MAX_CHANGED_LENGTH + 1)),
        ("touched", ["t" * (MAX_TOUCHED_ITEM_LENGTH + 1)]),
        ("touched", [str(n) for n in range(MAX_TOUCHED_ITEMS + 1)]),
        ("commit", "f" * (max(FULL_HASH_LENGTHS) + 1)),
    ):
        document: dict[str, object] = {
            "commit": LONGEST_HASH,
            "changed": "c",
            "touched": ["t"],
            field: value,
        }
        with pytest.raises(ValueError, match=field):
            ReportReleaseRequest.model_validate(document)


def test_the_largest_report_fits_the_constant_for_all_four_outcomes() -> None:
    assert len(NOTE_OUTCOMES) == 4
    assert _every_outcome_fits()


def test_the_check_fails_when_the_template_grows_past_the_constant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        release_notes,
        "CLOSING_LINE",
        release_notes.CLOSING_LINE + " and some more words than the constant counted",
    )

    assert not _every_outcome_fits()


# --- the text --------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome",
    [ReportOutcome.RECORDED, ReportOutcome.VERSIONED, ReportOutcome.CORRECTED],
)
def test_a_writing_outcomes_note_carries_commit_version_changed_and_touched(
    outcome: ReportOutcome,
) -> None:
    subject, body = compose_release_note(
        outcome, FULL_HASH, "tag-one", "adds the thing", ("alpha", "beta")
    )

    assert subject == f"Release report {outcome.value}: tag-one"
    assert outcome.value in body.splitlines()[0]
    assert FULL_HASH in body and "tag-one" in body
    assert "adds the thing" in body
    assert "alpha; beta" in body
    assert "changes" in body.splitlines()[-1]


def test_a_note_for_a_report_with_no_version_says_none_and_names_the_commit() -> None:
    subject, body = compose_release_note(
        ReportOutcome.RECORDED, FULL_HASH, None, "text", ("one",)
    )

    assert subject.endswith(FULL_HASH)
    assert f"Version: {NO_VERSION}" in body


def test_a_correction_says_it_replaces_the_earlier_text_and_other_outcomes_do_not() -> (
    None
):
    _, corrected = compose_release_note(
        ReportOutcome.CORRECTED, FULL_HASH, None, "text", ("one",)
    )
    _, recorded = compose_release_note(
        ReportOutcome.RECORDED, FULL_HASH, None, "text", ("one",)
    )

    assert "replaces the earlier text" in corrected
    assert "replaces" not in recorded


def test_a_withdrawal_carries_no_changed_text_and_says_to_disregard() -> None:
    subject, body = compose_release_note(
        ReportOutcome.WITHDRAWN, FULL_HASH, "tag-one", "secret changed text", ("one",)
    )

    assert subject == f"Release report {ReportOutcome.WITHDRAWN.value}: tag-one"
    assert "secret changed text" not in body
    assert "disregard" in body
    assert FULL_HASH in body and "tag-one" in body
