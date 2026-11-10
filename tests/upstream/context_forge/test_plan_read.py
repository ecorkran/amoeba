"""The two plan reads run through a fake ``CfRun`` (slice 223, task 4.2)."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from cf_plan_run import plan_cf_run

from amoeba.upstream.context_forge.cli_call import CfRun
from amoeba.upstream.context_forge.plan import CFErrorDocument, CFSliceList
from amoeba.upstream.context_forge.plan_read import (
    read_initiatives,
    read_slice_list,
)
from amoeba.upstream.context_forge.target_read import ReadFailure

CHECKOUT = Path("/work/checkout")
TIMEOUT = 5.0


def _canned(returncode: int, stdout: str, stderr: str) -> CfRun:
    def run(argv: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(argv), returncode, stdout, stderr)

    return run


def test_initiatives_are_read_with_the_project_flag() -> None:
    run = plan_cf_run(integration_branch="", broken=False)

    result = read_initiatives(CHECKOUT, "pid", run, TIMEOUT)

    assert not isinstance(result, ReadFailure)
    assert [item.index for item in result][-1] == 220
    assert run.calls == [
        ["cf", "list", "initiatives", "--json", "-a", "-p", "pid"],
    ]


def test_a_failing_initiatives_call_is_a_read_failure() -> None:
    result = read_initiatives(CHECKOUT, "pid", _canned(1, "", "boom"), TIMEOUT)

    assert isinstance(result, ReadFailure)
    assert "boom" in result.detail


def test_unusable_initiatives_output_is_a_read_failure() -> None:
    result = read_initiatives(CHECKOUT, "pid", _canned(0, "{}", ""), TIMEOUT)

    assert isinstance(result, ReadFailure)


def test_a_slice_list_is_parsed() -> None:
    run = plan_cf_run(integration_branch="", broken=False)

    result = read_slice_list(CHECKOUT, "pid", 220, run, TIMEOUT)

    assert isinstance(result, CFSliceList)
    assert 223 in [entry.index for entry in result.entries]


def test_the_error_document_on_stderr_is_cfs_answer_not_a_failure() -> None:
    run = plan_cf_run(integration_branch="", broken=False)

    result = read_slice_list(CHECKOUT, "pid", 200, run, TIMEOUT)

    assert isinstance(result, CFErrorDocument)


def test_a_non_json_failure_is_a_read_failure() -> None:
    result = read_slice_list(CHECKOUT, "pid", 220, _canned(1, "", "boom"), TIMEOUT)

    assert isinstance(result, ReadFailure)
    assert "boom" in result.detail


def test_a_json_failure_that_is_not_the_error_document_is_a_read_failure() -> None:
    result = read_slice_list(
        CHECKOUT, "pid", 220, _canned(1, "", '{"entries": []}'), TIMEOUT
    )

    assert isinstance(result, ReadFailure)
