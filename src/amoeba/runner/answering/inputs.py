"""The input contract: what Amoeba writes before the pipeline runs (D3, D7)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from amoeba.runner.answering.pipeline_file import (
    PASSAGES_FILE,
    QUESTION_FILE,
    RULES_DIRECTORY,
    SQUADRON_CONFIG_FILE,
)


@dataclass(frozen=True)
class QuestionInput:
    """The question and the slice it was asked about (``<index> <name>``)."""

    slice_label: str
    question: str


def render_question(question: QuestionInput) -> str:
    """The exact ``question.md`` content of D3. The question text is verbatim.

    Raises:
        ValueError: For an empty slice label or an empty question.
    """
    if not question.slice_label:
        raise ValueError("slice_label must not be empty")
    if not question.question:
        raise ValueError("question must not be empty")
    return f"# Question\n\nslice: {question.slice_label}\n\n{question.question}"


def render_squadron_config(directory: Path, max_cost_usd: float) -> str:
    """The ``.squadron.toml`` of D7: a per-run cost cap and an empty rules directory."""
    rules_dir = directory.resolve() / RULES_DIRECTORY
    # A JSON string is a valid TOML basic string, so quoting and escapes stay correct.
    return (
        f'"pipeline.max_cost_usd" = {max_cost_usd!r}\n'
        f"rules_dir = {json.dumps(str(rules_dir))}\n"
    )


def prepare_scratch(
    directory: Path,
    question: QuestionInput,
    passages_markdown: str,
    max_cost_usd: float,
) -> None:
    """Write the four scratch entries of D7 into an existing, empty directory.

    Raises:
        ValueError: Misuse (a programming error): the directory is absent or not
            empty, the cost cap is not positive, or the passages are empty.
    """
    if not directory.is_dir():
        raise ValueError(f"scratch directory does not exist: {directory}")
    if any(directory.iterdir()):
        raise ValueError(f"scratch directory is not empty: {directory}")
    if max_cost_usd <= 0:
        raise ValueError(f"max_cost_usd must be positive, got {max_cost_usd}")
    if not passages_markdown:
        raise ValueError("passages_markdown must not be empty")
    question_text = render_question(question)  # validates before anything is written
    (directory / QUESTION_FILE).write_text(question_text, encoding="utf-8")
    # Bytes, so no newline translation touches the passages.
    (directory / PASSAGES_FILE).write_bytes(passages_markdown.encode("utf-8"))
    (directory / RULES_DIRECTORY).mkdir()
    (directory / SQUADRON_CONFIG_FILE).write_text(
        render_squadron_config(directory, max_cost_usd), encoding="utf-8"
    )
