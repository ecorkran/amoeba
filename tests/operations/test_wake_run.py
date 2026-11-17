"""`run_wake`: the command, its environment, its end and each failure (244, D6)."""

from __future__ import annotations

import json
import logging
import os
import stat
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from process_containment import contained_popen
from store.message_support import NOW

from amoeba.operations import processes
from amoeba.operations.processes import WaitableChild
from amoeba.operations.wake_environment import WAKE_ENV_NAMES
from amoeba.operations.wake_run import WakeRunError, run_wake
from amoeba.store.errors import StoreBusyError, StoreCorruptError
from amoeba.store.store import Store
from amoeba.store.vocabulary import WakeOutcome
from amoeba.store.wakes import set_command_pid
from operations.message_support import message_deps
from operations.release_support import SettableClock
from operations.wake_run_support import (
    WAKE_ID,
    claimed_store,
    popen_failing_on_wait,
    probe_command,
    process_is_gone,
    stored_row,
    wait_until,
)

SECRET_MARKER = "SECRET-MARKER-IN-A-COMMAND"
#: A name macOS adds to every process it starts, whatever the parent passed.
OS_ADDED_NAMES = {"__CF_USER_TEXT_ENCODING"}


def _clock() -> SettableClock:
    clock = SettableClock()
    clock.now = NOW
    return clock


def _run(tmp_path: Path, command: str) -> WakeOutcome:
    store, _ = claimed_store(tmp_path, command)
    with store:
        return run_wake(
            store, message_deps(tmp_path, _clock()), WAKE_ID, popen=contained_popen
        )


def test_a_command_that_exits_zero_ends_exited_with_its_pid(tmp_path: Path) -> None:
    outcome = _run(tmp_path, probe_command(tmp_path, code=0))

    row = stored_row(tmp_path)
    assert outcome is WakeOutcome.EXITED
    assert (row.outcome, row.exit_code, row.detail) == (WakeOutcome.EXITED, 0, None)
    assert row.command_pid is not None
    assert row.ended_at == NOW


def test_a_non_zero_exit_is_data_not_a_wrapper_failure(tmp_path: Path) -> None:
    outcome = _run(tmp_path, probe_command(tmp_path, code=3))

    row = stored_row(tmp_path)
    assert outcome is WakeOutcome.EXITED
    assert (row.outcome, row.exit_code) == (WakeOutcome.EXITED, 3)


def test_a_command_past_the_deadline_is_stopped_with_its_whole_group(
    tmp_path: Path,
) -> None:
    outcome = _run(tmp_path, probe_command(tmp_path, mode="grandchild-sleep"))

    row = stored_row(tmp_path)
    assert outcome is WakeOutcome.TIMED_OUT
    assert (row.outcome, row.exit_code) == (WakeOutcome.TIMED_OUT, None)
    grandchild = int((tmp_path / "grandchild.pid").read_text(encoding="utf-8"))
    assert wait_until(lambda: process_is_gone(grandchild))


def test_after_a_normal_exit_a_member_left_in_the_group_gets_sigterm(
    tmp_path: Path,
) -> None:
    outcome = _run(tmp_path, probe_command(tmp_path, mode="grandchild"))

    assert outcome is WakeOutcome.EXITED
    grandchild = int((tmp_path / "grandchild.pid").read_text(encoding="utf-8"))
    assert wait_until(lambda: process_is_gone(grandchild))


def test_the_command_runs_in_the_rows_directory_with_only_the_wake_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SENDER_SECRET_MARKER", "sender-only-value")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "another-sender-value")

    _run(tmp_path, probe_command(tmp_path))

    seen = json.loads((tmp_path / "seen.json").read_text(encoding="utf-8"))
    assert Path(seen["cwd"]).resolve() == (tmp_path / "checkout").resolve()
    assert seen["stdin"] == ""
    environment: dict[str, str] = seen["env"]
    assert environment["AMOEBA_HOME"] == os.environ["AMOEBA_HOME"]
    # Only names the wrapper itself had can be judged: the interpreter may add its own.
    from_wrapper = set(environment) & set(os.environ) - OS_ADDED_NAMES
    assert from_wrapper <= set(WAKE_ENV_NAMES)
    assert "SENDER_SECRET_MARKER" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment


