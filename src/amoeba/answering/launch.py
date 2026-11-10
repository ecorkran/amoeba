"""Before a run starts: passage provenance and the scratch directory.

The caller assembles the sources, calls :func:`prepare_scratch_directory`, and starts
the run. Nothing here reads a store or starts a process.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Sequence
from pathlib import Path

from amoeba.answering.inputs import BarredItem, QuestionInput, prepare_scratch
from amoeba.answering.passages import PassageSet
from amoeba.answering.values import PassageRef

logger = logging.getLogger(__name__)


def passage_refs(passages: PassageSet) -> tuple[PassageRef, ...]:
    """Where each passage came from, without its text (D11).

    A PM passage has no path: its record id stands for both its source and its
    question.

    Raises:
        ValueError: A passage has neither a path nor a question record.
    """
    refs: list[PassageRef] = []
    for passage in passages.passages:
        source = passage.source or passage.question_id
        if source is None:
            raise ValueError(f"passage {passage.id} has no source")
        refs.append(PassageRef(passage.id, source, passage.question_id, passage.date))
    return tuple(refs)


def prepare_scratch_directory(
    scratch: Path,
    question: QuestionInput,
    passages: str,
    max_cost_usd: float,
    *,
    not_authorized: Sequence[BarredItem],
) -> str | None:
    """Make and fill the scratch directory; the error text if the disk refused.

    ``not_authorized`` is the member's own list, always stated by the caller.
    """
    try:
        scratch.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive: a directory is never reused, even on a run id collision.
        scratch.mkdir()
        prepare_scratch(
            scratch, question, passages, max_cost_usd, not_authorized=not_authorized
        )
    except OSError as error:
        # An expected external failure (permissions, a full disk): an answer for
        # the caller to record as a decline, not a bug. ``prepare_scratch``'s
        # ``ValueError`` is misuse and is not caught.
        return f"{type(error).__name__}: {error}"
    return None


def discard_scratch(scratch: Path) -> None:
    """Remove a scratch directory that was made and then not used."""
    try:
        shutil.rmtree(scratch)
    except OSError:
        # Best effort on a directory nothing references: a leftover is clutter, not
        # a fault, and the launch has already been given up. Logged, not raised.
        logger.warning("could not remove unused scratch directory %s", scratch)
