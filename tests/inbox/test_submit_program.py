"""submit_program(): the same guarantees as submit(), into the program inbox."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from program_harness import member, member_payload, program_payload

from amoeba.inbox import InvalidSubmissionError, layout, submit_program
from amoeba.store import QuarantineReason
from amoeba.store.paths import STORE_DIR_ENV_VAR, program_dir
from amoeba.store.program_models import ProgramSubmissionKind


def _files(directory: Path) -> list[Path]:
    return sorted(directory.iterdir()) if directory.is_dir() else []


def _submit(supervisor_dir: Path, **overrides: object) -> str:
    arguments: dict[str, object] = {
        "kind": ProgramSubmissionKind.REGISTER_PROGRAM,
        "payload": program_payload(),
        "submitted_by": "tester",
        "store_dir": supervisor_dir,
    }
    arguments.update(overrides)
    return submit_program(**arguments)  # pyright: ignore[reportArgumentType]


def test_the_file_lands_in_the_program_inbox_and_nowhere_in_the_project_inbox(
    tmp_path: Path,
) -> None:
    identifier = _submit(tmp_path)

    (landed,) = _files(layout.new_dir(program_dir(tmp_path)))
    assert landed.name.endswith(f"-{identifier}.json")
    assert not layout.inbox_dir(tmp_path).exists()
    assert _files(layout.tmp_dir(program_dir(tmp_path))) == []


def test_the_file_holds_a_valid_envelope_with_no_project_id(tmp_path: Path) -> None:
    identifier = _submit(tmp_path)

    (landed,) = _files(layout.new_dir(program_dir(tmp_path)))
    data = json.loads(landed.read_text(encoding="utf-8"))
    assert data["id"] == identifier
    assert data["kind"] == "register_program"
    assert data["submitted_by"] == "tester"
    assert "project_id" not in data
    assert data["payload"]["members"][0]["consumed"] == "from_source"


def test_an_invalid_payload_writes_nothing(tmp_path: Path) -> None:
    bad = program_payload()
    del bad["concept_path"]

    with pytest.raises(InvalidSubmissionError) as caught:
        _submit(tmp_path, payload=bad)

    assert caught.value.reason is QuarantineReason.INVALID_PAYLOAD
    assert "concept_path" in caught.value.detail
    assert not program_dir(tmp_path).exists()


def test_a_supplied_id_is_reused(tmp_path: Path) -> None:
    first = _submit(tmp_path, submission_id="retry-1")
    second = _submit(tmp_path, submission_id="retry-1")

    assert first == second == "retry-1"


def test_register_member_is_accepted(tmp_path: Path) -> None:
    identifier = _submit(
        tmp_path,
        kind=ProgramSubmissionKind.REGISTER_MEMBER,
        payload=member_payload(member("ui")),
    )

    (landed,) = _files(layout.new_dir(program_dir(tmp_path)))
    assert landed.name.endswith(f"-{identifier}.json")


def test_the_supervisor_directory_resolves_as_for_submit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(STORE_DIR_ENV_VAR, str(tmp_path))

    submit_program(
        kind=ProgramSubmissionKind.REGISTER_PROGRAM,
        payload=program_payload(),
        submitted_by="tester",
    )

    assert len(_files(layout.new_dir(program_dir(tmp_path)))) == 1
