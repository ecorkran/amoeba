"""Directories, a settable clock and ``Deps`` for the release operation tests
(slice 227)."""

from __future__ import annotations

import sqlite3
import subprocess
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from store.release_support import OTHER_PROVIDER, PROGRAM, PROVIDER, START
from store.seed import insert_member, insert_pair

from amoeba.operations.deps import Deps
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode
from amoeba.upstream.context_forge.cli_call import CfCallFailed
from amoeba.upstream.context_forge.projects import ProjectNames
from operations.status_support import CfAnswer, FakeCf, status_deps

PROVIDER_DIR = Path("/work/provider")
OTHER_DIR = Path("/work/other")
NOT_IN_PROGRAM_DIR = Path("/work/not-in-program")
NOT_A_PROJECT_DIR = Path("/work/not-a-project")
CF_DOWN_DIR = Path("/work/cf-down")
SOURCE_CONSUMER_DIR = Path("/work/source-consumer")
RELEASE_CONSUMER_DIR = Path("/work/release-consumer")
NOT_IN_PROGRAM_ID = "project-in-no-program"
SOURCE_CONSUMER = "consumer-source-id"
RELEASE_CONSUMER = "consumer-release-id"
GONE_PROVIDER = "gone-provider-id"


@dataclass
class SettableClock:
    """``Deps.clock``: returns ``now``, which a test moves."""

    now: datetime = START

    def __call__(self) -> datetime:
        return self.now


def release_cf() -> FakeCf:
    return FakeCf(
        {
            PROVIDER_DIR: PROVIDER,
            OTHER_DIR: OTHER_PROVIDER,
            SOURCE_CONSUMER_DIR: SOURCE_CONSUMER,
            RELEASE_CONSUMER_DIR: RELEASE_CONSUMER,
            NOT_IN_PROGRAM_DIR: NOT_IN_PROGRAM_ID,
            NOT_A_PROJECT_DIR: CfAnswer.NOT_A_PROJECT,
            CF_DOWN_DIR: CfAnswer.FAILS,
        }
    )


def release_deps(
    tmp_path: Path,
    clock: SettableClock,
    *,
    cf: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    names: ProjectNames | CfCallFailed | None = None,
) -> Deps:
    """``Deps`` with the release ``cf``, the given clock and the given names."""
    base = status_deps(
        tmp_path,
        cf=cf or release_cf(),
        runs=[],
        names={} if names is None else names,
    )
    return replace(base, clock=clock)


def seed_pairs(store: Store) -> None:
    """On top of ``seed_members``: ``OTHER_PROVIDER`` provides to ``PROVIDER``, which
    provides to a ``from_source`` and a ``from_release`` consumer."""
    extra = (SOURCE_CONSUMER, RELEASE_CONSUMER)
    with store.write() as transaction:
        for member in extra:
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
        for provider, consumer, consumed in (
            (OTHER_PROVIDER, PROVIDER, ConsumedMode.FROM_SOURCE),
            (PROVIDER, SOURCE_CONSUMER, ConsumedMode.FROM_SOURCE),
            (PROVIDER, RELEASE_CONSUMER, ConsumedMode.FROM_RELEASE),
        ):
            insert_pair(
                transaction,
                program_id=PROGRAM,
                provider_id=provider,
                consumer_id=consumer,
                consumed=consumed,
                registered_at=START,
                updated_at=START,
            )


def release_rows(store: Store) -> list[tuple[object, ...]]:
    """Every row of ``releases``, oldest first."""
    with store.read() as transaction:
        return transaction.execute("SELECT * FROM releases ORDER BY seq").fetchall()


def database_dump(store: Store) -> list[str]:
    """The whole database as SQL text, schema and rows, from a second connection, for
    before/after comparisons. ``iterdump`` writes the statements, so no table name is
    put into SQL here."""
    with closing(sqlite3.connect(store.path)) as connection:
        return list(connection.iterdump())
