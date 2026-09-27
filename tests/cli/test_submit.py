"""``amoeba submit`` and the inbox listings, driven as real subprocesses.

The generic listing tests in ``test_cli_inspect.py`` already run every
registered listing stopped and running, in both forms. This module covers
what is specific to this slice: each ``submit`` subcommand, its refusals, and
the behavior of the three new listings.
"""

from __future__ import annotations

import argparse
import json
import time
from enum import StrEnum
from pathlib import Path

import pytest
from cli_harness import await_running, run_cli, start_background
from pydantic import BaseModel

from amoeba.cli.main import ExitCode
from amoeba.cli.submit import (
    _takes_text,  # pyright: ignore[reportPrivateUsage]
    add_payload_flags,
    payload_from,
    subcommand_name,
)
from amoeba.inbox import layout
from amoeba.store import BlockedKind, NodeKind, Store, SubmissionKind

PROJECT = "demo"

#: How long a running process may take to drain a handful of files.
DRAIN_TIMEOUT_SECONDS = 20.0


@pytest.fixture
def supervisor_dir(tmp_path: Path) -> Path:
    """A throwaway supervisor directory that exists. Never the real one."""
    directory = tmp_path / "supervisor"
    directory.mkdir()
    return directory


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    """An empty Squadron runs directory. Never the real one."""
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory


def _new_files(supervisor_dir: Path) -> list[Path]:
    return layout.submission_files(layout.new_dir(supervisor_dir))


def _submit_arguments(kind: SubmissionKind, *flags: str) -> list[str]:
    return [
        "submit",
        subcommand_name(kind),
        "--project",
        PROJECT,
        "--by",
        "cli",
        *flags,
    ]


def _listing(supervisor_dir: Path, *arguments: str) -> list[dict[str, object]]:
    result = run_cli(["inspect", *arguments, "--json"], supervisor_dir)
    assert result.returncode == ExitCode.OK, result.stderr
    rows: list[dict[str, object]] = json.loads(result.stdout)
    return rows


# --------------------------------------------------------------------------
# submit
# --------------------------------------------------------------------------

#: Each kind's payload flags, as the CLI derives them from the payload models.
KIND_FLAGS: dict[SubmissionKind, tuple[str, ...]] = {
    SubmissionKind.CREATE_PROJECT: (),
    SubmissionKind.RESOLUTION: ("--blocked-state-id", "b-1", "--detail", "go"),
    SubmissionKind.INTENT: ("--body", '{"want": "a run"}', "--node-id", "n-1"),
    SubmissionKind.VERDICT: (
        "--node-id",
        "n-1",
        "--verdict",
        "concerns",
        "--derivation",
        "stated",
        "--fallback-used",
        "null",
        "--findings-parsed",
        "true",
        "--provider-failure",
        "false",
        "--review-type",
        "tasks",
        "--model",
        "demo-model",
        "--findings",
        '[{"severity": "CONCERN", "summary": "x", "location": "a.py:3"}]',
        "--upstream",
        "squadron",
        "--upstream-version",
        "0.14.0",
        "--source",
        "artifact_frontmatter",
    ),
}


def test_every_kind_has_a_subcommand() -> None:
    assert set(KIND_FLAGS) == set(SubmissionKind)


@pytest.mark.parametrize("kind", list(SubmissionKind))
def test_submit_prints_the_id_of_the_file_it_wrote(
    supervisor_dir: Path, kind: SubmissionKind
) -> None:
    result = run_cli(_submit_arguments(kind, *KIND_FLAGS[kind]), supervisor_dir)

    assert result.returncode == ExitCode.OK, result.stderr
    submission_id = result.stdout.strip()
    [written] = _new_files(supervisor_dir)
    assert written.name.endswith(f"-{submission_id}{layout.SUBMISSION_SUFFIX}")
    assert json.loads(written.read_text())["kind"] == kind.value


def test_a_supplied_id_is_used(supervisor_dir: Path) -> None:
    arguments = _submit_arguments(SubmissionKind.CREATE_PROJECT, "--id", "retry-1")

    assert run_cli(arguments, supervisor_dir).stdout.strip() == "retry-1"


@pytest.mark.parametrize(
    "arguments",
    [
        ["submit", "create-project", "--project", "a/b", "--by", "cli"],
        ["submit", "create-project", "--project", "..", "--by", "cli"],
        [
            "submit",
            "create-project",
            "--project",
            PROJECT,
            "--by",
            "cli",
            "--id",
            "../x",
        ],
    ],
)
def test_an_invalid_submission_is_refused_and_writes_nothing(
    supervisor_dir: Path, arguments: list[str]
) -> None:
    result = run_cli(arguments, supervisor_dir)

    assert result.returncode == ExitCode.SUBMISSION_REFUSED
    assert "amoeba:" in result.stderr
    assert _new_files(supervisor_dir) == []


@pytest.mark.parametrize(
    "arguments",
    [
        _submit_arguments(SubmissionKind.INTENT, "--body", "not json"),
        _submit_arguments(SubmissionKind.INTENT, "--body", "[1, 2]"),
        _submit_arguments(SubmissionKind.RESOLUTION, "--detail", "missing target"),
    ],
)
def test_a_malformed_payload_is_a_usage_error_and_writes_nothing(
    supervisor_dir: Path, arguments: list[str]
) -> None:
    result = run_cli(arguments, supervisor_dir)

    assert result.returncode != ExitCode.OK
    assert _new_files(supervisor_dir) == []