def test_a_missing_executable_ends_start_failed_without_the_file_name(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.DEBUG)

    outcome = _run(tmp_path, f"/nonexistent/{SECRET_MARKER}-agent --flag")

    row = stored_row(tmp_path)
    assert outcome is WakeOutcome.START_FAILED
    assert row.outcome is WakeOutcome.START_FAILED
    assert row.detail == "FileNotFoundError: No such file or directory"
    printed = caplog.text + capsys.readouterr().err
    assert SECRET_MARKER not in printed
    # The row holds the command it ran (D3); nothing else may carry the marker.
    assert SECRET_MARKER not in repr(replace(row, command=""))


def test_a_missing_directory_ends_start_failed(tmp_path: Path) -> None:
    store, _ = claimed_store(
        tmp_path, probe_command(tmp_path), directory=tmp_path / "gone"
    )
    with store:
        outcome = run_wake(
            store, message_deps(tmp_path, _clock()), WAKE_ID, popen=contained_popen
        )

    assert outcome is WakeOutcome.START_FAILED
    assert stored_row(tmp_path).detail == "FileNotFoundError: No such file or directory"


def test_a_file_that_is_not_executable_ends_start_failed(tmp_path: Path) -> None:
    plain = tmp_path / f"{SECRET_MARKER}-plain"
    plain.write_text("not a program", encoding="utf-8")
    plain.chmod(stat.S_IRUSR | stat.S_IWUSR)

    outcome = _run(tmp_path, str(plain))

    assert outcome is WakeOutcome.START_FAILED
    detail = stored_row(tmp_path).detail
    assert detail == "PermissionError: Permission denied"


def test_a_command_text_that_cannot_be_split_ends_start_failed(tmp_path: Path) -> None:
    outcome = _run(tmp_path, f"agent '{SECRET_MARKER}")

    row = stored_row(tmp_path)
    assert outcome is WakeOutcome.START_FAILED
    assert row.detail == "ValueError"


def test_a_missing_row_raises_with_no_command_run(tmp_path: Path) -> None:
    store, _ = claimed_store(tmp_path, probe_command(tmp_path))
    with store, pytest.raises(WakeRunError):
        run_wake(
            store,
            message_deps(tmp_path, _clock()),
            "no-such-wake",
            popen=contained_popen,
        )

    assert not (tmp_path / "seen.json").exists()


def test_an_ended_row_raises_with_no_command_run_and_no_row_change(
    tmp_path: Path,
) -> None:
    _run(tmp_path, f"/nonexistent/{SECRET_MARKER}")
    before = stored_row(tmp_path)

    with (
        Store.open(tmp_path / "amoeba.sqlite3") as reopened,
        pytest.raises(WakeRunError),
    ):
        run_wake(
            reopened, message_deps(tmp_path, _clock()), WAKE_ID, popen=contained_popen
        )

    assert stored_row(tmp_path) == before
    assert not (tmp_path / "seen.json").exists()


def test_a_store_that_cannot_be_read_raises_with_no_command_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _ = claimed_store(tmp_path, probe_command(tmp_path))

    def refuse() -> None:
        raise StoreBusyError("the store is held")

    monkeypatch.setattr(store, "read", refuse)
    with store, pytest.raises(StoreBusyError):
        run_wake(
            store, message_deps(tmp_path, _clock()), WAKE_ID, popen=contained_popen
        )

    assert not (tmp_path / "seen.json").exists()


