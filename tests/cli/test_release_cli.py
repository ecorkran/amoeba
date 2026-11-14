"""``amoeba report-release`` and ``changes``: documents, exits and ``-j`` (slice 227,
D5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from amoeba import wiring
from amoeba.cli import commands
from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE
from amoeba.cli.main import main
from amoeba.operations.changes_models import ChangesOutcome, ChangesResult, MemberRef
from amoeba.operations.names import Door, OperationName
from cli.cli_support import PROJECT_ID, result_of, run_amoeba, write_config

FULL_HASH = "ab12" * 10
SINCE = "2026-11-09T12:00:00+00:00"


def _registered(tmp_path: Path) -> None:
    write_config()
    assert run_amoeba(tmp_path, "add").returncode == EXIT_OK


def test_report_release_prints_the_result_document_with_touched_in_order(
    tmp_path: Path,
) -> None:
    _registered(tmp_path)

    completed = run_amoeba(
        tmp_path,
        "report-release",
        "--commit",
        FULL_HASH,
        "--changed",
        "what changed",
        "--touched",
        "second",
        "--touched",
        "first",
        as_json=True,
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    result = result_of(completed)
    assert result["outcome"] == "recorded"
    assert result["member"] == PROJECT_ID
    assert result["report"]["touched"] == ["second", "first"]
    assert result["report"]["commit"] == FULL_HASH


def test_report_release_text_says_reported(tmp_path: Path) -> None:
    _registered(tmp_path)

    completed = run_amoeba(
        tmp_path,
        "report-release",
        "--commit",
        FULL_HASH,
        "--changed",
        "text",
        "--touched",
        "item",
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    assert completed.stdout.splitlines()[0] == "reported"


def test_changes_lists_with_no_providers(tmp_path: Path) -> None:
    _registered(tmp_path)

    completed = run_amoeba(
        tmp_path, "changes", "--since", "2026-11-09T12:00:00+00:00", as_json=True
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    result = result_of(completed)
    assert result["outcome"] == "listed"
    assert result["pairs"] == []
    assert result["member"]["id"] == PROJECT_ID


def test_an_abbreviated_hash_is_rejected_as_malformed_with_exit_one(
    tmp_path: Path,
) -> None:
    _registered(tmp_path)

    completed = run_amoeba(
        tmp_path,
        "report-release",
        "--commit",
        FULL_HASH[:7],
        "--changed",
        "text",
        "--touched",
        "item",
        as_json=True,
    )

    assert completed.returncode == EXIT_REJECTED
    result = result_of(completed)
    assert result["outcome"] == "rejected"
    assert result["problems"][0]["code"] == "malformed"


def test_a_missing_flag_is_rejected_by_the_operation_not_by_argparse(
    tmp_path: Path,
) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, "changes", as_json=True)

    assert completed.returncode == EXIT_REJECTED
    assert result_of(completed)["problems"][0]["code"] == "malformed"


def test_correct_with_withdraw_is_a_usage_error(tmp_path: Path) -> None:
    completed = run_amoeba(
        tmp_path, "report-release", "--commit", FULL_HASH, "--correct", "--withdraw"
    )

    assert completed.returncode == EXIT_USAGE
    assert "not allowed with" in completed.stderr


@pytest.mark.parametrize(
    "arguments",
    [
        ("report-release", "--commit", FULL_HASH, "--changed", "t", "--touched", "i"),
        ("changes", "--since", SINCE),
    ],
    ids=["report-release", "changes"],
)
def test_a_failing_cf_exits_three(tmp_path: Path, arguments: tuple[str, ...]) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, *arguments, cf_fixture=None)

    assert completed.returncode == EXIT_ERROR


# --- what the flags put in the document -----------------------------------------


@pytest.fixture
def documents(monkeypatch: pytest.MonkeyPatch) -> list[tuple[OperationName, object]]:
    seen: list[tuple[OperationName, object]] = []

    def recording(
        name: OperationName, document: object, directory: Path | None, door: Door
    ) -> wiring.OperationResult:
        seen.append((name, document))
        return ChangesResult(
            outcome=ChangesOutcome.LISTED,
            member=MemberRef(id="member", name=None),
            since=SINCE,
            pairs=(),
            problems=(),
            warnings=(),
        )

    monkeypatch.setattr(commands, "invoke", recording)
    return seen


def _document_of(documents: list[tuple[OperationName, object]]) -> object:
    ((_, document),) = documents
    return document


def test_only_the_flags_given_reach_the_document(
    documents: list[tuple[OperationName, object]],
) -> None:
    assert main(["report-release", "--commit", FULL_HASH]) == EXIT_OK

    assert _document_of(documents) == {"commit": FULL_HASH}


def test_every_flag_reaches_the_document_and_touched_is_a_list(
    documents: list[tuple[OperationName, object]],
) -> None:
    arguments = [
        "report-release",
        "--commit",
        FULL_HASH,
        "--version",
        "tag-one",
        "--changed",
        "text",
        "--touched",
        "b",
        "--touched",
        "a",
    ]
    assert main(arguments) == EXIT_OK

    assert _document_of(documents) == {
        "commit": FULL_HASH,
        "version": "tag-one",
        "changed": "text",
        "touched": ["b", "a"],
    }


@pytest.mark.parametrize("flag", ["correct", "withdraw"])
def test_the_mode_flags_set_mode(
    documents: list[tuple[OperationName, object]], flag: str
) -> None:
    assert main(["report-release", "--commit", FULL_HASH, f"--{flag}"]) == EXIT_OK

    assert _document_of(documents) == {"mode": flag, "commit": FULL_HASH}


def test_changes_builds_since_when_given_and_nothing_otherwise(
    documents: list[tuple[OperationName, object]],
) -> None:
    assert main(["changes", "--since", SINCE]) == EXIT_OK
    assert main(["changes"]) == EXIT_OK

    assert [document for _, document in documents] == [{"since": SINCE}, {}]
