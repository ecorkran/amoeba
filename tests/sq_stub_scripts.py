"""Ready-made run scripts for the stub ``sq`` (see ``sq_stub.write_run_script``).

Each builder returns a :class:`RunScript`: the review files a run writes and the
fields it adds to its final outcome document. Review text comes from the real
captures in ``tests/fixtures/sq_reviews/``; ``checkpoint`` and ``failure`` come
from the real captures in ``tests/fixtures/sq_outcomes/``. Only a review's
``slice`` frontmatter is rewritten, where a test needs a given slice.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from review_fixtures import PAIR_ARTIFACT, ROUND_2_PART_1, ROUND_2_PART_2

from amoeba.runner.answering.pipeline_file import ANSWER_REPLY_FILE, CHECK_REPLY_FILE

SQ_OUTCOMES: Final = Path(__file__).parent / "fixtures" / "sq_outcomes"

#: Where a run writes its reviews, relative to its working directory.
REVIEWS_DIR: Final = "project-documents/user/reviews"

#: A review the stub lists but does not write.
MISSING_REVIEW_PATH: Final = f"{REVIEWS_DIR}/999-review.slice.never-written.md"

_SLICE_LINE: Final = re.compile(r"^slice:.*$", re.MULTILINE)


@dataclass(frozen=True)
class RunScript:
    """What a run writes (``files``) and adds to its document (``document``)."""

    files: Mapping[str, str]
    document: Mapping[str, object]


def with_slice(text: str, slice_name: str | None) -> str:
    """``text`` with its first ``slice:`` frontmatter line set to ``slice_name``."""
    if slice_name is None:
        return text
    return _SLICE_LINE.sub(f"slice: {slice_name}", text, count=1)


def _review_entry(**fields: object) -> dict[str, object]:
    """A ``reviews`` entry as Squadron prints it; unset fields are ``null``."""
    entry: dict[str, object] = {
        "path": None,
        "paths": None,
        "template": "slice",
        "verdict": "CONCERNS",
        "step": "slices",
        "round": None,
    }
    entry.update(fields)
    return entry


def single_review(slice_name: str | None = None) -> RunScript:
    """One review file, listed by ``path`` with ``paths`` null."""
    path = f"{REVIEWS_DIR}/{PAIR_ARTIFACT.name}"
    text = with_slice(PAIR_ARTIFACT.read_text(encoding="utf-8"), slice_name)
    return RunScript({path: text}, {"reviews": [_review_entry(path=path)]})


def split_review(slice_name: str | None = None) -> RunScript:
    """A review split in two part files, listed by ``paths`` in part order."""
    parts = [
        f"{REVIEWS_DIR}/{source.name}" for source in (ROUND_2_PART_1, ROUND_2_PART_2)
    ]
    texts = [
        with_slice(source.read_text(encoding="utf-8"), slice_name)
        for source in (ROUND_2_PART_1, ROUND_2_PART_2)
    ]
    entry = _review_entry(path=parts[0], paths=parts, template="tasks")
    return RunScript(dict(zip(parts, texts, strict=True)), {"reviews": [entry]})


def null_path_review() -> RunScript:
    """An entry with neither ``path`` nor ``paths``: nothing to read."""
    return RunScript({}, {"reviews": [_review_entry()]})


def empty_reviews() -> RunScript:
    """A run that wrote no review."""
    return RunScript({}, {"reviews": []})


def missing_file_review() -> RunScript:
    """An entry whose listed file was never written."""
    entry = _review_entry(path=MISSING_REVIEW_PATH)
    return RunScript({}, {"reviews": [entry]})


def _captured(name: str, key: str) -> object:
    document = json.loads((SQ_OUTCOMES / name).read_text(encoding="utf-8"))
    return document[key]


def paused_checkpoint() -> RunScript:
    """The real ``awaits_human`` checkpoint, with no reviews."""
    checkpoint = _captured("paused_awaits_human.json", "checkpoint")
    return RunScript({}, {"checkpoint": checkpoint, "reviews": []})


def failed_run() -> RunScript:
    """The real ``artifact_missing`` failure, with no reviews."""
    failure = _captured("failed_artifact_missing.json", "failure")
    return RunScript({}, {"failure": failure, "reviews": []})


def agent_question_run(question: str) -> RunScript:
    """A run paused on the agent's own question (run it with outcome ``paused``).

    The real ``agent_question`` checkpoint, with ``question`` as the agent's text.
    """
    checkpoint = dict(
        _captured_checkpoint("composed_paused_agent_question.json"), question=question
    )
    return RunScript({}, {"checkpoint": checkpoint, "reviews": []})


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
