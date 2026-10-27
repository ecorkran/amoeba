"""The Runner's check vocabulary: names, ids and provenance, defined once (slice 128).

The ungate hatches (D4) and the gate disagreement (D7) share this, so a check id or a
provenance is never spelled twice. Names are data and never logic (evidence contract).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from amoeba.store import Provenance, RecordSource

#: The ``upstream`` of every check the Runner records: Amoeba itself.
RUNNER_UPSTREAM: Final = "amoeba"

_CHECK_ID_PREFIX: Final = "chk"


class RunnerCheck(StrEnum):
    """The checks the Runner records about a slice."""

    #: The design declares ``review: none`` (D4).
    UNGATE_REVIEW_NONE = "ungate_review_none"
    #: The design was created before the review gate's effective date (D4).
    UNGATE_EFFECTIVE_DATE = "ungate_effective_date"
    #: The store accepted a step whose CF gate still fails (D7).
    CF_GATE_ACCEPT_DISAGREEMENT = "cf_gate_accept_disagreement"


def check_id(entry_id: str, name: RunnerCheck) -> str:
    """The id of ``name``'s check for one journal entry: ``chk-<entry id>-<name>``.

    Fixed by the entry and the name, so a repeat after a crash is ``record_check``'s
    retry and keeps the first record.
    """
    return f"{_CHECK_ID_PREFIX}-{entry_id}-{name.value}"


def runner_provenance(
    amoeba_version: str, source: RecordSource, source_path: str | None
) -> Provenance:
    """Where a Runner check came from: Amoeba, at its version label."""
    return Provenance(
        upstream=RUNNER_UPSTREAM,
        upstream_version=amoeba_version,
        source=source,
        source_path=source_path,
    )
