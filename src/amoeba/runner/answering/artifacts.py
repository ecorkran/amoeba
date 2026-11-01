"""The artifact contract: parse the reply files a finished run leaves (D6).

Parsers return a typed value or an :class:`ArtifactProblem` and never raise for
bad file content: bad model output is a normal outcome. Squadron does the JSON
extraction (D8); here the file is parsed as one JSON object, nothing more.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, cast

from amoeba.runner.answering.pipeline_file import ANSWER_REPLY_FILE, CHECK_REPLY_FILE


class ProblemKind(StrEnum):
    MISSING = "missing"
    MALFORMED = "malformed"


class AnswerKind(StrEnum):
    """Values of an answer reply's ``kind`` key."""

    ANSWER = "answer"
    DECLINE = "decline"


class Verdict(StrEnum):
    """Values of a check reply's ``verdict`` key."""

    YES = "yes"
    NO = "no"


# Reply key names, defined once.
KIND_KEY: Final = "kind"
ANSWER_KEY: Final = "answer"
CITED_KEY: Final = "cited"
REASON_KEY: Final = "reason"
VERDICT_KEY: Final = "verdict"


@dataclass(frozen=True)
class ProposedAnswer:
    answer: str
    cited: tuple[str, ...]


@dataclass(frozen=True)
class AnswererDecline:
    reason: str


@dataclass(frozen=True)
class CheckReply:
    verdict: Verdict
    reason: str | None


@dataclass(frozen=True)
class ArtifactProblem:
    kind: ProblemKind
    detail: str


AnswerReply = ProposedAnswer | AnswererDecline


def _read_object(path: Path) -> dict[str, object] | ArtifactProblem:
    """The file's single JSON object, or the problem that prevents reading it."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return ArtifactProblem(ProblemKind.MISSING, f"{path.name} was not written")
    except OSError as error:
        # Unreadable (a directory, permissions): a normal outcome, reported by name.
        return ArtifactProblem(
            ProblemKind.MALFORMED, f"{path.name} is unreadable: {error}"
        )
    try:
        parsed: object = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as error:
        return ArtifactProblem(
            ProblemKind.MALFORMED, f"{path.name} is not UTF-8: {error}"
        )
    except json.JSONDecodeError as error:
        return ArtifactProblem(
            ProblemKind.MALFORMED, f"{path.name} is not JSON: {error}"
        )
    if not isinstance(parsed, dict):
        return ArtifactProblem(
            ProblemKind.MALFORMED,
            f"{path.name} holds {type(parsed).__name__}, not one JSON object",
        )
    # JSON object keys are always strings.
    return cast("dict[str, object]", parsed)


def _malformed(file_name: str, detail: str) -> ArtifactProblem:
    return ArtifactProblem(ProblemKind.MALFORMED, f"{file_name}: {detail}")


def _enum_value[E: StrEnum](enum: type[E], value: object) -> E | None:
    """Match a string to an enum member, trimmed and case-insensitive."""
    if not isinstance(value, str):
        return None
    try:
        return enum(value.strip().lower())
    except ValueError:
        return None


def _non_empty_text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _string_list(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    items = cast("list[object]", value)
    strings = tuple(item for item in items if isinstance(item, str))
    return strings if len(strings) == len(items) else None


def read_answer(directory: Path) -> AnswerReply | ArtifactProblem:
    """Parse the answer step's reply file in ``directory``."""
    document = _read_object(directory / ANSWER_REPLY_FILE)
    if isinstance(document, ArtifactProblem):
        return document
    kind = _enum_value(AnswerKind, document.get(KIND_KEY))
    if kind is None:
        return _malformed(
            ANSWER_REPLY_FILE,
            f"'{KIND_KEY}' must be one of {[k.value for k in AnswerKind]}, "
            f"got {document.get(KIND_KEY)!r}",
        )
    if kind is AnswerKind.DECLINE:
        reason = _non_empty_text(document.get(REASON_KEY))
        if reason is None:
            return _malformed(
                ANSWER_REPLY_FILE, f"a decline needs a non-empty '{REASON_KEY}'"
            )
        return AnswererDecline(reason=reason)
    text = _non_empty_text(document.get(ANSWER_KEY))
    if text is None:
        return _malformed(
            ANSWER_REPLY_FILE, f"an answer needs non-empty '{ANSWER_KEY}' text"
        )
    cited = _string_list(document.get(CITED_KEY))
    if cited is None:
        return _malformed(ANSWER_REPLY_FILE, f"'{CITED_KEY}' must be a list of strings")
    return ProposedAnswer(answer=text, cited=cited)


def read_check(directory: Path) -> CheckReply | ArtifactProblem:
    """Parse the check step's reply file in ``directory``."""
    document = _read_object(directory / CHECK_REPLY_FILE)
    if isinstance(document, ArtifactProblem):
        return document
    verdict = _enum_value(Verdict, document.get(VERDICT_KEY))
    if verdict is None:
        return _malformed(
            CHECK_REPLY_FILE,
            f"'{VERDICT_KEY}' must be one of {[v.value for v in Verdict]}, "
            f"got {document.get(VERDICT_KEY)!r}",
        )
    reason = document.get(REASON_KEY)
    return CheckReply(
        verdict=verdict, reason=reason if isinstance(reason, str) else None
    )
