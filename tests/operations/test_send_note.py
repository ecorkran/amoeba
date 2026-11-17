"""``send`` of a note: recipients, resend, refusals and their records (slice 243, D1
to D3)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT
from store.message_support import PROGRAM, count, delivery_rows
from store.seed import insert_member
from user_configs import user_config

from amoeba.operations import note_room
from amoeba.operations.deps import Deps
from amoeba.operations.message_models import (
    MAX_BODY_LENGTH,
    MAX_ID_LENGTH,
    MAX_SUBJECT_LENGTH,
    SendOutcome,
)
from amoeba.operations.message_results import SendResult
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.send import send
from amoeba.store.messages import get_message
from amoeba.store.programs import remove_member
from amoeba.store.store import Store
from amoeba.store.vocabulary import MessageKind
from operations.message_support import (
    RECIPIENT,
    RECIPIENT_NAME,
    SENDER,
    SENDER_NAME,
    THIRD,
    message_cf,
    message_deps,
    message_ids,
    open_message_store,
    rejection_rows,
    send_request_as_sender,
)
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY

CONFIG = user_config()
RETENTION = timedelta(days=CONFIG.prune_after_days)
#: Not a member and not a program.
NOWHERE = "no-such-place"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from open_message_store(tmp_path)


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def deps(tmp_path: Path, clock: SettableClock) -> Deps:
    return message_deps(tmp_path, clock)


def _note(note_id: str = "news-1", **fields: Any) -> dict[str, Any]:
    return {
        "kind": "note",
        "id": note_id,
        "subject": f"subject of {note_id}",
        "body": f"body of {note_id}",
        **fields,
    }


def _send(store: Store, deps: Deps, document: object) -> SendResult:
    return send(store, CONFIG, document, directory=DIRECTORY, deps=deps)


def _deliveries(store: Store) -> list[tuple[str, str]]:
    """``(member, message)`` of every delivery, in ``seq`` order."""
    with store.read() as transaction:
        return [(row[1], row[2]) for row in delivery_rows(transaction)]


def test_a_direct_note_is_stored_and_delivered_to_the_addressee_only(
    store: Store, deps: Deps
) -> None:
    result = _send(store, deps, _note(to=RECIPIENT_NAME))

    assert result.outcome is SendOutcome.SENT
    assert result.request is None
    assert result.note is not None
    assert (result.note.from_member, result.note.to_member) == (SENDER, RECIPIENT)
    assert result.note.to_program is None
    assert _deliveries(store) == [(RECIPIENT, "news-1")]
    with store.read() as transaction:
        stored = get_message(transaction, "news-1")
    assert stored is not None
    assert stored.kind is MessageKind.NOTE and stored.state is None


def test_a_program_note_reaches_the_others_once_each_and_never_the_sender(
    store: Store, deps: Deps
) -> None:
    result = _send(store, deps, _note(to_program=PROGRAM))

    assert result.outcome is SendOutcome.SENT
    assert result.note is not None
    assert (result.note.to_member, result.note.to_program) == (None, PROGRAM)
    assert sorted(_deliveries(store)) == sorted(
        [(RECIPIENT, "news-1"), (THIRD, "news-1")]
    )
    assert count_rows(store) == 1


def count_rows(store: Store) -> int:
    with store.read() as transaction:
        return count(transaction, "messages")


def test_a_member_added_afterwards_gets_nothing(store: Store, deps: Deps) -> None:
    _send(store, deps, _note(to_program=PROGRAM))
    with store.write() as transaction:
        insert_member(
            transaction,
            project_id="late-joiner",
            program_id=PROGRAM,
            rules_paths=(),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=deps.clock(),
            updated_at=deps.clock(),
        )

    assert "late-joiner" not in {member for member, _ in _deliveries(store)}


def test_a_direct_note_to_the_senders_own_member_is_delivered(
    store: Store, deps: Deps
) -> None:
    result = _send(store, deps, _note(to=SENDER_NAME))

    assert result.outcome is SendOutcome.SENT
    assert _deliveries(store) == [(SENDER, "news-1")]


def _remove(store: Store, deps: Deps, *members: str) -> None:
    with store.write() as transaction:
        for member in members:
            remove_member(transaction, member, deps.clock())


def test_a_program_with_only_the_sender_is_refused_saying_so(
    store: Store, deps: Deps
) -> None:
    _remove(store, deps, RECIPIENT, THIRD)

    result = _send(store, deps, _note(to_program=PROGRAM))

    assert result.rejection is RejectCode.UNKNOWN_RECIPIENT
    assert "no one else" in result.problems[0]
    assert rejection_rows(store) == [
        (SENDER, "send", PROGRAM, "news-1", "-", "unknown_recipient")
    ]
    assert message_ids(store) == []


def test_an_unknown_program_is_refused_saying_so(store: Store, deps: Deps) -> None:
    result = _send(store, deps, _note(to_program=NOWHERE))

    assert result.rejection is RejectCode.UNKNOWN_RECIPIENT
    assert "unknown program" in result.problems[0]
    assert rejection_rows(store) == [
        (SENDER, "send", NOWHERE, "news-1", "-", "unknown_recipient")
    ]


def test_a_sender_at_the_note_cap_drops_its_oldest_note_to_send_another(
    store: Store, deps: Deps, clock: SettableClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(note_room, "MAX_NOTES_PER_SENDER", 3)
    for name in ("z1", "y2", "x3", "w4"):
        sent = _send(store, deps, _note(name, to=RECIPIENT_NAME))
        assert sent.outcome is SendOutcome.SENT
        clock.now += timedelta(seconds=1)

    assert sorted(message_ids(store)) == ["w4", "x3", "y2"]
    assert sorted(message for _member, message in _deliveries(store)) == [
        "w4",
        "x3",
        "y2",
    ]


def test_a_refused_or_repeated_note_at_the_cap_drops_nothing(
    store: Store, deps: Deps, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(note_room, "MAX_NOTES_PER_SENDER", 3)
    for name in ("a", "b", "c"):
        _send(store, deps, _note(name, to=RECIPIENT_NAME))

    refused = _send(store, deps, _note("d", to=NOWHERE))
    repeated = _send(store, deps, _note("c", to=RECIPIENT_NAME))

    assert refused.rejection is RejectCode.UNKNOWN_RECIPIENT
    assert repeated.outcome is SendOutcome.UNCHANGED
    assert sorted(message_ids(store)) == ["a", "b", "c"]


@pytest.mark.parametrize("recipient", ["removed", "unknown"])
def test_a_removed_or_unknown_recipient_is_refused(
    store: Store, deps: Deps, recipient: str
) -> None:
    if recipient == "removed":
        _remove(store, deps, RECIPIENT)
    name = RECIPIENT_NAME if recipient == "removed" else NOWHERE

    result = _send(store, deps, _note(to=name))

    assert result.rejection is RejectCode.UNKNOWN_RECIPIENT
    assert rejection_rows(store) == [
        (SENDER, "send", name, "news-1", "-", "unknown_recipient")
    ]
    assert message_ids(store) == []


@pytest.mark.parametrize(
    ("fields", "to_ref"),
    [
        ({"to": RECIPIENT_NAME, "parent": "p-1"}, RECIPIENT_NAME),
        ({"to": RECIPIENT_NAME, "to_program": PROGRAM}, RECIPIENT_NAME),
        ({}, "-"),
        (
            {"to": RECIPIENT_NAME, "subject": "s" * (MAX_SUBJECT_LENGTH + 1)},
            RECIPIENT_NAME,
        ),
        ({"to": RECIPIENT_NAME, "body": "b" * (MAX_BODY_LENGTH + 1)}, RECIPIENT_NAME),
        ({"to": RECIPIENT_NAME, "id": "i" * (MAX_ID_LENGTH + 1)}, RECIPIENT_NAME),
        ({"to_program": PROGRAM, "parent": "p-1"}, PROGRAM),
    ],
    ids=[
        "parent",
        "both recipients",
        "neither recipient",
        "subject over the limit",
        "body over the limit",
        "id over the limit",
        "program note with a parent",
    ],
)
def test_a_malformed_note_is_rejected_with_one_record_and_nothing_stored(
    store: Store, deps: Deps, fields: dict[str, Any], to_ref: str
) -> None:
    result = _send(store, deps, _note(**fields))

    assert result.rejection is RejectCode.MALFORMED
    assert message_ids(store) == []
    [row] = rejection_rows(store)
    assert row[:3] == (SENDER, "send", to_ref)
    assert row[5] == "malformed"


def test_a_request_with_to_program_is_rejected_naming_the_request(
    store: Store, deps: Deps
) -> None:
    document = _note(kind="request", to=RECIPIENT_NAME, to_program=PROGRAM)

    result = _send(store, deps, document)

    assert result.rejection is RejectCode.MALFORMED
    assert "request" in result.problems[0]
    assert len(rejection_rows(store)) == 1


def test_not_a_member_leaves_no_record(
    store: Store, tmp_path: Path, clock: SettableClock
) -> None:
    outside = message_deps(tmp_path, clock, message_cf(OUTSIDE_ANY_PROJECT))

    result = _send(store, outside, _note(to_program=PROGRAM))

    assert result.rejection is RejectCode.NOT_A_MEMBER
    assert rejection_rows(store) == []


def test_a_resend_with_equal_content_is_unchanged_and_writes_no_delivery(
    store: Store, deps: Deps
) -> None:
    first = _send(store, deps, _note(to_program=PROGRAM))
    before = _deliveries(store)

    again = _send(store, deps, _note(to_program=PROGRAM))

    assert again.outcome is SendOutcome.UNCHANGED
    assert again.note == first.note
    assert _deliveries(store) == before
    assert rejection_rows(store) == []


@pytest.mark.parametrize(
    "changed",
    [{"body": "a different body"}, {"subject": "a different subject"}],
    ids=["body", "subject"],
)
def test_a_changed_resend_is_id_reused(
    store: Store, deps: Deps, changed: dict[str, str]
) -> None:
    _send(store, deps, _note(to=RECIPIENT_NAME))

    result = _send(store, deps, _note(to=RECIPIENT_NAME, **changed))

    assert result.rejection is RejectCode.ID_REUSED
    assert _deliveries(store) == [(RECIPIENT, "news-1")]


def test_a_resend_to_another_member_is_id_reused(store: Store, deps: Deps) -> None:
    _send(store, deps, _note(to=RECIPIENT_NAME))

    result = _send(store, deps, _note(to=SENDER_NAME))

    assert result.rejection is RejectCode.ID_REUSED


def test_a_note_resent_as_a_program_note_is_id_reused(store: Store, deps: Deps) -> None:
    _send(store, deps, _note(to=RECIPIENT_NAME))

    result = _send(store, deps, _note(to_program=PROGRAM))

    assert result.rejection is RejectCode.ID_REUSED


def test_a_request_id_reused_for_a_note_is_id_reused(store: Store, deps: Deps) -> None:
    send_request_as_sender(store, deps, "shared-id")

    result = _send(store, deps, _note("shared-id", to=RECIPIENT_NAME))

    assert result.rejection is RejectCode.ID_REUSED
    assert len(rejection_rows(store)) == 1


def test_a_note_id_reused_for_a_request_is_id_reused(store: Store, deps: Deps) -> None:
    _send(store, deps, _note("shared-id", to=RECIPIENT_NAME))

    result = send_request_as_sender(store, deps, "shared-id")

    assert result.rejection is RejectCode.ID_REUSED


def test_an_id_pruned_and_sent_again_is_a_new_note(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    first = _send(store, deps, _note(to=RECIPIENT_NAME))
    clock.now += RETENTION + timedelta(days=1)

    again = _send(store, deps, _note(to=RECIPIENT_NAME))

    assert again.outcome is SendOutcome.SENT
    assert first.note is not None and again.note is not None
    assert again.note.created_at > first.note.created_at
    assert _deliveries(store) == [(RECIPIENT, "news-1")]


def test_an_id_starting_release_colon_is_malformed(store: Store, deps: Deps) -> None:
    result = _send(store, deps, _note("release:abc", to=RECIPIENT_NAME))

    assert result.rejection is RejectCode.MALFORMED
    assert message_ids(store) == []
