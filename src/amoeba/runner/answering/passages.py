"""The passages an answering run sees: types, cutting, selection, assembly (slice 143).

Pure: no file, process or store access. ``source_reads`` fetches committed text and
``sources`` wires it to the store; everything that can be decided from values lives
here so it is tested without a repository.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

#: ATX heading of level 1-3: up to three leading spaces, 1-3 ``#``, then a blank or EOL.
_CUT_HEADING = re.compile(r"^ {0,3}#{1,3}(?:[ \t]|$)")
_FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_LINES = re.compile(r"[^\n]*\n|[^\n]+")


class PassageKind(StrEnum):
    """The ``kind:`` words of 140's ``passages.md`` format."""

    RULE = "rule"
    PLAN = "plan"
    PM_ANSWER = "pm_answer"


@dataclass(frozen=True)
class Passage:
    """One numbered, dated piece of source text."""

    id: str
    kind: PassageKind
    #: Repo-relative path for a rule or plan passage; ``None`` for a PM answer.
    source: str | None
    date: datetime
    text: str
    #: PM answers only: the question the PM answered.
    question: str | None
    #: PM answers only: the slice the question was about.
    slice_label: str | None
    #: PM answers only: the record it came from. Not rendered.
    question_id: str | None


@dataclass(frozen=True)
class PassageSet:
    """The passages for one question, the commit they were read at, and what was cut."""

    passages: tuple[Passage, ...]
    source_commit: str
    #: Record ids of PM answers that did not fit the size limit, in trimming order.
    dropped_pm_answers: tuple[str, ...]

    @property
    def ids(self) -> frozenset[str]:
        return frozenset(passage.id for passage in self.passages)


@dataclass(frozen=True)
class SourceFile:
    """One committed rules or plan file, read whole."""

    path: str
    kind: PassageKind
    date: datetime
    text: str


@dataclass(frozen=True)
class PmAnswer:
    """One PM answer to an earlier question, offered as precedent."""

    record_id: str
    question: str
    answer: str
    date: datetime
    node_id: str
    slice_label: str


class SourcesProblemKind(StrEnum):
    TOO_LARGE = "sources_too_large"
    MISSING = "sources_missing"
    UNREADABLE = "sources_unreadable"


@dataclass(frozen=True)
class SourcesProblem:
    """Why a passage set could not be built; ``detail`` names the path or command."""

    kind: SourcesProblemKind
    detail: str


class CitationKind(StrEnum):
    UNCITED = "uncited"
    UNKNOWN_IDS = "unknown_ids"


@dataclass(frozen=True)
class CitationProblem:
    kind: CitationKind
    #: The cited ids that are not in the set, in cited order; empty for ``uncited``.
    ids: tuple[str, ...]


def cut_passages(text: str) -> tuple[str, ...]:
    """Cut ``text`` before every level 1-3 heading outside a fenced code block.

    Text is never rewritten, so joining the passages gives back ``text``, except that
    a blank preamble (whitespace before the first heading) is dropped. Text before the
    first heading, front matter included, is its own passage. A file with no headings
    is one passage; empty text gives none.
    """
    passages: list[str] = []
    current: list[str] = []
    fence: str | None = None
    for line in _LINES.findall(text):
        fence = _fence_after(line, fence)
        if fence is None and _CUT_HEADING.match(line) and current:
            passages.append("".join(current))
            current = []
        current.append(line)
    if current:
        passages.append("".join(current))
    if passages and not passages[0].strip():
        passages.pop(0)
    return tuple(passages)


def _fence_after(line: str, fence: str | None) -> str | None:
    """The open fence marker once ``line`` is read; ``None`` outside a fence.

    A fence opens on three or more backticks or tildes and closes on a line holding at
    least as many of the same character and nothing else but blanks. A heading line is
    a heading only when this returns ``None`` for it, including a closing fence line.
    """
    opened = _FENCE_OPEN.match(line)
    if fence is None:
        return opened.group(1) if opened else None
    if opened and opened.group(1)[0] == fence[0] and len(opened.group(1)) >= len(fence):
        if not line.strip().strip(fence[0]):
            return None
    return fence
