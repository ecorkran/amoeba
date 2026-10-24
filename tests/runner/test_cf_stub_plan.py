"""The stub ``cf``'s plan reads: from a plan dir, numbered sequences, modes, log."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from cf_stub import LOG_ENV, MODE_ENV, PLAN_DIR_ENV, CfMode, write_cf_stub

from amoeba.upstream.context_forge import (
    CFErrorDocument,
    CFSliceList,
    parse_initiatives,
    parse_slice_list,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cf"
LINK = "cf-1"


@pytest.fixture
def plan_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "plan"
    directory.mkdir()
    bin_dir = write_cf_stub(tmp_path / "bin")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv(PLAN_DIR_ENV, str(directory))
    monkeypatch.setenv(LOG_ENV, str(tmp_path / "cf.log"))
    monkeypatch.delenv(MODE_ENV, raising=False)
    return directory


def _cf(*arguments: str, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["cf", *arguments, "--json", "-p", LINK],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _slice_list(*indexes: int) -> str:
    entries = [{"index": i, "name": f"s{i}", "isChecked": False} for i in indexes]
    return json.dumps({"entries": entries})


def test_initiatives_answer_from_the_plan_dir(plan_dir: Path) -> None:
    document = json.dumps([{"index": 7, "name": "seven", "isChecked": False}])
    (plan_dir / "initiatives.json").write_text(document)

    completed = _cf("list", "initiatives", "-a")

    assert completed.returncode == 0
    assert [entry.index for entry in parse_initiatives(completed.stdout)] == [7]


def test_initiatives_without_a_plan_file_answer_the_captured_fixture(
    plan_dir: Path,
) -> None:
    completed = _cf("list", "initiatives", "-a")

    assert completed.stdout == (FIXTURES / "list_initiatives_a.json").read_text()


def test_a_slice_list_answers_from_the_plan_dir(plan_dir: Path) -> None:
    (plan_dir / "slices-120.json").write_text(_slice_list(120, 121))

    completed = _cf("list", "slices", "120")

    parsed = parse_slice_list(completed.stdout)
    assert isinstance(parsed, CFSliceList)
    assert [entry.index for entry in parsed.entries] == [120, 121]


def test_a_missing_slice_file_prints_the_captured_error_document_and_exits_1(
    plan_dir: Path,
) -> None:
    completed = _cf("list", "slices", "140")

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == (FIXTURES / "list_slices_error.json").read_text()
    assert isinstance(parse_slice_list(completed.stderr), CFErrorDocument)


def test_numbered_files_answer_successive_calls_in_order(plan_dir: Path) -> None:
    (plan_dir / "slices-120.1.json").write_text(_slice_list(120))
    (plan_dir / "slices-120.2.json").write_text(_slice_list(120, 121))
    (plan_dir / "slices-120.10.json").write_text(_slice_list(120, 121, 122))

    counts: list[int] = []
    for _ in range(4):
        parsed = parse_slice_list(_cf("list", "slices", "120").stdout)
        assert isinstance(parsed, CFSliceList)
        counts.append(len(parsed.entries))

    assert counts == [1, 2, 3, 3], "numeric order, and the last answer repeats"


def test_numbered_sequences_are_per_index(plan_dir: Path) -> None:
    (plan_dir / "slices-120.1.json").write_text(_slice_list(120))
    (plan_dir / "slices-120.2.json").write_text(_slice_list(120, 121))
    (plan_dir / "slices-100.json").write_text(_slice_list(100))

    _cf("list", "slices", "120")
    other = parse_slice_list(_cf("list", "slices", "100").stdout)
    second = parse_slice_list(_cf("list", "slices", "120").stdout)

    assert isinstance(other, CFSliceList) and len(other.entries) == 1
    assert isinstance(second, CFSliceList) and len(second.entries) == 2


@pytest.mark.parametrize(
    ("mode", "returncode", "stdout_empty"),
    [(CfMode.FAIL, 1, True), (CfMode.EMPTY, 0, True)],
)
def test_a_failure_mode_applies_to_a_slice_read(
    plan_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: CfMode,
    returncode: int,
    stdout_empty: bool,
) -> None:
    (plan_dir / "slices-120.json").write_text(_slice_list(120))
    monkeypatch.setenv(MODE_ENV, mode.value)

    completed = _cf("list", "slices", "120")

    assert completed.returncode == returncode
    assert (completed.stdout == "") is stdout_empty


def test_the_wrong_form_mode_applies_to_a_slice_read(
    plan_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (plan_dir / "slices-120.json").write_text(_slice_list(120))
    monkeypatch.setenv(MODE_ENV, CfMode.WRONG_FORM.value)

    completed = _cf("list", "slices", "120")

    assert json.loads(completed.stdout) == []


def test_a_sleeping_stub_times_out_a_slice_read(
    plan_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(MODE_ENV, CfMode.SLEEP.value)

    with pytest.raises(subprocess.TimeoutExpired):
        _cf("list", "slices", "120", timeout=0.5)


def test_the_log_records_both_plan_commands(plan_dir: Path, tmp_path: Path) -> None:
    _cf("list", "initiatives", "-a")
    _cf("list", "slices", "120")

    assert (tmp_path / "cf.log").read_text().splitlines() == [
        f"list initiatives -a --json -p {LINK}",
        f"list slices 120 --json -p {LINK}",
    ]
