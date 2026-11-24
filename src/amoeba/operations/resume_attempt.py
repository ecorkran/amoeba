"""The small file a resume attempt leaves on its own machine (slice 262, D6).

``logs/resume/<run id>/<answer seq>.attempt`` is written twice: ``started`` just before
``sq run --resume`` is started, then the judged outcome before ``resume_record`` is
called. A later attempt for the same answer runs on the same machine and reads it
first, so a lost record or a killed attempt does not turn a resumed answer into
``not_delivered``. Each write goes to a temporary name and is renamed, so a reader
sees a whole file or none.

A write that fails is logged at error level and the attempt goes on: ``resume_record``
is the record that counts. A file that cannot be read is logged and read as none.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from amoeba.store.vocabulary import ResumeOutcome

logger = logging.getLogger(__name__)

RESUME_LOG_DIRECTORY: Final = "resume"
ATTEMPT_SUFFIX: Final = ".attempt"
TEMPORARY_SUFFIX: Final = ".tmp"
#: The file's one non-outcome state: the attempt is about to start ``sq``.
STARTED: Final = "started"


@dataclass(frozen=True)
class AttemptFile:
    """What the file holds: ``started`` (no outcome) or a judged outcome."""

    outcome: ResumeOutcome | None
    detail: str | None = None
    log: str | None = None

    @property
    def is_started(self) -> bool:
        return self.outcome is None


def attempt_path(logs_dir: Path, run_id: str, answer_seq: int) -> Path:
    """Where the attempt file of this answer lives."""
    return logs_dir / RESUME_LOG_DIRECTORY / run_id / f"{answer_seq}{ATTEMPT_SUFFIX}"


def read_attempt(path: Path) -> AttemptFile | None:
    """The file's content, or ``None`` when there is no file or it cannot be read."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Expected: the first attempt for this answer leaves no earlier file.
        return None
    except OSError:
        logger.exception("cannot read the resume attempt file %s", path)
        return None
    try:
        return _parse(text)
    except (ValueError, TypeError, KeyError):
        logger.exception("the resume attempt file %s is not readable", path)
        return None


def _parse(text: str) -> AttemptFile:
    document = json.loads(text)
    state = document["state"]
    if state == STARTED:
        return AttemptFile(outcome=None)
    return AttemptFile(
        outcome=ResumeOutcome(state),
        detail=document.get("detail"),
        log=document.get("log"),
    )


def write_started(path: Path) -> None:
    """Record that ``sq run --resume`` is about to be started; never raises."""
    _write(path, {"state": STARTED})


def write_judged(
    path: Path, outcome: ResumeOutcome, detail: str | None, log: str | None
) -> None:
    """Record the outcome this attempt judged, before it is recorded; never raises."""
    _write(path, {"state": outcome.value, "detail": detail, "log": log})


def _write(path: Path, document: dict[str, str | None]) -> None:
    temporary = path.with_name(path.name + TEMPORARY_SUFFIX)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(document), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        # Logged, not raised: the attempt goes on and ``resume_record`` is the record
        # that counts. Without the file a later attempt behaves as it did before it.
        logger.exception("cannot write the resume attempt file %s", path)
