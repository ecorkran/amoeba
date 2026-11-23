"""Every way a request ends gets its held question started by the next operation
(slice 242, D7, 6.5), through the real ``amoeba`` script.

Three checkouts in one program and a routing ``cf``, as 240's scenario tests. The
held question is written straight into the store (no real pipeline pauses here); what
is checked is that the operation after the request's end records a start for it and
starts a detached ``handle-pause`` whose logs land in ``logs/request-release/``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from release_child_wait import child_finished, wait_until
from store_open import open_local_store

from amoeba.config.home import logs_dir, store_path
from amoeba.store.held_questions import HeldQuestion, insert_held
from amoeba.store.models import QuestionKey
from amoeba.store.questions import get_question
from amoeba.store.row_values import encode_timestamp
from cli.cli_support import write_config
from cli.requests_support import Repos

REQUEST_ID = "hold-1"
HELD = QuestionKey("held-run", "2026-11-10T11:00:00+00:00")
#: How long the test waits for the detached child's calls-log line, so no child is
#: left writing into a removed home.


@pytest.fixture
def repos(tmp_path: Path) -> Repos:
    write_config()
    found = Repos(tmp_path)
    for project in found.projects:
        found.run(project, "add", "--program", "demo")
    found.run(
        found.squadron, "send", "--id", REQUEST_ID, "--to", "context-forge",
        "--subject", "Need X", "--body", "Please add X",
    )  # fmt: skip
    with open_local_store(store_path()) as store, store.write() as transaction:
        held = HeldQuestion(HELD, found.squadron.id, "q", str(found.squadron.path))
        assert insert_held(transaction, held, REQUEST_ID, datetime.now(UTC))
    return found


def _start_attempted(key: QuestionKey) -> datetime | None:
    with open_local_store(store_path()) as store, store.read() as transaction:
        row = get_question(transaction, key)
    assert row is not None
    return row.start_attempted_at


def _wait_for_child() -> None:
    """The child's stdout log, and its calls-log line once it has exited."""
    wait_until(
        lambda: child_finished(HELD.run_id),
        lambda: f"no finished handle-pause child for {HELD.run_id} under {logs_dir()}",
    )


def _reply_done(repos: Repos) -> None:
    repos.run(repos.forge, "reply", REQUEST_ID, "accept")
    repos.run(repos.forge, "reply", REQUEST_ID, "done", "--text", "X is in")


def _cancel(repos: Repos) -> None:
    repos.run(repos.squadron, "cancel", REQUEST_ID)


def _remove_addressee(repos: Repos) -> None:
    repos.run(repos.forge, "rm")


ENDINGS: dict[str, Callable[[Repos], None]] = {
    "reply": _reply_done,
    "cancel": _cancel,
    "rm": _remove_addressee,
}


@pytest.mark.parametrize("ending", sorted(ENDINGS))
def test_the_operation_that_ends_the_request_starts_its_held_question(
    repos: Repos, ending: str
) -> None:
    assert _start_attempted(HELD) is None

    ENDINGS[ending](repos)

    assert _start_attempted(HELD) is not None
    _wait_for_child()


def test_an_expired_request_is_started_by_the_next_send(repos: Repos) -> None:
    """``send`` here, not ``list``: ``list`` first closes this test's held row as
    ``run_gone``, because no real Squadron run stands behind it."""
    past = encode_timestamp(datetime.now(UTC) - timedelta(hours=1))
    with open_local_store(store_path()) as store, store.write() as transaction:
        transaction.execute(
            "UPDATE messages SET expires_at = ? WHERE message_id = ?",
            (past, REQUEST_ID),
        )

    repos.run(
        repos.guide, "send", "--id", "another", "--to", "squadron",
        "--subject", "s", "--body", "b",
    )  # fmt: skip

    assert _start_attempted(HELD) is not None
    _wait_for_child()


def test_inbox_starts_nothing(repos: Repos) -> None:
    _reply_done(repos)
    with open_local_store(store_path()) as store, store.write() as transaction:
        transaction.execute("UPDATE questions SET start_attempted_at = NULL")
    _wait_for_child()

    repos.run(repos.squadron, "inbox")

    assert _start_attempted(HELD) is None
