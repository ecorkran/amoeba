"""The real detached child of the start trigger (slice 242, D7, 6.5).

The one non-live test that starts it for real: ``production_deps``' own
``amoeba_script`` and ``spawn``, the throwaway ``AMOEBA_HOME``, a routing ``cf`` and
the stub ``sq`` first on ``PATH``. ``wiring.invoke`` of ``reply`` marks the request
``done``; nothing calls ``handle_pause`` by hand. The stub ``sq`` knows no run, so the
child's ``handle-pause`` closes the held question as ``run_gone``: the question leaves
``waiting_on_request`` only because the child ran.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cf_routing import RoutedProject, write_routing_cf
from release_child_wait import child_finished, wait_until
from sq_stub import write_sq_stub
from user_configs import example_config_text

from amoeba import wiring
from amoeba.config.home import config_path, logs_dir, state_layout
from amoeba.operations.caller import find_member
from amoeba.operations.names import Door, OperationName
from amoeba.operations.work_start import HANDLE_PAUSE_LOG_DIRECTORY
from amoeba.store.held_questions import HeldQuestion, insert_held
from amoeba.store.models import QuestionKey, QuestionRecord
from amoeba.store.questions import get_question
from amoeba.store.vocabulary import QuestionState

SYSTEM_PATH = "/usr/bin:/bin"
REQUEST_ID = "child-request"
HELD = QuestionKey("child-held-run", "2026-11-10T11:00:00+00:00")


def _row() -> QuestionRecord:
    with wiring.open_store(state_layout()) as store, store.read() as transaction:
        row = get_question(transaction, HELD)
    assert row is not None
    return row


def test_reply_done_starts_a_real_child_that_moves_the_held_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sender, addressee = (
        RoutedProject(f"child-{name}-id", name, tmp_path / name)
        for name in ("asker", "replier")
    )
    for project in (sender, addressee):
        project.path.mkdir()
    bin_dir = tmp_path / "bin"
    write_routing_cf(bin_dir, [sender, addressee])
    write_sq_stub(bin_dir)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{SYSTEM_PATH}")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(example_config_text(), encoding="utf-8")
    for project in (sender, addressee):
        wiring.invoke(OperationName.ADD, {"program": "demo"}, project.path, Door.CLI)
    wiring.invoke(
        OperationName.SEND,
        {"id": REQUEST_ID, "to": addressee.name, "subject": "s", "body": "b"},
        sender.path,
        Door.CLI,
    )
    with wiring.open_store(state_layout()) as store, store.write() as transaction:
        asker = find_member(transaction, sender.name)
        assert asker is not None
        held = HeldQuestion(HELD, asker.project_id, "q", str(sender.path))
        assert insert_held(transaction, held, REQUEST_ID, datetime.now(UTC))
    wiring.invoke(
        OperationName.REPLY,
        {"id": REQUEST_ID, "action": "accept"},
        addressee.path,
        Door.CLI,
    )

    wiring.invoke(
        OperationName.REPLY,
        {"id": REQUEST_ID, "action": "done", "text": "it is in"},
        addressee.path,
        Door.CLI,
    )

    def left_the_hold() -> bool:
        return (
            child_finished(HELD.run_id)
            and _row().state is not QuestionState.WAITING_ON_REQUEST
        )

    def last_state() -> str:
        child_logs = (logs_dir() / HANDLE_PAUSE_LOG_DIRECTORY).glob("*.log")
        texts = {path.name: path.read_text() for path in child_logs}
        return f"row {_row().state}, child logs {texts}"

    wait_until(left_the_hold, last_state)
    row = _row()
    assert row.state is QuestionState.CLOSED
    assert row.start_attempted_at is not None
