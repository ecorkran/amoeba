"""``amoeba wake-run`` through ``main``: its exit codes and what it needs (244, D6)."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from operations.wake_run_support import (
    WAKE_ID,
    claimed_store,
    popen_failing_on_wait,
    probe_command,
    row_of,
)
from process_containment import contained_popen
from user_configs import example_config_text

from amoeba.cli import wake_command
from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK, EXIT_REJECTED
from amoeba.cli.main import main
from amoeba.config.home import config_path, store_path
from amoeba.operations.wake_run import run_wake
from amoeba.store.store import Store
from amoeba.store.vocabulary import WakeOutcome

SECRET_MARKER = "SECRET-MARKER-IN-A-COMMAND"
#: Far longer than any test command runs, so the deadline never decides a test.
CLAIM_TIMEOUT_SECONDS = 120.0


def _claim(tmp_path: Path, command: str) -> None:
    """A claimed row for ``command`` in the store ``main`` will open."""
    store_path().parent.mkdir(parents=True, exist_ok=True)
    # The CLI reads the real clock, so the row is claimed now with a roomy deadline.
    store, _ = claimed_store(
        tmp_path,
        command,
        database=store_path(),
        claimed_at=datetime.now(UTC),
        timeout_seconds=CLAIM_TIMEOUT_SECONDS,
    )
    store.close()


def _row() -> Any:
    with Store.open(store_path()) as store:
        return row_of(store)


def test_a_command_that_ran_exits_zero_and_the_row_is_ended(tmp_path: Path) -> None:
    _claim(tmp_path, probe_command(tmp_path, code=7))

    code = main(["wake-run", WAKE_ID])

    row = _row()
    assert code == EXIT_OK
    assert (row.outcome, row.exit_code) == (WakeOutcome.EXITED, 7)


def test_a_missing_executable_exits_one(tmp_path: Path) -> None:
    _claim(tmp_path, f"/nonexistent/{SECRET_MARKER}-agent")

    code = main(["wake-run", WAKE_ID])

    assert code == EXIT_REJECTED
    assert _row().outcome is WakeOutcome.START_FAILED


def test_a_wrapper_failure_exits_three_with_the_row_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    popen = popen_failing_on_wait("wrapper bug", contained_popen)
    monkeypatch.setattr(wake_command, "run_wake", partial(run_wake, popen=popen))
    _claim(tmp_path, probe_command(tmp_path, mode="sleep"))

    code = main(["wake-run", WAKE_ID])

    row = _row()
    assert code == EXIT_ERROR
    assert (row.outcome, row.detail) == (WakeOutcome.WRAPPER_FAILED, "RuntimeError")


def test_a_missing_row_exits_three_with_one_stderr_line_and_no_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _claim(tmp_path, probe_command(tmp_path))

    code = main(["wake-run", "no-such-wake"])

    lines = capsys.readouterr().err.splitlines()
    assert code == EXIT_ERROR
    assert len(lines) == 1
    assert lines[0].startswith("error: WakeRunError: ")
    assert not (tmp_path / "seen.json").exists()


def test_a_config_missing_the_new_keys_does_not_stop_the_wrapper(
    tmp_path: Path,
) -> None:
    text = "\n".join(
        line
        for line in example_config_text().splitlines()
        if not line.startswith(("wake_timeout_seconds", "max_wakes_per_day"))
    )
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(text + "\n", encoding="utf-8")
    _claim(tmp_path, probe_command(tmp_path))

    code = main(["wake-run", WAKE_ID])

    assert code == EXIT_OK
    assert _row().outcome is WakeOutcome.EXITED


def test_the_command_is_listed_in_help_as_internal(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])

    help_text = capsys.readouterr().out
    assert "wake-run" in help_text
    assert "internal" in help_text
