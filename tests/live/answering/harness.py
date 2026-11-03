"""Harness for the live answering tests (slice 140, Task 9): runs and passage text."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from live_settings import LiveSettings

from amoeba.runner.answering.inputs import QuestionInput, prepare_scratch
from amoeba.runner.answering.pipeline_file import (
    CHECK_MODEL_PARAM,
    answering_pipeline_path,
)

SQ_RUN_TIMEOUT_SECONDS = 600
CF_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class AnsweringRun:
    """One finished ``sq run`` of the answering pipeline."""

    directory: Path
    completed: subprocess.CompletedProcess[str]


@dataclass(frozen=True)
class LiveHarness:
    """Creates scratch directories under the registered parent and runs in them."""

    parent: Path
    environ: dict[str, str]
    settings: LiveSettings

    def run(
        self,
        name: str,
        question: QuestionInput,
        passages_markdown: str,
        *,
        check_model: str | None = None,
    ) -> AnsweringRun:
        directory = self.parent / name
        directory.mkdir()
        prepare_scratch(
            directory, question, passages_markdown, self.settings.max_cost_usd
        )
        argv = [
            "sq",
            "run",
            str(answering_pipeline_path()),
            self.settings.answer_model,
            "-p",
            f"{CHECK_MODEL_PARAM}={check_model or self.settings.check_model}",
        ]
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            argv,
            cwd=directory,
            env=self.environ,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=SQ_RUN_TIMEOUT_SECONDS,
            check=False,
        )
        return AnsweringRun(directory=directory, completed=completed)


def passage(  # noqa: PLR0913 - one argument per line of the D3 format
    number: int,
    kind: str,
    date: str,
    text: str,
    *,
    source: str | None = None,
    question: str | None = None,
    slice_label: str | None = None,
) -> str:
    """One ``passages.md`` section in the D3 format (hand-written for the tests)."""
    header = [("kind", kind), ("source", source), ("date", date)]
    header += [("question", question), ("slice", slice_label)]
    lines = [f"## Passage P{number}", ""]
    lines += [f"{key}: {value}" for key, value in header if value is not None]
    lines += ["", text, ""]
    return "\n".join(lines) + "\n"
