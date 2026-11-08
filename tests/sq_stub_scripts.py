"""Ready-made run scripts for the stub ``sq`` (see ``sq_stub.write_run_script``).

Each builder returns a :class:`RunScript`: the files a run writes and the fields it
adds to its final outcome document. ``checkpoint`` and ``failure`` come from the real
captures in ``tests/fixtures/sq_outcomes/``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from amoeba.answering.pipeline_file import ANSWER_REPLY_FILE, CHECK_REPLY_FILE

SQ_OUTCOMES: Final = Path(__file__).parent / "fixtures" / "sq_outcomes"


@dataclass(frozen=True)
class RunScript:
    """What a run writes (``files``) and adds to its document (``document``)."""

    files: Mapping[str, str]
    document: Mapping[str, object]


def _captured(name: str, key: str) -> object:
    document = json.loads((SQ_OUTCOMES / name).read_text(encoding="utf-8"))
    return document[key]


def paused_checkpoint() -> RunScript:
    """The real ``awaits_human`` checkpoint."""
    checkpoint = _captured("paused_awaits_human.json", "checkpoint")
    return RunScript({}, {"checkpoint": checkpoint})


def failed_run() -> RunScript:
    """The real ``artifact_missing`` failure."""
    failure = _captured("failed_artifact_missing.json", "failure")
    return RunScript({}, {"failure": failure})


def agent_question_run(question: str) -> RunScript:
    """A run paused on the agent's own question (run it with outcome ``paused``).

    The real ``agent_question`` checkpoint, with ``question`` as the agent's text.
    """
    checkpoint = dict(
        _captured_checkpoint("composed_paused_agent_question.json"), question=question
    )
    return RunScript({}, {"checkpoint": checkpoint})


def _captured_checkpoint(name: str) -> dict[str, object]:
    checkpoint = _captured(name, "checkpoint")
    assert isinstance(checkpoint, dict)
    return dict(checkpoint)  # pyright: ignore[reportUnknownArgumentType]


def answering_run(
    answer: Mapping[str, object] | str | None,
    check: Mapping[str, object] | str | None = None,
    *,
    document: Mapping[str, object] | None = None,
) -> RunScript:
    """An answering run's reply files, for ``ANSWER_SCRIPT_ENV`` (slice 144, D13).

    ``answer`` and ``check`` are the content of ``answer.json`` and ``check.json``:
    a mapping is written as JSON, a string verbatim (for malformed text), and
    ``None`` writes no file. ``document`` adds fields to the final outcome document
    (a ``failure`` or ``checkpoint`` for a run that does not complete). The file
    names are 140's, imported from the answering package.
    """
    files: dict[str, str] = {}
    for name, content in ((ANSWER_REPLY_FILE, answer), (CHECK_REPLY_FILE, check)):
        if content is not None:
            files[name] = content if isinstance(content, str) else json.dumps(content)
    return RunScript(files, dict(document or {}))


def proposed_answer_reply(answer: str, cited: list[str]) -> dict[str, object]:
    """An ``answer.json`` that answers, citing ``cited``."""
    return {"kind": "answer", "answer": answer, "cited": cited}


def declining_answer_reply(reason: str) -> dict[str, object]:
    """An ``answer.json`` that declines."""
    return {"kind": "decline", "reason": reason}


def check_reply(verdict: str, reason: str | None = None) -> dict[str, object]:
    """A ``check.json``."""
    return {"verdict": verdict, "reason": reason}
