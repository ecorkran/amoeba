"""Harness for the live answering tests (slice 140, Task 9): runs and passage text."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from live_harness import PipelineRun, run_pipeline
from live_settings import LiveSettings

from amoeba.answering.inputs import QuestionInput, prepare_scratch
from amoeba.upstream.squadron.run_outcome import RunOutcome, RunOutcomeDocument

SQ_RUN_TIMEOUT_SECONDS = 600
CF_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class AnsweringRun:
    """One finished run of the answering pipeline, in its scratch directory."""

    directory: Path
    pipeline: PipelineRun

    @property
    def succeeded(self) -> bool:
        poll = self.pipeline.poll
        return isinstance(poll, RunOutcomeDocument) and (
            poll.outcome is RunOutcome.COMPLETED
        )

    @property
    def report(self) -> str:
        """What a failed assertion shows: the poll and the head of ``sq``'s output."""
        return f"{self.pipeline.poll}\n{self.pipeline.sq_output}"


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
        pipeline = run_pipeline(
            directory,
            self.settings.answer_model,
            check_model or self.settings.check_model,
            SQ_RUN_TIMEOUT_SECONDS,
            self.environ,
        )
        return AnsweringRun(directory=directory, pipeline=pipeline)


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
