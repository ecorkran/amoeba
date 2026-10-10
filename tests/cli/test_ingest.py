"""``amoeba ingest review`` as a real subprocess: every failure leaves the inbox empty.

A template supervisor directory with a real store file and a stopped process is
built once per module; each test works on its own copy, so nothing a test
submits is seen by the next.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from cli_harness import (
    CommandResult,
    await_condition,
    cli_environment,
    run_cli,
    start_running,
    stop_running,
    submit_cli,
)
from review_fixtures import (
    PR_REVIEW_116,
    ROUND_1_PART_1,
    ROUND_2_PART_1,
    SQ_REVIEWS,
    STAMPED_REVIEW_106,
)

from amoeba.cli.main import ExitCode
from amoeba.inbox import layout
from amoeba.upstream.squadron import parse_review_artifact, review_record_id

PROJECT = "demo"
NODE = "node-1"
PRE_STAMP_LABEL = "label-from-the-operator"
ARGUMENT_ERROR_STATUS = 2  # argparse's own usage-error status
DEMO_SCRIPT = Path(__file__).parents[2] / "scripts" / "demo_evidence.py"
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
    supervisor_dir: Path,
    *arguments: str,
    project: str = PROJECT,
    node: str = NODE,
) -> CommandResult:
    return run_cli(
        ["ingest", "review", "--project", project, "--node", node, "--by", "pm"]
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
    assert not (supervisor_dir / "nosuch.sqlite3").exists()


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


# --- The success path --------------------------------------------------------


def _digest(path: Path) -> str:
    return review_record_id(parse_review_artifact(path.read_text(encoding="utf-8")))


def _submission(supervisor_dir: Path) -> dict[str, object]:
    (file,) = new_files(supervisor_dir)
    submission: dict[str, object] = json.loads(file.read_text(encoding="utf-8"))
    return submission


def _seed_node(supervisor_dir: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(DEMO_SCRIPT)],
        capture_output=True,
        text=True,
        env=cli_environment(supervisor_dir),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_a_review_file_writes_one_submission_named_by_its_digest(
    supervisor_dir: Path,
) -> None:
    result = ingest(
        supervisor_dir,
        "--artifact",
        str(ROUND_1_PART_1),
        "--upstream-version",
        PRE_STAMP_LABEL,
    )
    assert result.returncode == ExitCode.OK, result.stderr
    assert result.stdout.strip() == _digest(ROUND_1_PART_1)
    assert len(new_files(supervisor_dir)) == 1
    assert NODE in result.stderr
    assert "resident-process-and-recovery" in result.stderr
    assert "tasks" in result.stderr


def test_a_stdout_capture_is_ingested(supervisor_dir: Path) -> None:
    capture = SQ_REVIEWS / "stdout-slice-104-concerns-glmflash.json"
    result = ingest(
        supervisor_dir,
        "--stdout-json",
        str(capture),
        "--upstream-version",
        PRE_STAMP_LABEL,
    )
    assert result.returncode == ExitCode.OK, result.stderr
    assert len(new_files(supervisor_dir)) == 1
    assert result.stdout.strip().startswith("sq-review-")
    payload = _submission(supervisor_dir)["payload"]
    assert isinstance(payload, dict)
    assert payload["source"] == "stdout_json"  # pyright: ignore[reportUnknownMemberType]


def test_a_node_that_differs_from_the_reviews_slice_is_accepted_and_shown(
    supervisor_dir: Path,
) -> None:
    node = _seed_node(supervisor_dir)
    parsed = parse_review_artifact(ROUND_2_PART_1.read_text(encoding="utf-8"))
    assert parsed.slice is not None and parsed.slice != node  # the precondition
    result = ingest(
        supervisor_dir,
        "--artifact",
        str(ROUND_2_PART_1),
        "--upstream-version",
        PRE_STAMP_LABEL,
        node=node,
    )
    assert result.returncode == ExitCode.OK, result.stderr
    assert len(new_files(supervisor_dir)) == 1
    assert node in result.stderr and parsed.slice in result.stderr


def test_a_review_with_no_slice_shows_a_dash(supervisor_dir: Path) -> None:
    result = ingest(
        supervisor_dir,
        "--artifact",
        str(PR_REVIEW_116),
        "--upstream-version",
        PRE_STAMP_LABEL,
    )
    assert result.returncode == ExitCode.OK, result.stderr
    assert "slice -," in result.stderr


def test_id_overrides_the_digest_and_is_the_submission_id(
    supervisor_dir: Path,
) -> None:
    result = ingest(
        supervisor_dir,
        "--artifact",
        str(ROUND_1_PART_1),
        "--upstream-version",
        PRE_STAMP_LABEL,
        "--id",
        "chosen-id",
    )
    assert result.returncode == ExitCode.OK, result.stderr
    assert result.stdout.strip() == "chosen-id"
    assert _submission(supervisor_dir)["id"] == "chosen-id"
