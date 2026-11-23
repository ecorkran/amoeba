"""The four message operations find members by name in the store, with a ``cf`` that
answers only the caller's directory (slice 261, D5, D6, D10)."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from cf_fixtures import DEFAULT_WORKTREE, OUTSIDE_ANY_PROJECT, replay
from store.message_support import NOW
from store.seed import insert_member
from store_open import open_local_store

from amoeba.operations.deps import Deps
from amoeba.operations.message_models import (
    CancelOutcome,
    InboxOutcome,
    ReplyOutcome,
    SendOutcome,
)
from amoeba.store.store import Store
from operations.message_placed import cancel, inbox, reply, send
from operations.message_support import (
    CONFIG,
    RECIPIENT,
    RECIPIENT_NAME,
    SENDER_NAME,
    message_deps,
    seed_message_members,
)
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY

#: A member whose Context Forge project does not exist anywhere, and has no checkout.
GHOST_ID = "ghost-member-id"
GHOST_NAME = "ghost-member-name"


class CallerOnlyCf:
    """Answers ``cf get --json`` for the directory and fails on anything else, so a
    lookup of another project by name or id would fail the test."""

    def __init__(self, fixture: str) -> None:
        self._fixture = fixture
        self.calls: list[list[str]] = []

    def __call__(
        self, argv: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        assert list(argv) == ["cf", "get", "--json"], argv
        return replay(argv, self._fixture)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_message_members(transaction)
            insert_member(
                transaction,
                project_id=GHOST_ID,
                program_id="demo",
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=NOW,
                updated_at=NOW,
                name=GHOST_NAME,
            )
        yield opened


def _deps(tmp_path: Path, fixture: str) -> tuple[Deps, CallerOnlyCf]:
    cf = CallerOnlyCf(fixture)
    return message_deps(tmp_path, SettableClock(), cf), cf


@pytest.mark.parametrize(
    "recipient", [RECIPIENT_NAME, RECIPIENT, GHOST_NAME, GHOST_ID], ids=str
)
def test_send_reaches_a_recipient_by_name_and_by_id_with_one_cf_call(
    store: Store, tmp_path: Path, recipient: str
) -> None:
    deps, cf = _deps(tmp_path, DEFAULT_WORKTREE)
    document = {"id": "ask", "to": recipient, "subject": "s", "body": "b"}

    result = send(store, CONFIG, document, directory=DIRECTORY, deps=deps)

    assert result.outcome is SendOutcome.SENT
    assert len(cf.calls) == 1


def test_inbox_finds_an_explicit_member_by_name(store: Store, tmp_path: Path) -> None:
    deps, cf = _deps(tmp_path, OUTSIDE_ANY_PROJECT)

    result = inbox(store, {"member": SENDER_NAME}, directory=DIRECTORY, deps=deps)

    assert result.outcome is InboxOutcome.LISTED
    assert len(cf.calls) == 1


def test_reply_and_cancel_find_an_explicit_member_by_name(
    store: Store, tmp_path: Path
) -> None:
    sender_deps, _ = _deps(tmp_path, DEFAULT_WORKTREE)
    outside_deps, cf = _deps(tmp_path, OUTSIDE_ANY_PROJECT)
    send(
        store,
        CONFIG,
        {"id": "ask", "to": RECIPIENT_NAME, "subject": "s", "body": "b"},
        directory=DIRECTORY,
        deps=sender_deps,
    )

    accepted = reply(
        store,
        CONFIG,
        {"id": "ask", "action": "accept", "member": RECIPIENT_NAME},
        directory=DIRECTORY,
        deps=outside_deps,
    )
    cancelled = cancel(
        store,
        CONFIG,
        {"id": "ask", "member": SENDER_NAME},
        directory=DIRECTORY,
        deps=outside_deps,
    )

    assert accepted.outcome is ReplyOutcome.APPLIED
    assert cancelled.outcome is CancelOutcome.CANCELLED
    assert len(cf.calls) == 2
