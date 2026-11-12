"""The passages an answering run sees: types, cutting, selection, assembly (slice 143).

Pure: no file, process or store access. ``source_reads`` fetches committed text and
``operations.pause_context.gather`` wires it to the caller's values; everything that
can be decided from values lives here so it is tested without a repository.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final

from amoeba.answering.values import GLOB_WILDCARD

_FRONT_MATTER_MARK: Final = "---"
#: ATX heading of level 1-3: up to three leading spaces, 1-3 ``#``, then a blank or EOL.
_CUT_HEADING = re.compile(r"^ {0,3}#{1,3}(?:[ \t]|$)")
_FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_LINES = re.compile(r"[^\n]*\n|[^\n]+")
#: Each section ends in a newline, so one more newline is the blank line between them.
_SECTION_SEPARATOR = "\n"


class PassageKind(StrEnum):
    """The ``kind:`` words of 140's ``passages.md`` format."""

    RULE = "rule"
    PLAN = "plan"
    PM_ANSWER = "pm_answer"
    PROGRAM_CONCEPT = "program_concept"
    PROGRAM_MEMBERS = "program_members"


@dataclass(frozen=True)
class Passage:
    """One numbered, dated piece of source text."""

    id: str
    kind: PassageKind
    #: Repo-relative path for a rule, plan or concept passage; the program id for the
    #: member list (recorded, not rendered); ``None`` for a PM answer.
    source: str | None
    date: datetime
    text: str
    #: PM answers only: the question the PM answered.
    question: str | None
    #: PM answers only: the slice the question was about.
    slice_label: str | None
    #: PM answers only: the record it came from. Not rendered.
    question_id: str | None
    #: Program concept passages only: the project that holds the concept file.
    member: str | None


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
    """One committed rules, plan or program file, read whole.

    ``path`` is the repo-relative path, or the program id for the member list.
    """

    path: str
    kind: PassageKind
    date: datetime
    text: str
    #: Program concept only: the project that holds the file.
    member: str | None


@dataclass(frozen=True)
class ProgramSources:
    """The program files an answering run adds to a member's question (slice 182)."""

    #: Kind ``program_concept``, ``member`` set to the concept member. ``None`` for a
    #: program with no concept: then there is no concept passage.
    concept: SourceFile | None
    #: Kind ``program_members``; its path is the program id and is not rendered.
    members: SourceFile

    @property
    def files(self) -> tuple[SourceFile, ...]:
        """The files in offer order: the concept (if any), then the member list."""
        return (self.members,) if self.concept is None else (self.concept, self.members)


@dataclass(frozen=True)
class PmAnswer:
    """One PM answer to an earlier question, offered as precedent."""

    record_id: str
    question: str
    answer: str
    date: datetime
    #: The slice it was answered on, as ``<index> <title>``; ``None`` when the
    #: question was recorded before its slice was known (then no ``slice:`` line is
    #: rendered, so the check cannot match it to a slice).
    slice_label: str | None


class SourcesProblemKind(StrEnum):
    TOO_LARGE = "sources_too_large"
    MISSING = "sources_missing"
    UNREADABLE = "sources_unreadable"


@dataclass(frozen=True)
class SourcesProblem:
    """Why a passage set could not be built; ``detail`` names the path or command."""

    kind: SourcesProblemKind
    detail: str


def unreadable(detail: str) -> SourcesProblem:
    """A ``sources_unreadable`` problem, the one every read failure becomes."""
    return SourcesProblem(SourcesProblemKind.UNREADABLE, detail)


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
    lines = _LINES.findall(text)
    front_matter_end = _front_matter_end(lines)
    for number, line in enumerate(lines):
        fence = _fence_after(line, fence)
        in_front_matter = number <= front_matter_end
        if (
            not in_front_matter
            and fence is None
            and _CUT_HEADING.match(line)
            and current
        ):
            passages.append("".join(current))
            current = []
        current.append(line)
    if current:
        passages.append("".join(current))
    if passages and not passages[0].strip():
        passages.pop(0)
    return tuple(passages)


def _front_matter_end(lines: list[str]) -> int:
    """The index of the line closing a leading ``---`` block, or ``-1`` for none.

    Inside the block ``#`` lines are YAML comments, not headings. A file that opens
    with ``---`` but never closes it has no front matter (it is a rule).
    """
    if not lines or lines[0].strip() != _FRONT_MATTER_MARK:
        return -1
    for number, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONT_MATTER_MARK:
            return number
    return -1


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


@dataclass(frozen=True)
class PlanRow:
    """One row of CF's document layout: where a plan file lives and what it is named.

    ``pattern`` may hold ``{initiative}``, ``{slice}`` and ``*``; the rest is literal.
    """

    directory: str
    pattern: str
    #: Finding no file for a required row is a problem; any other row may be empty.
    required: bool


def glob_matches(pattern: str, names: Sequence[str]) -> tuple[str, ...]:
    """The ``names`` that match ``pattern``, sorted. ``*`` is the only wildcard."""
    parts = pattern.split(GLOB_WILDCARD)
    expression = ".*".join(re.escape(part) for part in parts)
    return tuple(sorted(name for name in names if re.fullmatch(expression, name)))


def match_rules_entry(entry: str, listing: Sequence[str]) -> tuple[str, ...]:
    """The files in the entry's parent directory that the entry names.

    Only the entry's last path segment is compared, against each listed name; the
    parent directory is the caller's concern (it produced ``listing``).
    """
    return glob_matches(entry.rsplit("/", 1)[-1], listing)


