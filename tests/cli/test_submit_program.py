"""``amoeba submit register-program | register-member``, as real subprocesses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cli_harness import run_cli

from amoeba.cli.main import ExitCode
from amoeba.inbox import layout
from amoeba.store.paths import program_dir

MEMBERS = json.dumps(
    [
        {
            "project_id": "data",
            "requests_initiative": 790,
            "consumed": "from_source",
            "overrides": {},
        },
        {
            "project_id": "engine",
            "requests_initiative": 790,
            "consumed": "from_source",
            "overrides": {"data": "from_release"},
        },
    ]
)
MEMBER = json.dumps(
    {
        "project_id": "ui",
        "requests_initiative": 790,
        "consumed": "from_release",
        "overrides": {},
    }
)


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory that exists. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


def _program_files(supervisor_dir: Path) -> list[Path]:
    return layout.submission_files(layout.new_dir(program_dir(supervisor_dir)))


REGISTER_PROGRAM = [
    "submit",
    "register-program",
    "--by",
    "operator",
    "--program-id",
    "demo",
    "--concept-member",
    "data",
    "--concept-path",
    "docs/program-concept.md",
    "--members",
    MEMBERS,
]
REGISTER_MEMBER = [
    "submit",
    "register-member",
    "--by",
    "operator",
    "--program-id",
    "demo",
    "--member",
    MEMBER,
]


def test_register_program_prints_the_id_and_writes_a_program_file(
    supervisor_dir: Path,
) -> None:
    result = run_cli(REGISTER_PROGRAM, supervisor_dir)

    assert result.returncode == ExitCode.OK, result.stderr
    (landed,) = _program_files(supervisor_dir)
    assert landed.name.endswith(f"-{result.stdout.strip()}.json")
    assert not layout.inbox_dir(supervisor_dir).exists()


def test_register_member_prints_the_id_and_writes_a_program_file(
    supervisor_dir: Path,
) -> None:
    result = run_cli(REGISTER_MEMBER, supervisor_dir)

    assert result.returncode == ExitCode.OK, result.stderr
    assert len(_program_files(supervisor_dir)) == 1


def test_the_id_flag_reuses_an_id(supervisor_dir: Path) -> None:
    result = run_cli([*REGISTER_MEMBER, "--id", "retry-7"], supervisor_dir)

    assert result.stdout.strip() == "retry-7"


def test_a_missing_requests_initiative_is_refused_naming_the_field(
    supervisor_dir: Path,
) -> None:
    member = json.loads(MEMBER)
    del member["requests_initiative"]
    arguments = [*REGISTER_MEMBER[:-1], json.dumps(member)]

    result = run_cli(arguments, supervisor_dir)

    assert result.returncode == ExitCode.SUBMISSION_REFUSED
    assert "requests_initiative" in result.stderr
    assert _program_files(supervisor_dir) == []


def test_program_kinds_take_no_project_flag(supervisor_dir: Path) -> None:
    result = run_cli([*REGISTER_MEMBER, "--project", "demo"], supervisor_dir)

    assert result.returncode != ExitCode.OK
    assert "--project" in result.stderr
    assert _program_files(supervisor_dir) == []


def test_help_lists_both_subcommands(supervisor_dir: Path) -> None:
    result = run_cli(["submit", "--help"], supervisor_dir)

    assert result.returncode == ExitCode.OK
    assert "register-program" in result.stdout
    assert "register-member" in result.stdout