def test_a_held_store_while_writing_the_pid_is_a_warning_and_the_wake_is_recorded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def held(*_: object) -> None:
        raise StoreBusyError("held")

    monkeypatch.setattr("amoeba.operations.wake_run.set_command_pid", held)
    caplog.set_level(logging.WARNING)

    outcome = _run(tmp_path, probe_command(tmp_path))

    row = stored_row(tmp_path)
    assert outcome is WakeOutcome.EXITED
    assert row.command_pid is None
    assert "could not record the command pid" in caplog.text


def _record_failures(caplog: pytest.LogCaptureFixture) -> int:
    """How many log records say the end of the wake could not be recorded."""
    return sum("could not record how" in record.message for record in caplog.records)


def _popen_that_raises(*_: Any, **__: Any) -> WaitableChild:
    raise RuntimeError(f"unexpected {SECRET_MARKER}")


class _WritesFail:
    """A store whose reads work and whose writes fail from the ``fail_from``-th."""

    def __init__(self, store: Store, fail_from: int) -> None:
        self._store = store
        self._writes = 0
        self._fail_from = fail_from

    def read(self) -> Any:
        return self._store.read()

    def write(self) -> Any:
        self._writes += 1
        if self._writes >= self._fail_from:
            raise StoreBusyError("held")
        return self._store.write()


