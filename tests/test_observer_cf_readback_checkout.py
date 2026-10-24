"""The read-back runs in the entry's checkout and checks the slice index.

The comparison runs against the real worktree-form ``cf get --json`` capture
(``tests/fixtures/cf/cf_get_worktree.json``, see the fixtures README); the
subprocess boundary is an injected runner that records how it was called.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest

from amoeba.process.observers.cf_readback import (
    RESULT_FILE_SLICE,
    RESULT_PROJECT_PATH,
    RESULT_UPDATED_AT,
    RESULT_VERSION_LABEL,
    RESULT_WORKTREE_ID,
    read_back_cf_write,
)
from amoeba.process.recovery import Adopt, NotApplied, Unknown
from amoeba.store import (
    PARAM_CHECKOUT,
    PARAM_EXPECTED_SLICE_INDEX,
    CommandKind,
    JournalEntry,
)
from amoeba.upstream.context_forge import parse_slice_stem

FIXTURE = Path(__file__).parent / "fixtures" / "cf" / "cf_get_worktree.json"
CHECKOUT = "/work/amoeba"
TIMEOUT_SECONDS = 10.0


def _record() -> dict[str, object]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast("dict[str, object]", payload)


def _fixture_index() -> int:
    file_slice = _record()["fileSlice"]
    assert isinstance(file_slice, str)
    stem = parse_slice_stem(file_slice)
    assert stem is not None
    return stem.index


def _entry(**parameters: object) -> JournalEntry:
    return JournalEntry(
        id="entry-1",
        project_id="demo",
        node_id="node-1",
        kind=CommandKind.CF_WRITE,
        parameters={"project": "amoeba", "expected": {}, **parameters},
    )


class RecordingRun:
    """An injected ``cf`` runner: replies with one record, remembers its calls."""

    def __init__(self, record: Mapping[str, object]) -> None:
        self._stdout = json.dumps(record)
        self.calls: list[dict[str, object]] = []

    def __call__(
        self, args: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(dict(kwargs))
        return subprocess.CompletedProcess(list(args), 0, self._stdout, "")


def _read_back(entry: JournalEntry, run: RecordingRun) -> object:
    return read_back_cf_write(entry, run, TIMEOUT_SECONDS)


def test_a_matching_index_adopts_with_the_checkout_identity() -> None:
    record = _record()
    run = RecordingRun(record)
    entry = _entry(
        **{PARAM_CHECKOUT: CHECKOUT, PARAM_EXPECTED_SLICE_INDEX: _fixture_index()}
    )

    observation = _read_back(entry, run)

    assert isinstance(observation, Adopt)
    worktree = cast("dict[str, object]", record["worktree"])
    assert observation.result == {
        RESULT_UPDATED_AT: record["updatedAt"],
        RESULT_FILE_SLICE: record["fileSlice"],
        RESULT_WORKTREE_ID: worktree["id"],
        RESULT_PROJECT_PATH: record["projectPath"],
    }


def test_the_version_label_is_recorded_only_when_a_label_is_supplied() -> None:
    entry = _entry(
        **{PARAM_CHECKOUT: CHECKOUT, PARAM_EXPECTED_SLICE_INDEX: _fixture_index()}
    )

    observation = read_back_cf_write(
        entry, RecordingRun(_record()), TIMEOUT_SECONDS, lambda: "label-1"
    )

    assert isinstance(observation, Adopt)
    assert observation.result[RESULT_VERSION_LABEL] == "label-1"


def test_another_index_is_not_applied() -> None:
    run = RecordingRun(_record())
    entry = _entry(
        **{PARAM_CHECKOUT: CHECKOUT, PARAM_EXPECTED_SLICE_INDEX: _fixture_index() + 1}
    )

    assert isinstance(_read_back(entry, run), NotApplied)


def test_a_record_without_file_slice_is_unknown() -> None:
    record = _record()
    del record["fileSlice"]
    entry = _entry(
        **{PARAM_CHECKOUT: CHECKOUT, PARAM_EXPECTED_SLICE_INDEX: _fixture_index()}
    )

    assert isinstance(_read_back(entry, RecordingRun(record)), Unknown)


def test_a_file_slice_that_does_not_parse_is_unknown() -> None:
    record = {**_record(), "fileSlice": "125-tasks.not-a-slice"}
    entry = _entry(
        **{PARAM_CHECKOUT: CHECKOUT, PARAM_EXPECTED_SLICE_INDEX: _fixture_index()}
    )

    assert isinstance(_read_back(entry, RecordingRun(record)), Unknown)


@pytest.mark.parametrize("bad_index", ["125", True, 1.5])
def test_an_expected_index_that_is_not_an_integer_is_unknown(bad_index: object) -> None:
    run = RecordingRun(_record())
    entry = _entry(**{PARAM_CHECKOUT: CHECKOUT, PARAM_EXPECTED_SLICE_INDEX: bad_index})

    assert isinstance(_read_back(entry, run), Unknown)
    assert run.calls == []


def test_an_entry_that_expects_nothing_is_unknown_without_reading() -> None:
    run = RecordingRun(_record())

    assert isinstance(_read_back(_entry(**{PARAM_CHECKOUT: CHECKOUT}), run), Unknown)
    assert run.calls == []


def test_the_read_runs_in_the_checkout() -> None:
    run = RecordingRun(_record())
    entry = _entry(
        **{PARAM_CHECKOUT: CHECKOUT, PARAM_EXPECTED_SLICE_INDEX: _fixture_index()}
    )

    _read_back(entry, run)

    assert [call["cwd"] for call in run.calls] == [CHECKOUT]


def test_an_entry_from_before_the_checkout_key_reads_without_a_working_directory() -> (
    None
):
    record = _record()
    run = RecordingRun(record)
    entry = _entry(expected={"developmentPhase": record["developmentPhase"]})

    assert isinstance(_read_back(entry, run), Adopt)
    assert "cwd" not in run.calls[0]
