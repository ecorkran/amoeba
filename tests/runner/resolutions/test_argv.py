"""The resume command line: flags, and instructions as one element."""

from __future__ import annotations

import pytest

from amoeba.process import SQ_EXECUTABLE
from amoeba.runner.resolutions.argv import (
    DECISION_FLAG,
    INSTRUCTIONS_FLAG,
    RESUME_FLAG,
    resume_argv,
)
from amoeba.runner.resolutions.vocabulary import Continuation


@pytest.mark.parametrize("decision", [Continuation.RETRY, Continuation.ACCEPT])
def test_without_instructions(decision: Continuation) -> None:
    assert resume_argv("run-1", decision, None) == [
        SQ_EXECUTABLE,
        "run",
        RESUME_FLAG,
        "run-1",
        DECISION_FLAG,
        decision.value,
    ]


def test_with_instructions_they_are_the_last_element() -> None:
    argv = resume_argv("run-1", Continuation.RETRY, "narrow it")

    assert argv[-2:] == [INSTRUCTIONS_FLAG, "narrow it"]


@pytest.mark.parametrize(
    "text",
    [
        "two  spaces",
        "say \"hi\" and 'bye'",
        "line one\nline two\r\n",
        "é ünïcode 日本語 🚀",
        "$(rm -rf /); `x` | & > <",
        "--decision accept",
        " leading and trailing ",
    ],
)
def test_instructions_are_one_element_byte_for_byte(text: str) -> None:
    argv = resume_argv("run-1", Continuation.ACCEPT, text)

    assert argv.count(text) == 1 and argv[-1] == text
    assert len(argv) == 8


def test_a_resume_names_no_pipeline_param_or_run_id_flag() -> None:
    argv = resume_argv("run-1", Continuation.RETRY, "x")

    assert "-p" not in argv and "--run-id" not in argv
    assert argv[:3] == [SQ_EXECUTABLE, "run", RESUME_FLAG]


def test_observe_is_refused() -> None:
    with pytest.raises(ValueError, match="no resume command"):
        resume_argv("run-1", Continuation.OBSERVE, None)