def test_submit_works_while_the_process_is_running(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    process = start_background(
        supervisor_dir, ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.05"]
    )
    try:
        await_running(supervisor_dir)
        result = run_cli(
            _submit_arguments(SubmissionKind.CREATE_PROJECT), supervisor_dir
        )
        assert result.returncode == ExitCode.OK, result.stderr
    finally:
        run_cli(["stop"], supervisor_dir)
        process.cleanup()


# --------------------------------------------------------------------------
# The listings
# --------------------------------------------------------------------------


def test_messages_filter_by_channel(supervisor_dir: Path) -> None:
    with Store.open(supervisor_dir / f"{PROJECT}.sqlite3") as store:
        node = store.create_node(project_id=PROJECT, kind=NodeKind.SLICE, title="n")
        store.block(node.id, kind=BlockedKind.HUMAN, context="decide")

    escalations = _listing(
        supervisor_dir, "messages", "--project", PROJECT, "--channel", "escalation"
    )
    intents = _listing(
        supervisor_dir, "messages", "--project", PROJECT, "--channel", "intent"
    )
    every = _listing(supervisor_dir, "messages", "--project", PROJECT)

    assert [row["channel"] for row in escalations] == ["escalation"]
    assert intents == []
    assert every == escalations


def test_submissions_list_in_applied_order(
    supervisor_dir: Path, runs_dir: Path
) -> None:
    ids = [
        run_cli(
            _submit_arguments(SubmissionKind.CREATE_PROJECT, "--id", f"s-{index}"),
            supervisor_dir,
        ).stdout.strip()
        for index in range(3)
    ]
    process = start_background(
        supervisor_dir, ["--sq-runs-dir", str(runs_dir), "--idle-interval", "0.05"]
    )
    try:
        await_running(supervisor_dir)
        # Readable while the writer runs, and drained by it — within a bound.
        deadline = time.monotonic() + DRAIN_TIMEOUT_SECONDS
        while _listing(supervisor_dir, "inbox"):
            assert time.monotonic() < deadline, "the inbox never drained"
            time.sleep(0.05)
        running = _listing(supervisor_dir, "submissions", "--project", PROJECT)
    finally:
        run_cli(["stop"], supervisor_dir)
        process.wait()
        process.cleanup()

    stopped = _listing(supervisor_dir, "submissions", "--project", PROJECT)
    assert [row["id"] for row in stopped] == ids
    assert stopped == running
    sequence = [
        value for row in stopped if isinstance(value := row["applied_seq"], int)
    ]
    assert len(sequence) == len(stopped)
    assert sequence == sorted(sequence)


def test_the_inbox_listing_shows_each_state(supervisor_dir: Path) -> None:
    for index in range(3):
        run_cli(
            _submit_arguments(SubmissionKind.CREATE_PROJECT, "--id", f"s-{index}"),
            supervisor_dir,
        )
    [to_quarantine, to_fail, _] = _new_files(supervisor_dir)
    for path, directory in (
        (to_quarantine, layout.quarantine_dir(supervisor_dir)),
        (to_fail, layout.failed_dir(supervisor_dir)),
    ):
        directory.mkdir(parents=True)
        path.replace(directory / path.name)

    rows = _listing(supervisor_dir, "inbox")

    assert sorted(str(row["state"]) for row in rows) == sorted(
        [layout.NEW_DIR_NAME, layout.QUARANTINE_DIR_NAME, layout.FAILED_DIR_NAME]
    )
    # Sidecar-less files are reported, not crashed on.
    assert all(row["problem"] for row in rows if row["state"] != layout.NEW_DIR_NAME)


# --------------------------------------------------------------------------
# the flag rule
# --------------------------------------------------------------------------


class _Color(StrEnum):
    RED = "red"


@pytest.mark.parametrize(
    ("annotation", "takes_text"),
    [
        (str, True),
        (str | None, True),
        (_Color, True),
        (_Color | None, True),
        (bool | None, False),
        (bool, False),
        (float | None, False),
        (int | None, False),
        (list[str], False),
        (dict[str, object], False),
    ],
)
def test_the_flag_rule_by_annotation(annotation: object, takes_text: bool) -> None:
    assert _takes_text(annotation) is takes_text


class _RulePayload(BaseModel):
    name: str
    color: _Color
    flag: bool | None
    score: float | None = None
    items: list[str] = []


def _parse(*flags: str) -> dict[str, object]:
    parser = argparse.ArgumentParser(exit_on_error=False)
    add_payload_flags(parser, _RulePayload)
    return payload_from(parser.parse_args(list(flags)), _RulePayload)


def test_json_flags_build_null_false_and_lists() -> None:
    payload = _parse(
        "--name", "n", "--color", "red", "--flag", "null", "--items", '["a", "b"]'
    )
    assert payload == {
        "name": "n",
        "color": "red",
        "flag": None,
        "score": None,
        "items": ["a", "b"],
    }
    assert _RulePayload.model_validate(payload).flag is None

    typed = _parse("--name", "n", "--color", "red", "--flag", "false", "--score", "8.5")
    assert (typed["flag"], typed["score"]) == (False, 8.5)


def test_text_flags_are_taken_as_typed() -> None:
    assert _parse("--name", "null", "--color", "red", "--flag", "true")["name"] == (
        "null"
    )


def test_bad_json_on_a_json_flag_names_the_flag() -> None:
    with pytest.raises(argparse.ArgumentError, match="--flag"):
        _parse("--name", "n", "--color", "red", "--flag", "nope")
