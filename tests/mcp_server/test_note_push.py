"""241's push check reports a note the way it reports a request (slice 243, push).

A fixture member has a baseline; a direct note, a program note and a release note
(through ``report_release``) reach it by the real operations; the push check (the
watcher's two reads and ``channel_event``) then finds one event whose entries name
``note``, ``sent`` and the sender's member id, and holds no subject, body or note id.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from operations.message_support import (
    RECIPIENT,
    SENDER,
    message_deps,
    seed_message_members,
    send_note_as_sender,
)
from operations.release_support import (
    PROVIDER_DIR,
    SettableClock,
    note_rows,
    release_deps,
)
from store.message_support import PROGRAM
from store.release_support import FULL_HASH, PROVIDER
from store.seed import insert_member, insert_pair
from store_open import open_local_store

from amoeba.mcp.channel_event import channel_event
from amoeba.operations.release_notes import RELEASE_NOTE_ID_PREFIX
from amoeba.operations.report_release import report_release
from amoeba.operations.report_release_models import ReportOutcome
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode, DeliveryEvent, MessageKind
from amoeba.wiring_presence import read_high_seq, read_push_rows
from mcp_server.presence_rig import START

#: Planted in the text of every note; must never reach the event.
MARKER = "MARKER-TEXT-9c"
DIRECT_ID = "push-direct-note"
PROGRAM_NOTE_ID = "push-program-note"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            seed_message_members(transaction)
            insert_member(
                transaction,
                project_id=PROVIDER,
                program_id=PROGRAM,
                rules_paths=(),
                authorize_allow=(),
                authorize_deny=(),
                registered_at=START,
                updated_at=START,
            )
            insert_pair(
                transaction,
                program_id=PROGRAM,
                provider_id=PROVIDER,
                consumer_id=RECIPIENT,
                consumed=ConsumedMode.FROM_SOURCE,
                registered_at=START,
                updated_at=START,
            )
        yield opened


def test_a_direct_note_a_program_note_and_a_release_note_make_one_event(
    store: Store, tmp_path: Path
) -> None:
    clock = SettableClock()
    send_deps = message_deps(tmp_path, clock)
    release_dependencies = release_deps(tmp_path, clock)

    def open_store() -> Store:
        return open_local_store(store.path)

    baseline = read_high_seq(open_store, RECIPIENT)
    direct = send_note_as_sender(
        store,
        send_deps,
        DIRECT_ID,
        subject=f"subject {MARKER}",
        body=f"body {MARKER}",
    )
    shared = send_note_as_sender(
        store,
        send_deps,
        PROGRAM_NOTE_ID,
        to=None,
        to_program=PROGRAM,
        subject=f"subject {MARKER}",
        body=f"body {MARKER}",
    )
    reported = report_release(
        store,
        {"commit": FULL_HASH, "changed": f"changed {MARKER}", "touched": [MARKER]},
        directory=PROVIDER_DIR,
        deps=release_dependencies,
    )
    assert direct.outcome.value == shared.outcome.value == "sent"
    assert reported.outcome is ReportOutcome.RECORDED

    assert read_high_seq(open_store, RECIPIENT) > baseline
    rows = read_push_rows(open_store, RECIPIENT, baseline)
    event = channel_event(rows)

    assert [(row.kind, row.event) for row in rows] == [
        (MessageKind.NOTE, DeliveryEvent.SENT)
    ] * 3
    assert [row.counterparty for row in rows] == [SENDER, SENDER, PROVIDER]
    content = event["content"]
    assert content.count(f"note, sent from {SENDER}") == 2
    assert content.count(f"note, sent from {PROVIDER}") == 1
    assert event["meta"] == {
        "first_seq": str(rows[0].seq),
        "last_seq": str(rows[-1].seq),
        "count": "3",
    }
    forbidden = [MARKER, DIRECT_ID, PROGRAM_NOTE_ID, RELEASE_NOTE_ID_PREFIX]
    forbidden += [row[0] for row in note_rows(store)]
    text = content + " ".join(event["meta"].values())
    assert not [word for word in forbidden if word in text]