def select_plan_files(
    rows: Sequence[PlanRow],
    listings: Mapping[str, Sequence[str]],
    slice_index: int,
    initiative_index: int,
) -> tuple[str, ...]:
    """Repo-relative plan file paths: table order, then file name within a row.

    A directory with no listing matches nothing.
    """
    paths: list[str] = []
    for row in rows:
        pattern = row.pattern.replace("{slice}", str(slice_index)).replace(
            "{initiative}", str(initiative_index)
        )
        names = glob_matches(pattern, listings.get(row.directory, ()))
        paths.extend(f"{row.directory}/{name}" for name in names)
    return tuple(paths)


def format_utc(moment: datetime) -> str:
    """``YYYY-MM-DDTHH:MM:SSZ``: UTC, to the second (140's ``passages.md`` date)."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_git_date(text: str) -> datetime | None:
    """A git ISO 8601 date, or ``None`` when empty, unparseable or without an offset.

    The caller turns ``None`` into ``sources_unreadable``; there is no fallback date.
    """
    try:
        moment = datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def _render_section(passage: Passage) -> str:
    """One ``## Passage`` section, ending in a newline."""
    lines = [f"## Passage {passage.id}", "", f"kind: {passage.kind}"]
    if passage.member is not None:
        lines.append(f"member: {passage.member}")
    # The member list's ``source`` is the program id, kept for the passage record.
    if passage.source is not None and passage.kind is not PassageKind.PROGRAM_MEMBERS:
        lines.append(f"source: {passage.source}")
    lines.append(f"date: {format_utc(passage.date)}")
    if passage.question is not None:
        lines.append(f"question: {passage.question}")
    if passage.slice_label is not None:
        lines.append(f"slice: {passage.slice_label}")
    head = "\n".join([*lines, "", ""])
    return head + passage.text + ("" if passage.text.endswith("\n") else "\n")


def render_passages(passage_set: PassageSet) -> str:
    """140's ``passages.md``: sections a blank line apart; empty for no passages."""
    return _SECTION_SEPARATOR.join(_render_section(p) for p in passage_set.passages)


def _pm_passage(answer: PmAnswer, number: int) -> Passage:
    return Passage(
        id=f"P{number}",
        kind=PassageKind.PM_ANSWER,
        source=None,
        date=answer.date,
        text=answer.answer,
        question=answer.question,
        slice_label=answer.slice_label,
        question_id=answer.record_id,
        member=None,
    )


def _committed_passages(committed: Sequence[SourceFile]) -> list[Passage]:
    found: list[Passage] = []
    for source in committed:
        for piece in cut_passages(source.text):
            found.append(
                Passage(
                    id=f"P{len(found) + 1}",
                    kind=source.kind,
                    source=source.path,
                    date=source.date,
                    text=piece,
                    question=None,
                    slice_label=None,
                    question_id=None,
                    member=source.member,
                )
            )
    return found


def _pm_order(answers: Sequence[PmAnswer]) -> list[PmAnswer]:
    """Newest first; ties (to the second) by record id.

    The slice label is never used to order or match: it is display text the answering
    models compare, and a renamed slice must not change what is kept.
    """
    return sorted(answers, key=lambda a: (-int(a.date.timestamp()), a.record_id))


def assemble(
    committed: Sequence[SourceFile],
    pm_answers: Sequence[PmAnswer],
    *,
    program_sources: ProgramSources,
    max_chars: int,
    source_commit: str,
) -> PassageSet | SourcesProblem:
    """Number the passages and fit PM precedent into ``max_chars`` of rendered text.

    Rules, plan and program passages (the concept, then the member list) are never
    trimmed: if they alone exceed the limit the result is ``sources_too_large``. PM
    answers are added in priority order until one does not fit; that one and every
    later one are dropped, so a smaller, lower-priority answer never jumps a dropped
    one.
    """
    kept = _committed_passages((*committed, *program_sources.files))
    size = _rendered_size(kept)
    if size > max_chars:
        return SourcesProblem(
            SourcesProblemKind.TOO_LARGE,
            f"rules, plan and program passages are {size} characters; "
            f"the limit is {max_chars}",
        )
    ordered = _pm_order(pm_answers)
    for position, answer in enumerate(ordered):
        passage = _pm_passage(answer, len(kept) + 1)
        grown = (
            size + len(_SECTION_SEPARATOR) * bool(kept) + len(_render_section(passage))
        )
        if grown > max_chars:
            dropped = tuple(a.record_id for a in ordered[position:])
            return PassageSet(tuple(kept), source_commit, dropped)
        kept.append(passage)
        size = grown
    return PassageSet(tuple(kept), source_commit, ())


def _rendered_size(kept: Sequence[Passage]) -> int:
    return len(render_passages(PassageSet(tuple(kept), "", ())))


def check_citations(
    cited: Sequence[str], passage_ids: Collection[str]
) -> CitationProblem | None:
    """The one place "every cited id is in the set" is decided (slice 143, D8).

    Ids are trimmed and upper-cased first. Blank entries are ignored; nothing left is
    ``uncited``. Unknown ids are reported once each, in cited order.
    """
    normalized = [item.strip().upper() for item in cited if item.strip()]
    if not normalized:
        return CitationProblem(CitationKind.UNCITED, ())
    unknown = tuple(dict.fromkeys(i for i in normalized if i not in passage_ids))
    return CitationProblem(CitationKind.UNKNOWN_IDS, unknown) if unknown else None
