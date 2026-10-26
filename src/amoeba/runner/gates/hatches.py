"""The two silent-ungate hatches as check records (slice 128, D4). Pure: no I/O.

CF's gate is skipped for a design whose frontmatter says ``review: none``, and for a
design created before a configured effective date. The Runner never writes either; it
reads the design and records what it found as two checks on the slice node. A hatch is
a ``failed`` check, and the routing table (D3) escalates anything not ``passed``. A
check that read no design is ``vacuous`` by 107's rule, so a missing design is never a
pass.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final, cast

import yaml

from amoeba.runner.gates.cf_reads import ReadFailure
from amoeba.runner.gates.checks import RunnerCheck, check_id, runner_provenance
from amoeba.store import CheckInput, CheckOutcome, RecordSource

FRONTMATTER_DELIMITER: Final = "---"
KEY_REVIEW: Final = "review"
KEY_DATE_CREATED: Final = "dateCreated"
REVIEW_NONE: Final = "none"
EFFECTIVE_DATE_DIGITS: Final = 8
_BYTE_ORDER_MARK: Final = "﻿"


@dataclass(frozen=True)
class FrontmatterError:
    """The design has no frontmatter, or it does not parse."""

    reason: str


@dataclass(frozen=True)
class DesignText:
    """The design file as read: its path (as the hatch checks record it) and text."""

    path: str
    text: str


@dataclass(frozen=True)
class DesignMissing:
    """No design was read: its path is unknown, or the file is not there."""

    reason: str
    path: str | None = None


type DesignSource = DesignText | DesignMissing


def read_frontmatter(text: str) -> Mapping[str, object] | FrontmatterError:
    """The YAML between a leading ``---`` line and the next ``---`` line.

    A byte-order mark and leading whitespace are allowed. ``dateCreated`` is returned
    as text, as CF compares it: YAML loads ``20261021`` as an integer.
    """
    lines = text.lstrip(_BYTE_ORDER_MARK).lstrip().splitlines()
    if not lines or lines[0].rstrip() != FRONTMATTER_DELIMITER:
        return FrontmatterError("the design has no frontmatter")
    for end, line in enumerate(lines[1:], start=1):
        if line.rstrip() == FRONTMATTER_DELIMITER:
            return _parse_block("\n".join(lines[1:end]))
    return FrontmatterError("the design's frontmatter is not closed")


def _parse_block(block: str) -> Mapping[str, object] | FrontmatterError:
    try:
        loaded: object = yaml.safe_load(block)
    except yaml.YAMLError as error:
        # Expected: frontmatter that is not YAML. Reported as a reason, not raised.
        return FrontmatterError(f"the design's frontmatter is not valid YAML: {error}")
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        return FrontmatterError("the design's frontmatter is not a mapping")
    fields = cast("dict[str, object]", loaded)
    created = fields.get(KEY_DATE_CREATED)
    if isinstance(created, date):
        fields[KEY_DATE_CREATED] = created.strftime("%Y%m%d")
    elif isinstance(created, int):
        fields[KEY_DATE_CREATED] = str(created)
    return fields


def hatch_checks(
    entry_id: str,
    slice_node_id: str,
    design: DesignSource,
    effective_date: str | ReadFailure,
    amoeba_version: str,
) -> tuple[CheckInput, CheckInput]:
    """The ``review: none`` check and the effective-date check for one outcome."""
    path = design.path
    provenance = runner_provenance(amoeba_version, RecordSource.DOCUMENT, path)
    frontmatter = (
        read_frontmatter(design.text) if isinstance(design, DesignText) else None
    )
    examined_count = 1 if isinstance(design, DesignText) else 0
    review_outcome, review_examined = _review_none(path, frontmatter)
    date_outcome, date_examined = _effective_date(path, frontmatter, effective_date)
    return (
        CheckInput(
            id=check_id(entry_id, RunnerCheck.UNGATE_REVIEW_NONE),
            node_id=slice_node_id,
            name=RunnerCheck.UNGATE_REVIEW_NONE.value,
            outcome=review_outcome,
            examined_count=examined_count,
            provenance=provenance,
            examined=review_examined,
        ),
        CheckInput(
            id=check_id(entry_id, RunnerCheck.UNGATE_EFFECTIVE_DATE),
            node_id=slice_node_id,
            name=RunnerCheck.UNGATE_EFFECTIVE_DATE.value,
            outcome=date_outcome,
            examined_count=examined_count,
            provenance=provenance,
            examined=date_examined,
        ),
    )


def _review_none(
    path: str | None, frontmatter: Mapping[str, object] | FrontmatterError | None
) -> tuple[CheckOutcome, Mapping[str, object]]:
    if frontmatter is None:
        return CheckOutcome.PASSED, {"design_path": path, "review": None}
    if isinstance(frontmatter, FrontmatterError):
        return CheckOutcome.ERRORED, {"design_path": path, "error": frontmatter.reason}
    review = frontmatter.get(KEY_REVIEW)
    text = None if review is None else str(review)
    hatch = text is not None and text.strip().lower() == REVIEW_NONE
    outcome = CheckOutcome.FAILED if hatch else CheckOutcome.PASSED
    return outcome, {"design_path": path, "review": text}


def _effective_date(
    path: str | None,
    frontmatter: Mapping[str, object] | FrontmatterError | None,
    effective_date: str | ReadFailure,
) -> tuple[CheckOutcome, Mapping[str, object]]:
    if isinstance(effective_date, ReadFailure):
        return CheckOutcome.ERRORED, {
            "design_path": path,
            "error": effective_date.detail,
        }
    cutoff = effective_date.strip()
    examined: dict[str, object] = {"design_path": path, "effective_date": cutoff}
    if cutoff == "":
        return CheckOutcome.PASSED, examined
    if not (
        cutoff.isascii() and cutoff.isdigit() and len(cutoff) == EFFECTIVE_DATE_DIGITS
    ):
        examined["error"] = "the effective date is not eight digits (YYYYMMDD)"
        return CheckOutcome.ERRORED, examined
    if frontmatter is None:
        return CheckOutcome.PASSED, examined
    if isinstance(frontmatter, FrontmatterError):
        examined["error"] = frontmatter.reason
        return CheckOutcome.ERRORED, examined
    created = frontmatter.get(KEY_DATE_CREATED)
    if created is None:
        examined["error"] = (
            "the design has no dateCreated while an effective date is set"
        )
        return CheckOutcome.ERRORED, examined
    examined["date_created"] = str(created)
    before = str(created) < cutoff
    return (CheckOutcome.FAILED if before else CheckOutcome.PASSED), examined
