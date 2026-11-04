"""The reply contract: parse the reply file a finished run leaves (D7).

``read_reply`` returns a typed value or a :class:`ReplyProblem` and never raises
for bad file content: bad model output is a normal outcome. Squadron does the JSON
extraction; here the file is parsed as one JSON object and checked for shape only.
Whether the index is new or the commit exists is for later slices to decide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, ValidationError

from amoeba.runner.request_run.pipeline_file import REPLY_FILE

_COMMIT_PATTERN = re.compile(r"[0-9a-fA-F]{7,40}")


class ProblemKind(StrEnum):
    MISSING = "missing"
    MALFORMED = "malformed"


class ReplyKind(StrEnum):
    """Values of the reply's ``kind`` key."""

    NEW_SLICE = "new_slice"
    ALREADY_MET = "already_met"


@dataclass(frozen=True)
class NewSlice:
    index: int


@dataclass(frozen=True)
class AlreadyMet:
    commit: str


@dataclass(frozen=True)
class ReplyProblem:
    kind: ProblemKind
    detail: str


def _lenient_kind(value: object) -> object:
    """Trim and lowercase a string before enum matching; other types pass through."""
    return value.strip().lower() if isinstance(value, str) else value


def _positive_index(value: object) -> int:
    """An integer, or decimal digits after trimming; positive; never a boolean.

    Raises:
        ValueError: Naming the cause, for an absent or bad value.
    """
    if isinstance(value, bool):
        raise ValueError("index must not be a boolean")
    if isinstance(value, str):
        text = value.strip()
        if not (text.isascii() and text.isdigit()):
            raise ValueError("index must be an integer or a string of digits")
        value = int(text)
    if not isinstance(value, int):
        raise ValueError("index must be an integer or a string of digits")
    if value < 1:
        raise ValueError("index must be positive")
    return value


def _commit_hash(value: object) -> str:
    """7 to 40 hexadecimal characters after trimming, returned lower case.

    Raises:
        ValueError: Naming the cause, for an absent or bad value.
    """
    if not isinstance(value, str) or not _COMMIT_PATTERN.fullmatch(value.strip()):
        raise ValueError("commit must be 7 to 40 hexadecimal characters")
    return value.strip().lower()


class _ReplyModel(BaseModel):
    """The reply file in the shape it must take on disk."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    kind: Annotated[ReplyKind, BeforeValidator(_lenient_kind)]
    # Checked only for the kind that uses them, so a stray value for the other
    # kind's key is an ignored unknown key, not a malformed reply.
    index: object = None
    commit: object = None


def _malformed(detail: str) -> ReplyProblem:
    return ReplyProblem(ProblemKind.MALFORMED, f"{REPLY_FILE}: {detail}")


def read_reply(directory: Path) -> NewSlice | AlreadyMet | ReplyProblem:
    """Parse the write step's reply file in ``directory``.

    Raises:
        ValueError: When ``directory`` is not an existing directory (a programming
            error; model output cannot cause it).
    """
    if not directory.is_dir():
        raise ValueError(f"reply directory does not exist: {directory}")
    path = directory / REPLY_FILE
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return ReplyProblem(ProblemKind.MISSING, f"{REPLY_FILE} was not written")
    except OSError as error:
        # Unreadable (a directory, permissions): a normal outcome, reported by name.
        return _malformed(f"unreadable: {error}")
    try:
        document = _ReplyModel.model_validate_json(raw)
    except ValidationError as error:
        return _malformed(str(error))
    try:
        if document.kind is ReplyKind.NEW_SLICE:
            return NewSlice(index=_positive_index(document.index))
        return AlreadyMet(commit=_commit_hash(document.commit))
    except ValueError as error:
        # The validators name the cause; a bad or absent value is model output.
        return _malformed(f"{document.kind} reply: {error}")
