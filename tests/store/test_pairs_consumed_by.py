"""``pairs_consumed_by``: only the consumer's own active pairs (slice 227)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from amoeba.store import sql
from amoeba.store.programs import pairs_consumed_by
from amoeba.store.row_values import encode_timestamp
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import ConsumedMode
from store.release_support import PROGRAM, START, seed_members
from store.seed import insert_member, insert_pair

CONSUMER = "consumer-id"
SECOND_PROVIDER = "second-provider-id"
OTHER_CONSUMER = "other-consumer-id"
FIRST_PROVIDER = "provider-id"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        seed_members(opened)
        with opened.write() as transaction:
            for member in (CONSUMER, SECOND_PROVIDER, OTHER_CONSUMER):
                insert_member(
                    transaction,
                    project_id=member,
                    program_id=PROGRAM,
                    rules_paths=(),
                    authorize_allow=(),
                    authorize_deny=(),
                    registered_at=START,
                    updated_at=START,
                )
            for provider, consumer in (
                (SECOND_PROVIDER, CONSUMER),
                (FIRST_PROVIDER, CONSUMER),
                (FIRST_PROVIDER, OTHER_CONSUMER),
                (CONSUMER, OTHER_CONSUMER),
            ):
                insert_pair(
                    transaction,
                    program_id=PROGRAM,
                    provider_id=provider,
                    consumer_id=consumer,
                    consumed=ConsumedMode.FROM_SOURCE,
                    registered_at=START,
                    updated_at=START,
                )
        yield opened


def _providers(transaction: Transaction, consumer: str) -> list[str]:
    return [pair.provider_id for pair in pairs_consumed_by(transaction, consumer)]


def test_only_the_consumers_own_pairs_come_back_by_provider_id(store: Store) -> None:
    with store.read() as transaction:
        assert _providers(transaction, CONSUMER) == [FIRST_PROVIDER, SECOND_PROVIDER]
        assert _providers(transaction, OTHER_CONSUMER) == [CONSUMER, FIRST_PROVIDER]


def test_a_member_that_consumes_nothing_has_no_pairs(store: Store) -> None:
    with store.read() as transaction:
        assert _providers(transaction, FIRST_PROVIDER) == []


def test_a_pair_with_a_removed_end_is_not_returned(store: Store) -> None:
    with store.write() as transaction:
        stamp = encode_timestamp(START)
        # Only the member row: the active-end rule alone must hide the pair.
        transaction.execute(sql.REMOVE_MEMBER, (stamp, stamp, SECOND_PROVIDER))
    with store.read() as transaction:
        assert _providers(transaction, CONSUMER) == [FIRST_PROVIDER]
