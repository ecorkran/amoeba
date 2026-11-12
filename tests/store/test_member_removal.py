"""Soft removal of members and pairs (slice 228, D8): the active-member predicate."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from amoeba.store.decisions import answers_since
from amoeba.store.errors import StoreIntegrityError
from amoeba.store.models import MemberSettings
from amoeba.store.programs import (
    get_member,
    get_member_any,
    get_pair,
    member_settings,
    members_of,
    pairs_of,
    remove_member,
    remove_pair,
    upsert_member,
)
from amoeba.store.questions import get_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode
from store.decision_support import (
    CORE,
    FIRST,
    LINT,
    SECOND,
    TOOLS,
    TRADING,
    at,
    automatic_answer,
    seed_programs,
    waiting_then_pm,
)
from store.question_support import NOW
from store.seed import insert_member, insert_pair

REMOVED_AT = NOW + timedelta(days=1)
THIRD_MEMBER = "member-third"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_programs(opened)
        with opened.write() as transaction:
            insert_member(
                transaction,
                project_id=THIRD_MEMBER,
                program_id=TRADING,
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=NOW,
                updated_at=NOW,
            )
            insert_pair(
                transaction,
                program_id=TRADING,
                provider_id=CORE,
                consumer_id=THIRD_MEMBER,
                consumed=ConsumedMode.FROM_SOURCE,
                registered_at=NOW,
                updated_at=NOW,
            )
            insert_pair(
                transaction,
                program_id=TRADING,
                provider_id=THIRD_MEMBER,
                consumer_id=CORE,
                consumed=ConsumedMode.FROM_RELEASE,
                registered_at=NOW,
                updated_at=NOW,
            )
        yield opened


def _settings(project_id: str) -> MemberSettings:
    return MemberSettings(
        project_id=project_id,
        rules_paths=("CLAUDE.md",),
        authorize_allow=(),
        authorize_deny=(),
    )


def _remove(store: Store, project_id: str) -> bool:
    with store.write() as transaction:
        return remove_member(transaction, project_id, REMOVED_AT)


def test_a_removed_member_is_absent_from_every_member_read(store: Store) -> None:
    assert _remove(store, THIRD_MEMBER)

    with store.read() as transaction:
        assert get_member(transaction, THIRD_MEMBER) is None
        assert member_settings(transaction, THIRD_MEMBER) is None
        assert [m.project_id for m in members_of(transaction, TRADING)] == [CORE]


def test_get_member_any_still_reads_it_with_its_removal_time(store: Store) -> None:
    _remove(store, THIRD_MEMBER)

    with store.read() as transaction:
        removed = get_member_any(transaction, THIRD_MEMBER)
        stranger = get_member_any(transaction, "no-such-member")

    assert removed is not None
    assert removed.removed_at == REMOVED_AT
    assert stranger is None


def test_removing_deletes_the_members_pairs_in_both_directions(store: Store) -> None:
    _remove(store, THIRD_MEMBER)

    with store.read() as transaction:
        assert pairs_of(transaction, TRADING) == ()
        assert get_pair(transaction, CORE, THIRD_MEMBER) is None
        remaining = transaction.execute("SELECT COUNT(*) FROM dependency_pairs")
        assert remaining.fetchone() == (0,)


def test_removing_twice_or_a_stranger_changes_nothing(store: Store) -> None:
    assert _remove(store, THIRD_MEMBER)

    assert not _remove(store, THIRD_MEMBER)
    assert not _remove(store, "no-such-member")
    with store.read() as transaction:
        row = get_member_any(transaction, THIRD_MEMBER)
    assert row is not None
    assert row.removed_at == REMOVED_AT


def test_remove_pair_deletes_one_pair_and_reports_absence(store: Store) -> None:
    with store.write() as transaction:
        assert remove_pair(transaction, CORE, THIRD_MEMBER)
        assert not remove_pair(transaction, CORE, THIRD_MEMBER)

    with store.read() as transaction:
        (left,) = pairs_of(transaction, TRADING)
    assert (left.provider_id, left.consumer_id) == (THIRD_MEMBER, CORE)


def test_a_pair_is_not_read_when_an_end_is_removed(store: Store) -> None:
    # remove_member deletes the pairs; the read rule holds without that, too.
    with store.write() as transaction:
        transaction.execute(
            "UPDATE members SET removed_at = ? WHERE project_id = ?",
            ("2026-11-10T00:00:00Z", THIRD_MEMBER),
        )

    with store.read() as transaction:
        assert pairs_of(transaction, TRADING) == ()
        assert get_pair(transaction, THIRD_MEMBER, CORE) is None


def test_the_removed_members_questions_answers_and_releases_remain(
    store: Store,
) -> None:
    automatic_answer(store, FIRST, THIRD_MEMBER, 1)
    waiting_then_pm(store, SECOND, THIRD_MEMBER, 2)
    with store.write() as transaction:
        transaction.execute(
            "INSERT INTO releases (member_id, commit_sha, changed, touched, "
            "reported_at) VALUES (?, 'abc', '[]', '[]', '2026-11-10T00:00:00Z')",
            (THIRD_MEMBER,),
        )

    _remove(store, THIRD_MEMBER)

    with store.read() as transaction:
        assert get_question(transaction, FIRST) is not None
        assert get_question(transaction, SECOND) is not None
        assert transaction.execute("SELECT COUNT(*) FROM answers").fetchone() == (2,)
        assert transaction.execute("SELECT COUNT(*) FROM releases").fetchone() == (1,)


def test_decisions_still_lists_a_removed_members_answers(store: Store) -> None:
    automatic_answer(store, FIRST, THIRD_MEMBER, 1)
    _remove(store, THIRD_MEMBER)

    with store.read() as transaction:
        listed = answers_since(transaction, after_seq=0, program=TRADING)

    assert [row.question.key for row in listed] == [FIRST]
    assert listed[0].program_id == TRADING


def test_re_registering_clears_removed_at_and_makes_it_a_member_again(
    store: Store,
) -> None:
    _remove(store, THIRD_MEMBER)

    with store.write() as transaction:
        wrote = upsert_member(
            transaction,
            program_id=TRADING,
            settings=_settings(THIRD_MEMBER),
            now=at(3),
        )

    assert wrote
    with store.read() as transaction:
        member = get_member(transaction, THIRD_MEMBER)
    assert member is not None
    assert member.removed_at is None
    assert member.settings.rules_paths == ("CLAUDE.md",)
    assert member.registered_at == at(3)


def test_a_removed_member_can_be_re_registered_in_another_program(
    store: Store,
) -> None:
    _remove(store, THIRD_MEMBER)

    with store.write() as transaction:
        upsert_member(
            transaction,
            program_id=TOOLS,
            settings=_settings(THIRD_MEMBER),
            now=at(3),
        )

    with store.read() as transaction:
        member = get_member(transaction, THIRD_MEMBER)
        assert member is not None
        assert member.program_id == TOOLS
        assert [m.project_id for m in members_of(transaction, TRADING)] == [CORE]
        assert {m.project_id for m in members_of(transaction, TOOLS)} == {
            LINT,
            THIRD_MEMBER,
        }


def test_an_active_member_in_another_program_is_still_refused(store: Store) -> None:
    with store.write() as transaction, pytest.raises(StoreIntegrityError):
        upsert_member(
            transaction,
            program_id=TOOLS,
            settings=_settings(THIRD_MEMBER),
            now=at(3),
        )
