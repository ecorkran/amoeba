"""``amoeba ingest review`` as a real subprocess: every failure leaves the inbox empty.

A template supervisor directory with a real store file and a stopped process is
built once per module; each test works on its own copy, so nothing a test
submits is seen by the next.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest
from cli_harness import (
    CommandResult,
    await_condition,
    run_cli,
    start_running,
    stop_running,
    submit_cli,
)
from review_fixtures import (
    PR_REVIEW_116,
    ROUND_1_PART_1,
    SQ_REVIEWS,
    STAMPED_REVIEW_106,
)

from amoeba.cli.main import ExitCode
from amoeba.inbox import layout
from amoeba.store import paths

PROJECT = "demo"
NODE = "node-1"
PRE_STAMP_LABEL = "label-from-the-operator"
ARGUMENT_ERROR_STATUS = 2  # argparse's own usage-error status
INGEST_SOURCE = Path(__file__).parents[2] / "src" / "amoeba" / "cli" / "ingest.py"


@pytest.fixture(scope="module")
def template_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A stopped supervisor directory holding project ``demo``'s store file."""
    root = tmp_path_factory.mktemp("ingest-template")
    supervisor_dir = root / "supervisor"
    supervisor_dir.mkdir()
    runs_dir = root / "runs"
    runs_dir.mkdir()
    process = start_running(supervisor_dir, runs_dir)
    submit_cli(supervisor_dir, PROJECT, "create-project", "--by", "pm")
    store_file = supervisor_dir / f"{PROJECT}.sqlite3"
    await_condition(store_file.is_file, "the project store")
    stop_running(supervisor_dir, process)
    return supervisor_dir


@pytest.fixture
def supervisor_dir(template_dir: Path, tmp_path: Path) -> Path:
    """This test's own copy of the template. Never the real supervisor directory."""
    copy = tmp_path / "supervisor"
    shutil.copytree(template_dir, copy)
    return copy


def new_files(supervisor_dir: Path) -> list[Path]:
    return layout.submission_files(layout.new_dir(supervisor_dir))


def ingest(
    supervisor_dir: Path, *arguments: str, project: str = PROJECT
) -> CommandResult:
    return run_cli(
        ["ingest", "review", "--project", project, "--node", NODE, "--by", "pm"]
        + list(arguments),
        supervisor_dir,
    )


def test_the_exit_code_is_twelve_and_every_code_is_distinct() -> None:
    assert ExitCode.REVIEW_UNREADABLE == 12
    assert len(ExitCode.__members__) == len({code.value for code in ExitCode})


def test_the_template_has_a_store_and_nothing_pending(supervisor_dir: Path) -> None:
    assert (supervisor_dir / f"{PROJECT}.sqlite3").is_file()
    assert new_files(supervisor_dir) == []


def _assert_refused(
    result: CommandResult, supervisor_dir: Path, code: int, *words: str
) -> None:
    assert result.returncode == code, result.stderr
    for word in words:
        assert word in result.stderr, result.stderr
    assert new_files(supervisor_dir) == []


def test_a_missing_file_is_unreadable(supervisor_dir: Path, tmp_path: Path) -> None:
    missing = tmp_path / "no-such-review.md"
    result = ingest(supervisor_dir, "--artifact", str(missing))
    _assert_refused(
        result, supervisor_dir, ExitCode.REVIEW_UNREADABLE, "no-such-review"
    )


def test_a_file_that_is_not_utf8_is_unreadable(
    supervisor_dir: Path, tmp_path: Path
) -> None:
    binary = tmp_path / "binary.md"
    binary.write_bytes(b"\xff\xfe\x00 not text")
    result = ingest(supervisor_dir, "--artifact", str(binary))
    _assert_refused(result, supervisor_dir, ExitCode.REVIEW_UNREADABLE, "binary.md")


def test_text_without_frontmatter_is_unreadable(
    supervisor_dir: Path, tmp_path: Path
) -> None:
    note = tmp_path / "note.md"
    note.write_text("# not a review\n", encoding="utf-8")
    result = ingest(supervisor_dir, "--artifact", str(note))
    _assert_refused(
        result, supervisor_dir, ExitCode.REVIEW_UNREADABLE, "no frontmatter"
    )


def test_a_pre_stamp_file_without_a_version_label_is_unreadable(
    supervisor_dir: Path,
) -> None:
    result = ingest(supervisor_dir, "--artifact", str(ROUND_1_PART_1))
    _assert_refused(
        result, supervisor_dir, ExitCode.REVIEW_UNREADABLE, "no upstream version"
    )


def test_a_label_that_disagrees_with_the_stamp_is_unreadable(
    supervisor_dir: Path,
) -> None:
    result = ingest(
        supervisor_dir,
        "--artifact",
        str(STAMPED_REVIEW_106),
        "--upstream-version",
        PRE_STAMP_LABEL,
    )
    _assert_refused(
        result, supervisor_dir, ExitCode.REVIEW_UNREADABLE, "0.15.0", PRE_STAMP_LABEL
    )


def test_a_project_with_no_store_is_refused_before_anything_is_read(
    supervisor_dir: Path,
) -> None:
    result = ingest(
        supervisor_dir,
        "--artifact",
        str(supervisor_dir / "never-read.md"),
        project="nosuch",
    )
    _assert_refused(
        result, supervisor_dir, ExitCode.SUBMISSION_REFUSED, "no store", "nosuch"
    )
    assert not paths.store_path(
        "nosuch", {"AMOEBA_STORE_DIR": str(supervisor_dir)}
    ).exists()


def test_stdout_text_with_no_json_object_is_unreadable(
    supervisor_dir: Path, tmp_path: Path
) -> None:
    captured = tmp_path / "stdout.txt"
    captured.write_text("Error: the provider timed out\n", encoding="utf-8")
    result = ingest(supervisor_dir, "--stdout-json", str(captured))
    _assert_refused(
        result, supervisor_dir, ExitCode.REVIEW_UNREADABLE, "no JSON object"
    )


def test_a_json_error_body_with_no_verdict_is_unreadable(
    supervisor_dir: Path, tmp_path: Path
) -> None:
    captured = tmp_path / "stdout.json"
    captured.write_text('{"error": {"message": "rate limited"}}', encoding="utf-8")
    result = ingest(supervisor_dir, "--stdout-json", str(captured))
    _assert_refused(result, supervisor_dir, ExitCode.REVIEW_UNREADABLE, "verdict")


def test_both_source_flags_together_are_a_usage_error(supervisor_dir: Path) -> None:
    result = ingest(
        supervisor_dir,
        "--artifact",
        str(PR_REVIEW_116),
        "--stdout-json",
        str(SQ_REVIEWS / "stdout-slice-927-clean-pass.json"),
    )
    _assert_refused(result, supervisor_dir, ARGUMENT_ERROR_STATUS, "not allowed with")


def test_neither_source_flag_is_a_usage_error(supervisor_dir: Path) -> None:
    result = ingest(supervisor_dir)
    _assert_refused(result, supervisor_dir, ARGUMENT_ERROR_STATUS, "required")


def test_ingest_opens_no_store() -> None:
    """D6: the command checks a file exists and writes through the inbox only."""
    tree = ast.parse(INGEST_SOURCE.read_text(encoding="utf-8"))
    mentioned = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    mentioned |= {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom | ast.Import):
            mentioned.update(alias.name.split(".")[-1] for alias in node.names)
    assert "Store" not in mentioned