def test_a_raise_after_the_start_records_wrapper_failed_and_stops_the_group(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store, _ = claimed_store(tmp_path, probe_command(tmp_path, mode="grandchild-sleep"))
    with store:
        outcome = run_wake(
            store,
            message_deps(tmp_path, _clock()),
            WAKE_ID,
            popen=popen_failing_on_wait(f"unexpected {SECRET_MARKER}", contained_popen),
        )

    row = stored_row(tmp_path)
    assert outcome is WakeOutcome.WRAPPER_FAILED
    assert (row.outcome, row.detail) == (WakeOutcome.WRAPPER_FAILED, "RuntimeError")
    assert SECRET_MARKER not in repr(replace(row, command=""))
    assert row.command_pid is not None
    assert wait_until(lambda: process_is_gone(row.command_pid or 0))
    assert "the wrapper failed" in caplog.text


def test_a_raise_before_the_start_records_start_failed(tmp_path: Path) -> None:
    store, _ = claimed_store(tmp_path, probe_command(tmp_path))
    with store:
        outcome = run_wake(
            store, message_deps(tmp_path, _clock()), WAKE_ID, popen=_popen_that_raises
        )

    row = stored_row(tmp_path)
    assert outcome is WakeOutcome.START_FAILED
    assert (row.outcome, row.detail) == (WakeOutcome.START_FAILED, "RuntimeError")
    assert not (tmp_path / "seen.json").exists()


def test_a_second_write_that_fails_leaves_the_row_unended_and_is_logged_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store, _ = claimed_store(tmp_path, probe_command(tmp_path))
    flaky = _WritesFail(store, fail_from=2)  # the pid write passes, the end fails
    caplog.set_level(logging.ERROR)

    with store, pytest.raises(StoreBusyError):
        run_wake(
            flaky,  # pyright: ignore[reportArgumentType]
            message_deps(tmp_path, _clock()),
            WAKE_ID,
            popen=contained_popen,
        )

    row = stored_row(tmp_path)
    assert (row.ended_at, row.outcome) == (None, None)
    assert row.command_pid is not None
    assert _record_failures(caplog) == 1


def test_a_failed_end_write_after_a_wrapper_error_is_also_raised_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store, _ = claimed_store(tmp_path, probe_command(tmp_path))
    flaky = _WritesFail(store, fail_from=1)
    caplog.set_level(logging.ERROR)

    with store, pytest.raises(StoreBusyError):
        run_wake(
            flaky,  # pyright: ignore[reportArgumentType]
            message_deps(tmp_path, _clock()),
            WAKE_ID,
            popen=_popen_that_raises,
        )

    assert stored_row(tmp_path).ended_at is None
    assert _record_failures(caplog) == 1


def test_a_store_error_after_the_start_stops_the_command_before_it_is_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A store that is broken (not merely held) while the pid is written cannot record
    the wake, but the command must not run on past its deadline with no wrapper."""

    def broken(*_: object) -> None:
        raise StoreCorruptError("the store is damaged")

    started: list[int] = []

    def recording_popen(*args: Any, **kwargs: Any) -> WaitableChild:
        child: WaitableChild = contained_popen(*args, **kwargs)
        started.append(child.pid)
        return child

    monkeypatch.setattr("amoeba.operations.wake_run.set_command_pid", broken)
    store, _ = claimed_store(tmp_path, probe_command(tmp_path, mode="sleep"))
    with store, pytest.raises(StoreCorruptError):
        run_wake(
            store, message_deps(tmp_path, _clock()), WAKE_ID, popen=recording_popen
        )

    row = stored_row(tmp_path)
    assert (row.ended_at, row.outcome) == (None, None)
    (pid,) = started
    assert wait_until(lambda: process_is_gone(pid))


def test_a_row_already_ended_by_another_writer_is_kept_and_a_warning_is_logged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def already_ended(*_args: object) -> bool:
        return False

    monkeypatch.setattr("amoeba.operations.wake_run.finish_wake", already_ended)
    caplog.set_level(logging.WARNING)

    outcome = _run(tmp_path, probe_command(tmp_path))

    assert outcome is WakeOutcome.EXITED
    assert "already recorded as ended" in caplog.text


def test_a_timeout_leaves_no_group_member_running_even_one_that_ignores_sigterm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The leader dies on SIGTERM at once; a member that ignores it must still be
    gone (by SIGKILL after the grace) once ``timed_out`` is recorded."""
    monkeypatch.setattr(processes, "TERMINATE_GRACE_SECONDS", 0.5)

    outcome = _run(tmp_path, probe_command(tmp_path, mode="stubborn"))

    assert outcome is WakeOutcome.TIMED_OUT
    stubborn = int((tmp_path / "grandchild.pid").read_text(encoding="utf-8"))
    assert wait_until(lambda: process_is_gone(stubborn))


def test_a_second_run_of_a_wake_that_already_has_a_command_runs_nothing(
    tmp_path: Path,
) -> None:
    store, _ = claimed_store(tmp_path, probe_command(tmp_path))
    with store, store.write() as transaction:
        set_command_pid(transaction, WAKE_ID, 4242)
    with (
        Store.open(tmp_path / "amoeba.sqlite3") as reopened,
        pytest.raises(WakeRunError, match="already has a command"),
    ):
        run_wake(
            reopened,
            message_deps(tmp_path, _clock()),
            WAKE_ID,
            popen=contained_popen,
        )

    assert not (tmp_path / "seen.json").exists()
    assert stored_row(tmp_path).command_pid == 4242


def test_a_run_that_loses_the_race_to_record_its_pid_stops_its_own_command(
    tmp_path: Path,
) -> None:
    """Two runs read the row unended; the other one records its pid first."""
    started: list[int] = []
    store, _ = claimed_store(tmp_path, probe_command(tmp_path, mode="sleep"))

    def racing_popen(*args: Any, **kwargs: Any) -> WaitableChild:
        child: WaitableChild = contained_popen(*args, **kwargs)
        started.append(child.pid)
        with Store.open(tmp_path / "amoeba.sqlite3") as other, other.write() as tx:
            set_command_pid(tx, WAKE_ID, 4242)
        return child

    with store, pytest.raises(WakeRunError, match="another run"):
        run_wake(store, message_deps(tmp_path, _clock()), WAKE_ID, popen=racing_popen)

    row = stored_row(tmp_path)
    assert (row.command_pid, row.ended_at) == (4242, None)
    (pid,) = started
    assert wait_until(lambda: process_is_gone(pid))
