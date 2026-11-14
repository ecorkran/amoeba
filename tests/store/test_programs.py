"""Program, member and pair reads and upserts."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amoeba.store.errors import StoreIntegrityError
from amoeba.store.models import DependencyPair, MemberSettings
from amoeba.store.programs import (
    get_member,
    get_pair,
    get_program,
    member_settings,
    members_of,
    pairs_of,
    upsert_member,
    upsert_pair,
    upsert_program,
)
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode, RulesFrom
from store.seed import insert_member, insert_pair, insert_program

FIRST = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
LATER = FIRST + timedelta(hours=1)
CONCEPT = "project-documents/user/project-guides/000-concept.demo.md"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _settings(project_id: str = "a", **changes: tuple[str, ...]) -> MemberSettings:
    base = MemberSettings(
        project_id=project_id,
        rules_paths=("CLAUDE.md",),
        authorize_allow=(),
        authorize_deny=(),
        rules_from=RulesFrom.NAMED,
    )
    return replace(base, **changes)


def test_program_is_created_and_read_back(store: Store) -> None:
    with store.write() as transaction:
        changed = upsert_program(
            transaction,
            program_id="demo",
            concept_member=None,
            concept_path=None,
            now=FIRST,
        )
    with store.read() as transaction:
        program = get_program(transaction, "demo")
        missing = get_program(transaction, "nope")

    assert changed
    assert missing is None
    assert program is not None
    assert (program.concept_member, program.concept_path) == (None, None)
    assert program.registered_at == program.updated_at == FIRST


def test_program_unchanged_upsert_keeps_updated_at_and_changed_moves_it(
    store: Store,
) -> None:
    def upsert(now: datetime, member: str | None, path: str | None) -> bool:
        with store.write() as transaction:
            return upsert_program(
                transaction,
                program_id="demo",
                concept_member=member,
                concept_path=path,
                now=now,
            )

    assert upsert(FIRST, None, None)
    assert not upsert(LATER, None, None)
    with store.write() as transaction:
        upsert_member(transaction, program_id="demo", settings=_settings(), now=FIRST)
    assert upsert(LATER, "a", CONCEPT)

    with store.read() as transaction:
        program = get_program(transaction, "demo")
    assert program is not None
    assert (program.concept_member, program.concept_path) == ("a", CONCEPT)
    assert program.registered_at == FIRST
    assert program.updated_at == LATER


@pytest.mark.parametrize(("member", "path"), [("a", None), (None, CONCEPT)])
def test_concept_columns_are_both_null_or_both_set(
    store: Store, member: str | None, path: str | None
) -> None:
    with pytest.raises(StoreIntegrityError), store.write() as transaction:
        upsert_program(
            transaction,
            program_id="demo",
            concept_member=member,
            concept_path=path,
            now=FIRST,
        )


def _program(store: Store) -> None:
    with store.write() as transaction:
        upsert_program(
            transaction,
            program_id="demo",
            concept_member=None,
            concept_path=None,
            now=FIRST,
        )


def test_member_is_created_read_back_and_its_lists_replace_whole(store: Store) -> None:
    _program(store)
    with store.write() as transaction:
        assert upsert_member(
            transaction,
            program_id="demo",
            settings=_settings(rules_paths=("CLAUDE.md", "docs/*.md")),
            now=FIRST,
        )
    with store.write() as transaction:
        assert upsert_member(
            transaction,
            program_id="demo",
            settings=_settings(
                rules_paths=("AGENTS.md",), authorize_allow=("merge_to_main",)
            ),
            now=LATER,
        )
    with store.read() as transaction:
        member = get_member(transaction, "a")
        settings = member_settings(transaction, "a")
        missing = member_settings(transaction, "zz")

    assert member is not None
    assert member.project_id == "a"
    assert member.program_id == "demo"
    assert member.settings.rules_paths == ("AGENTS.md",)
    assert member.settings.authorize_allow == ("merge_to_main",)
    assert member.registered_at == FIRST
    assert member.updated_at == LATER
    assert settings == member.settings
    assert missing is None


def test_member_unchanged_upsert_keeps_updated_at(store: Store) -> None:
    _program(store)
    with store.write() as transaction:
        upsert_member(transaction, program_id="demo", settings=_settings(), now=FIRST)
    with store.write() as transaction:
        changed = upsert_member(
            transaction, program_id="demo", settings=_settings(), now=LATER
        )
    with store.read() as transaction:
        member = get_member(transaction, "a")

    assert not changed
    assert member is not None
    assert member.updated_at == FIRST


def test_a_member_in_a_second_program_is_refused(store: Store) -> None:
    _program(store)
    with store.write() as transaction:
        upsert_program(
            transaction,
            program_id="other",
            concept_member=None,
            concept_path=None,
            now=FIRST,
        )
        upsert_member(transaction, program_id="demo", settings=_settings(), now=FIRST)

    with pytest.raises(StoreIntegrityError, match="belongs to program 'demo'"):
        with store.write() as transaction:
            upsert_member(
                transaction, program_id="other", settings=_settings(), now=LATER
            )


def test_the_unique_key_refuses_a_second_row_for_one_member(store: Store) -> None:
    with pytest.raises(StoreIntegrityError), store.write() as transaction:
        insert_program(
            transaction,
            program_id="demo",
            concept_member=None,
            concept_path=None,
            registered_at=FIRST,
            updated_at=FIRST,
        )
        insert_program(
            transaction,
            program_id="other",
            concept_member=None,
            concept_path=None,
            registered_at=FIRST,
            updated_at=FIRST,
        )
        for program_id in ("demo", "other"):
            insert_member(
                transaction,
                project_id="a",
                program_id=program_id,
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=FIRST,
                updated_at=FIRST,
            )


def test_pair_is_created_read_back_and_consumed_changes_in_place(store: Store) -> None:
    _program(store)
    with store.write() as transaction:
        for project_id in ("provider", "consumer"):
            upsert_member(
                transaction,
                program_id="demo",
                settings=_settings(project_id),
                now=FIRST,
            )

    def upsert(now: datetime, consumed: ConsumedMode) -> bool:
        with store.write() as transaction:
            return upsert_pair(
                transaction,
                program_id="demo",
                provider_id="provider",
                consumer_id="consumer",
                consumed=consumed,
                now=now,
            )

    assert upsert(FIRST, ConsumedMode.FROM_SOURCE)
    assert not upsert(LATER, ConsumedMode.FROM_SOURCE)
    assert upsert(LATER, ConsumedMode.FROM_RELEASE)
    with store.read() as transaction:
        pairs = pairs_of(transaction, "demo")
        one = get_pair(transaction, "provider", "consumer")
        none = get_pair(transaction, "consumer", "provider")

    assert pairs == (
        DependencyPair(
            program_id="demo",
            provider_id="provider",
            consumer_id="consumer",
            consumed=ConsumedMode.FROM_RELEASE,
            registered_at=FIRST,
            updated_at=LATER,
        ),
    )
    assert one == pairs[0]
    assert none is None


def test_members_of_lists_one_program_in_id_order(store: Store) -> None:
    _program(store)
    with store.write() as transaction:
        upsert_program(
            transaction,
            program_id="other",
            concept_member=None,
            concept_path=None,
            now=FIRST,
        )
        for program_id, project_id in (("demo", "b"), ("demo", "a"), ("other", "c")):
            upsert_member(
                transaction,
                program_id=program_id,
                settings=_settings(project_id),
                now=FIRST,
            )
    with store.read() as transaction:
        members = members_of(transaction, "demo")

    assert [member.project_id for member in members] == ["a", "b"]


def test_seeded_state_reads_back_through_programs(store: Store) -> None:
    with store.write() as transaction:
        insert_program(
            transaction,
            program_id="demo",
            concept_member=None,
            concept_path=None,
            registered_at=FIRST,
            updated_at=FIRST,
        )
        for project_id in ("provider", "consumer"):
            insert_member(
                transaction,
                project_id=project_id,
                program_id="demo",
                rules_paths=("CLAUDE.md",),
                authorize_allow=("x",),
                authorize_deny=(),
                registered_at=FIRST,
                updated_at=FIRST,
            )
        insert_pair(
            transaction,
            program_id="demo",
            provider_id="provider",
            consumer_id="consumer",
            consumed=ConsumedMode.FROM_SOURCE,
            registered_at=FIRST,
            updated_at=FIRST,
        )
    with store.read() as transaction:
        members = members_of(transaction, "demo")
        pairs = pairs_of(transaction, "demo")

    assert [member.project_id for member in members] == ["consumer", "provider"]
    assert members[0].settings.authorize_allow == ("x",)
    assert [(pair.provider_id, pair.consumer_id) for pair in pairs] == [
        ("provider", "consumer")
    ]
