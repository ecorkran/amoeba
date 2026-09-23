"""submit(): durability ordering, validation before writing, ids, and names.

The fsync order is asserted as a call sequence. Per the LLD this is the one
place a call-order assertion is the honest test: a unit test cannot simulate
power loss, and the contract claims no more than fsync-durability on POSIX.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from amoeba.inbox import (
    InvalidSubmissionError,
    SubmissionWriteError,
    durable,
    layout,
    submit,
)
from amoeba.store import QuarantineReason, SubmissionKind
from amoeba.store.inbox_models import INTENT_BODY
from amoeba.store.paths import STORE_FILE_SUFFIX


def _submit(store_dir: Path, **overrides: object) -> str:
    arguments: dict[str, object] = {
        "project_id": "demo",
        "kind": SubmissionKind.INTENT,
        "payload": {INTENT_BODY: {"want": "x"}},
        "submitted_by": "tester",
        "store_dir": store_dir,
    }
    arguments.update(overrides)
    return submit(**arguments)  # pyright: ignore[reportArgumentType]


def _files(directory: Path) -> list[Path]:
    return sorted(directory.iterdir()) if directory.is_dir() else []


def test_fsync_file_then_rename_then_fsync_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails if either fsync is removed or the order changes."""
    calls: list[str] = []
    real_fsync = os.fsync
    real_replace = Path.replace

    def recording_fsync(descriptor: int) -> None:
        is_directory = stat.S_ISDIR(os.fstat(descriptor).st_mode)
        calls.append("fsync-directory" if is_directory else "fsync-file")
        real_fsync(descriptor)

    def recording_replace(self: Path, target: Path) -> Path:
        calls.append("rename")
        return real_replace(self, target)

    monkeypatch.setattr(durable.os, "fsync", recording_fsync)
    monkeypatch.setattr(Path, "replace", recording_replace)

    _submit(tmp_path)

    assert calls == ["fsync-file", "rename", "fsync-directory"]


def test_the_file_lands_in_new_and_tmp_is_left_empty(tmp_path: Path) -> None:
    submission_id = _submit(tmp_path)

    [landed] = _files(layout.new_dir(tmp_path))
    assert landed.name.endswith(f"-{submission_id}{layout.SUBMISSION_SUFFIX}")
    assert _files(layout.tmp_dir(tmp_path)) == []


def test_the_filename_follows_the_layout_scheme(tmp_path: Path) -> None:
    submission_id = _submit(tmp_path)

    [landed] = _files(layout.new_dir(tmp_path))
    prefix = landed.name.split("-", 1)[0]
    assert prefix.isdigit()
    assert landed.name == layout.submission_filename(int(prefix), submission_id)


def test_a_supplied_id_is_returned(tmp_path: Path) -> None:
    assert _submit(tmp_path, submission_id="retry-me") == "retry-me"


def test_an_id_is_generated_when_none_is_supplied(tmp_path: Path) -> None:
    first = _submit(tmp_path)
    second = _submit(tmp_path)

    assert first != second
    assert len(first) == 32
    assert all(character in "0123456789abcdef" for character in first)


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"payload": {}}, QuarantineReason.INVALID_PAYLOAD),
        ({"project_id": ""}, QuarantineReason.INVALID_PROJECT_ID),
        ({"project_id": "a/b"}, QuarantineReason.INVALID_PROJECT_ID),
        ({"project_id": "."}, QuarantineReason.INVALID_PROJECT_ID),
        ({"project_id": ".."}, QuarantineReason.INVALID_PROJECT_ID),
        ({"submission_id": "../escape"}, QuarantineReason.UNPARSEABLE_ENVELOPE),
    ],
)
def test_invalid_input_raises_and_writes_nothing(
    tmp_path: Path, overrides: dict[str, object], reason: QuarantineReason
) -> None:
    with pytest.raises(InvalidSubmissionError) as caught:
        _submit(tmp_path, **overrides)

    assert caught.value.reason is reason
    assert _files(layout.new_dir(tmp_path)) == []
    assert _files(layout.tmp_dir(tmp_path)) == []


def test_a_write_failure_raises_and_leaves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_fsync(descriptor: int) -> None:
        raise OSError("disk went away")

    monkeypatch.setattr(durable.os, "fsync", failing_fsync)

    with pytest.raises(SubmissionWriteError, match="disk went away"):
        _submit(tmp_path)

    assert _files(layout.new_dir(tmp_path)) == []
    assert _files(layout.tmp_dir(tmp_path)) == []


def test_submit_opens_no_store(tmp_path: Path) -> None:
    """Works with no process and no store; creates none either."""
    _submit(tmp_path)

    assert list(tmp_path.rglob(f"*{STORE_FILE_SUFFIX}")) == []
