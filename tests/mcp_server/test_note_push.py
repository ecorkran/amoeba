"""241's push check reports a note the way it reports a request (slice 243, push).

A fixture member has a baseline; a direct note, a program note and a release note
(through ``report_release``) reach it by the real operations; the tick's reply
and ``channel_event`` then finds one event whose entries name
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
from operations.release_placed import report_release
from operations.release_support import (
    PROVIDER_DIR,
    SettableClock,
    note_rows,
    release_deps,
)
from store.message_support import PROGRAM
from store.release_support import FULL_HASH, PROVIDER, seed_checkout
from store.seed import insert_member, insert_pair
from store_open import open_local_store
from user_configs import user_config

from amoeba.mcp.channel_event import channel_event
from amoeba.operations.release_notes import RELEASE_NOTE_ID_PREFIX
from amoeba.operations.report_release_models import ReportOutcome
from amoeba.operations.steps.dispatch import StepEdges, run_step
from amoeba.operations.steps.models_session import SessionTickReply
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode, DeliveryEvent, MessageKind
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
            seed_checkout(transaction, PROVIDER)
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

    def tick(last_seen: int | None) -> SessionTickReply:
        reply = run_step(
            "session_tick",
            store,
            {
                "here": {"project_id": RECIPIENT},
                "session_id": "b" * 32,
                "client": "claude-code",
                "directory": "/work",
                "last_seen": last_seen,
                "push_confirmed": False,
            },
            StepEdges(lambda: START, user_config),
        )
        assert isinstance(reply, SessionTickReply)
        return reply

    baseline = tick(None).high_seq
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

    reply = tick(baseline)
    assert reply.high_seq > baseline
    rows = reply.entries
    event = channel_event(rows, count=reply.count, last_seq=reply.high_seq)

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
