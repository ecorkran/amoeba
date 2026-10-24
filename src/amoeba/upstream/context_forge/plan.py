"""Context Forge's plan reads: initiatives and the slice list of one initiative.

``cf list initiatives --json -a`` and ``cf list slices <index> --json`` are the
Runner's view of a project's plan. This module holds their models and parsers and
nothing else: running ``cf`` belongs to the Runner.

Models are lenient where CF varies and strict where the Runner relies on a field:
an unknown extra field is ignored, but a missing ``index``, ``name`` or
``isChecked`` (or ``entries``) fails the whole read with one :class:`PlanParseError`.
A status outside :class:`PlanEntryStatus` is an explicit :class:`UnknownPlanStatus`
carrying the raw text, never a default. An absent status is ``None``: CF did not
report one.

The ``error: true`` document CF prints for an initiative without a slice plan is a
CF answer, not a parse failure; :func:`parse_slice_list` returns it as a
:class:`CFErrorDocument`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Final, Literal, cast

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

#: The two reads, named in a :class:`PlanParseError`.
READ_INITIATIVES: Final = "list initiatives"
READ_SLICE_LIST: Final = "list slices"

#: Where a failing entry's own index sits, for the error message.
_ENTRIES_KEY: Final = "entries"
_ENTRY_INDEX_KEY: Final = "index"
_ERROR_FLAG_KEY: Final = "error"


class PlanEntryStatus(StrEnum):
    """The plan-entry statuses CF reports."""

    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"
    DEPRECATED = "deprecated"
    DEFERRED = "deferred"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class UnknownPlanStatus:
    """A status outside :class:`PlanEntryStatus`, with the text CF printed."""

    raw: str


type PlanStatus = PlanEntryStatus | UnknownPlanStatus


class PlanParseError(ValueError):
    """A plan read whose output cannot be used.

    Attributes:
        read: Which read failed (:data:`READ_INITIATIVES` or :data:`READ_SLICE_LIST`).
        entry_index: The CF index of the failing entry, when one was parsed.
        detail: What was wrong.
    """

    def __init__(self, read: str, entry_index: int | None, detail: str) -> None:
        where = "" if entry_index is None else f" (entry index {entry_index})"
        super().__init__(f"{read}{where}: {detail}")
        self.read = read
        self.entry_index = entry_index
        self.detail = detail


def _coerce_status(value: object) -> PlanStatus | None:
    if value is None or isinstance(value, PlanEntryStatus | UnknownPlanStatus):
        return value
    try:
        return PlanEntryStatus(value)
    except ValueError:
        # Specific: text outside the vocabulary is an answer, kept with its raw
        # value, so the caller decides what an unknown status means.
        return UnknownPlanStatus(raw=str(value))


type _Status = Annotated[PlanStatus | None, BeforeValidator(_coerce_status)]


class _PlanModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class CFInitiative(_PlanModel):
    """One initiative of ``cf list initiatives --json -a``."""

    index: int
    name: str
    is_checked: bool = Field(alias="isChecked")
    arch_file: str | None = Field(default=None, alias="archFile")
    status: _Status = None


class CFSliceEntry(_PlanModel):
    """One slice of ``cf list slices <index> --json``."""

    index: int
    name: str
    is_checked: bool = Field(alias="isChecked")
    design_file: str | None = Field(default=None, alias="designFile")
    status: _Status = None


class CFSliceList(_PlanModel):
    """The slice plan of one initiative."""

    entries: tuple[CFSliceEntry, ...]


class CFErrorDocument(_PlanModel):
    """CF's ``error: true`` document. CF reports every error as ``code: UNKNOWN``,
    so a decision never reads ``message``."""

    error: Literal[True]
    code: str | None = None
    message: str | None = None


def reported_complete(entry: CFInitiative | CFSliceEntry) -> bool:
    """Whether CF reports the entry complete: ``complete`` status or checked."""
    return entry.is_checked or entry.status == PlanEntryStatus.COMPLETE


def parse_initiatives(text: str) -> list[CFInitiative]:
    """Parse ``cf list initiatives --json -a``.

    Raises:
        PlanParseError: Malformed JSON, a top-level form that is not an array, or
            an entry missing a required field.
    """
    document = _as_array(_load(text, READ_INITIATIVES))
    if document is None:
        raise PlanParseError(READ_INITIATIVES, None, "expected a JSON array")
    return [
        _validate(CFInitiative, raw, READ_INITIATIVES, _own_index(raw))
        for raw in document
    ]


def parse_slice_list(text: str) -> CFSliceList | CFErrorDocument:
    """Parse ``cf list slices <index> --json``, or CF's error document.

    Raises:
        PlanParseError: Malformed JSON, a top-level form that is not an object,
            or a missing ``entries`` or required entry field.
    """
    document = _as_object(_load(text, READ_SLICE_LIST))
    if document is None:
        raise PlanParseError(READ_SLICE_LIST, None, "expected a JSON object")
    if document.get(_ERROR_FLAG_KEY) is True:
        return _validate(CFErrorDocument, document, READ_SLICE_LIST, None)
    entries = _as_array(document.get(_ENTRIES_KEY))
    if entries is None:
        raise PlanParseError(READ_SLICE_LIST, None, f"{_ENTRIES_KEY} is missing")
    parsed = tuple(
        _validate(CFSliceEntry, raw, READ_SLICE_LIST, _own_index(raw))
        for raw in entries
    )
    return CFSliceList(entries=parsed)


def _load(text: str, read: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        # Specific: not JSON at all. Re-raised as the one parse error.
        raise PlanParseError(read, None, f"not JSON: {error}") from error


def _as_array(value: object) -> list[object] | None:
    return cast("list[object]", value) if isinstance(value, list) else None


def _as_object(value: object) -> dict[str, object] | None:
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def _own_index(raw: object) -> int | None:
    """The entry's own index when it is a usable int, for error messages."""
    entry = _as_object(raw)
    if entry is None:
        return None
    index = entry.get(_ENTRY_INDEX_KEY)
    if isinstance(index, int) and not isinstance(index, bool):
        return index
    return None


def _validate[ModelT: _PlanModel](
    model: type[ModelT], raw: object, read: str, entry_index: int | None
) -> ModelT:
    try:
        return model.model_validate(raw)
    except ValidationError as error:
        # Specific: a missing or mistyped field. Re-raised naming the read, the
        # entry index when known, and pydantic's own message.
        raise PlanParseError(read, entry_index, str(error)) from error
