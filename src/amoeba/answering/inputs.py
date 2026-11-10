"""The input contract: what Amoeba writes before the pipeline runs (D3, D7)."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from amoeba.answering.pipeline_file import (
    NOT_AUTHORIZED_FILE,
    PASSAGES_FILE,
    QUESTION_FILE,
    RULES_DIRECTORY,
    SQUADRON_CONFIG_FILE,
)

_LINE_BREAKS = frozenset("\r\n")

#: What ``not_authorized.md`` says when the member has nothing barred (D11).
NO_ITEM_BARRED_TEXT: Final = "No item is barred for this repository."


class BarredItem(Protocol):
    """One thing answers may not authorize; the config's item satisfies it."""

    @property
    def key(self) -> str: ...

    @property
    def description(self) -> str: ...


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
    if not question.slice_label.strip() or _LINE_BREAKS & set(question.slice_label):
        raise ValueError("slice_label must be a non-blank single line")
    if not question.question.strip():
        raise ValueError("question must not be blank")
    return f"# Question\n\nslice: {question.slice_label}\n\n{question.question}"


def render_not_authorized(items: Sequence[BarredItem]) -> str:
    """The ``not_authorized.md`` content: one ``key: description`` bullet per item,
    or ``NO_ITEM_BARRED_TEXT`` when there is none."""
    if not items:
        return NO_ITEM_BARRED_TEXT
    return "\n".join(f"- {item.key}: {item.description}" for item in items)


def render_squadron_config(directory: Path, max_cost_usd: float) -> str:
    """The ``.squadron.toml`` of D7: a per-run cost cap and an empty rules directory.

    Raises:
        ValueError: When the cap is not a positive, finite number.
    """
    if not math.isfinite(max_cost_usd) or max_cost_usd <= 0:
        raise ValueError(f"max_cost_usd must be positive, got {max_cost_usd}")
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
    *,
    not_authorized: Sequence[BarredItem] = (),
) -> None:
    """Write the five scratch entries of D7 and D11 into an existing, empty directory.

    ``not_authorized`` defaults to none, which renders ``NO_ITEM_BARRED_TEXT``, so
    a caller that has no list still gives the pipeline the file it names.

    Raises:
        ValueError: Misuse (a programming error): the directory is absent or not
            empty, the cost cap is not positive, or the passages are empty.
    """
    if not directory.is_dir():
        raise ValueError(f"scratch directory does not exist: {directory}")
    if any(directory.iterdir()):
        raise ValueError(f"scratch directory is not empty: {directory}")
    if not passages_markdown:
        raise ValueError("passages_markdown must not be empty")
    # Both render before anything is written, so a bad input leaves no file.
    question_text = render_question(question)
    config_text = render_squadron_config(directory, max_cost_usd)
    (directory / QUESTION_FILE).write_text(question_text, encoding="utf-8")
    # Bytes, so no newline translation touches the passages.
    (directory / PASSAGES_FILE).write_bytes(passages_markdown.encode("utf-8"))
    (directory / NOT_AUTHORIZED_FILE).write_text(
        render_not_authorized(not_authorized), encoding="utf-8"
    )
    (directory / RULES_DIRECTORY).mkdir()
    (directory / SQUADRON_CONFIG_FILE).write_text(config_text, encoding="utf-8")
