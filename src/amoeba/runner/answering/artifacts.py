"""The artifact contract: parse the reply files a finished run leaves (D6).

Parsers return a typed value or an :class:`ArtifactProblem` and never raise for
bad file content: bad model output is a normal outcome. Squadron does the JSON
extraction (D8); here the file is parsed as one JSON object, nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

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


_NonEmptyStr = Annotated[str, Field(min_length=1)]
_MODEL_CONFIG = ConfigDict(extra="ignore", frozen=True, str_strip_whitespace=True)


def _trimmed_lower(value: object) -> object:
    """Trim and lowercase a string before enum matching; other types pass through."""
    return value.strip().lower() if isinstance(value, str) else value


_LenientAnswerKind = Annotated[AnswerKind, BeforeValidator(_trimmed_lower)]
_LenientVerdict = Annotated[Verdict, BeforeValidator(_trimmed_lower)]


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


class _AnswerReplyModel(BaseModel):
    """The answer step's reply file, in the shape it must take on disk."""

    model_config = _MODEL_CONFIG

    kind: _LenientAnswerKind
    answer: _NonEmptyStr | None = None
    cited: tuple[str, ...] | None = None  # required when kind is 'answer'
    reason: _NonEmptyStr | None = None


class _CheckReplyModel(BaseModel):
    """The check step's reply file, in the shape it must take on disk."""

    model_config = _MODEL_CONFIG

    verdict: _LenientVerdict
    reason: str | None = None


def _read_bytes(path: Path) -> bytes | ArtifactProblem:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return ArtifactProblem(ProblemKind.MISSING, f"{path.name} was not written")
    except OSError as error:
        # Unreadable (a directory, permissions): a normal outcome, reported by name.
        return ArtifactProblem(
            ProblemKind.MALFORMED, f"{path.name} is unreadable: {error}"
        )


def _malformed(file_name: str, detail: str) -> ArtifactProblem:
    return ArtifactProblem(ProblemKind.MALFORMED, f"{file_name}: {detail}")


def read_answer(directory: Path) -> AnswerReply | ArtifactProblem:
    """Parse the answer step's reply file in ``directory``."""
    raw = _read_bytes(directory / ANSWER_REPLY_FILE)
    if isinstance(raw, ArtifactProblem):
        return raw
    try:
        document = _AnswerReplyModel.model_validate_json(raw)
    except ValidationError as error:
        return _malformed(ANSWER_REPLY_FILE, str(error))
    if document.kind is AnswerKind.DECLINE:
        if document.reason is None:
            return _malformed(ANSWER_REPLY_FILE, "a decline needs a non-empty 'reason'")
        return AnswererDecline(reason=document.reason)
    if document.answer is None:
        return _malformed(ANSWER_REPLY_FILE, "an answer needs non-empty 'answer' text")
    if document.cited is None:
        return _malformed(ANSWER_REPLY_FILE, "'cited' must be a list of strings")
    return ProposedAnswer(answer=document.answer, cited=document.cited)


def read_check(directory: Path) -> CheckReply | ArtifactProblem:
    """Parse the check step's reply file in ``directory``."""
    raw = _read_bytes(directory / CHECK_REPLY_FILE)
    if isinstance(raw, ArtifactProblem):
        return raw
    try:
        document = _CheckReplyModel.model_validate_json(raw)
    except ValidationError as error:
        return _malformed(CHECK_REPLY_FILE, str(error))
    return CheckReply(verdict=document.verdict, reason=document.reason)
