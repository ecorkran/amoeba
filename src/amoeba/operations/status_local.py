"""The sentences ``status``'s result adds (slice 261, D11): the ``file_problems`` and
sweep-problem text. Split from ``status`` to keep it under its size."""

from __future__ import annotations

from amoeba.operations.runs_document import RunsDocument, left_out_text


def file_problems(
    runs: RunsDocument, call_problems: tuple[str, ...], prune_problems: tuple[str, ...]
) -> tuple[str, ...]:
    """The call-log and prune problems, and the sentence for a cut document."""
    cut = left_out_text(runs.left_out)
    return (*call_problems, *(() if cut is None else (cut,)), *prune_problems)


def joined(*problems: str | None) -> str | None:
    """The sweep problems that happened, one text, or ``None`` when none did."""
    found = [problem for problem in problems if problem is not None]
    return "; ".join(found) if found else None
