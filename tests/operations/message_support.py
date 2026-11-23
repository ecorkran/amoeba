"""Shared by the request operation tests: members, a routing ``cf``, ``Deps`` and
readers of what the operations leave in the store (slice 240)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

from cf_fixtures import DEFAULT_WORKTREE, fixture_document
from store.message_support import NOW, seed_members
from store.seed import insert_checkout
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.deps import Deps
from amoeba.operations.message_results import SendResult
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import get_message
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import DeliveryEvent, RequestState
from operations.message_placed import send
from operations.release_support import SettableClock, release_deps
from operations.set_up_support import DIRECTORY, RECORDED_ID, RECORDED_NAME, FakeCf

#: Context Forge's ``projectPath`` for every project the stub ``cf`` knows.
CHECKOUT_PATH = Path(str(fixture_document(DEFAULT_WORKTREE)["projectPath"]))
#: The directory's own member, the usual sender.
SENDER = RECORDED_ID
SENDER_NAME = RECORDED_NAME
RECIPIENT = "recipient-project-id"
RECIPIENT_NAME = "recipient-project-name"
THIRD = "third-project-id"
THIRD_NAME = "third-project-name"
#: A project that is registered nowhere: no member by that id.
STRANGER = "stranger-project-id"


def message_cf(directory_fixture: str = DEFAULT_WORKTREE) -> FakeCf:
    """A ``cf`` that knows the three members by name, and answers a directory with
    ``directory_fixture``."""
    return FakeCf(
        directory_fixture=directory_fixture,
        projects=[(RECIPIENT, RECIPIENT_NAME), (THIRD, THIRD_NAME)],
    )


def message_deps(
    tmp_path: Path,
    clock: SettableClock,
    cf: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> Deps:
    return release_deps(tmp_path, clock, cf=cf or message_cf())


def seed_message_members(
    transaction: Transaction, *, extra: Sequence[str] = ()
) -> None:
    """The sender, the recipient and a third member in one program, each named and
    with a checkout on the ``local`` machine at the one path the stub ``cf`` gives
    every project; ``extra`` ids are members named by their ids with no checkout."""
    seed_members(
        transaction,
        SENDER,
        RECIPIENT,
        THIRD,
        *extra,
        names={SENDER: SENDER_NAME, RECIPIENT: RECIPIENT_NAME, THIRD: THIRD_NAME},
    )
    for member in (SENDER, RECIPIENT, THIRD):
        insert_checkout(
            transaction,
            member_id=member,
            cf_project_id=member,
            path=str(CHECKOUT_PATH),
            now=NOW,
        )


def open_message_store(tmp_path: Path) -> Iterator[Store]:
    """A store holding the sender, the recipient and a third member in one program."""
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_message_members(transaction)
        yield opened


def rejection_rows(store: Store) -> list[tuple[str, ...]]:
    """Every ``message_rejections`` row as ``(member, operation, to_ref, message_id,
    parent_id, code)``, oldest first; a null is the string ``-``."""
    with store.read() as transaction:
        rows = transaction.execute(
            "SELECT member_id, operation, to_ref, message_id, parent_id, code "
            "FROM message_rejections ORDER BY id"
        ).fetchall()
    return [
        tuple("-" if value is None else str(value) for value in row) for row in rows
    ]


def message_ids(store: Store) -> list[str]:
    with store.read() as transaction:
        return [
            str(row[0])
            for row in transaction.execute(
                "SELECT message_id FROM messages ORDER BY created_at, message_id"
            )
        ]


CONFIG = user_config()


def send_request_as_sender(
    store: Store, deps: Deps, request_id: str, **fields: object
) -> SendResult:
    """``send`` a request from ``SENDER``'s directory to ``RECIPIENT`` through the
    real operation, so its expiry follows the config."""
    document = {
        "id": request_id,
        "to": RECIPIENT_NAME,
        "subject": f"subject of {request_id}",
        "body": f"body of {request_id}",
        **fields,
    }
    return send(store, CONFIG, document, directory=DIRECTORY, deps=deps)


def send_note_as_sender(
    store: Store, deps: Deps, note_id: str, **fields: object
) -> SendResult:
    """``send`` a note from ``SENDER``'s directory to ``RECIPIENT`` (243), through the
    real operation. A field given as ``None`` is dropped, so ``to=None`` with a
    ``to_program`` sends a program note."""
    document: dict[str, object] = {
        "kind": "note",
        "id": note_id,
        "to": RECIPIENT_NAME,
        "subject": f"subject of {note_id}",
        "body": f"body of {note_id}",
        **fields,
    }
    clean = {key: value for key, value in document.items() if value is not None}
    return send(store, CONFIG, clean, directory=DIRECTORY, deps=deps)


def end_request(store: Store, request_id: str, state: RequestState, deps: Deps) -> None:
    """Move a stored request to the terminal ``state`` as the addressee would."""
    with store.write() as transaction:
        message = get_message(transaction, request_id)
        assert message is not None
        change_state(
            transaction,
            message,
            state,
            DeliveryEvent(state.value),
            RECIPIENT,
            deps.clock(),
            StateFields(),
        )
