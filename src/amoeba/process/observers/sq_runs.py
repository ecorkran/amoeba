"""The Squadron runs-directory observer.

Answers, for a journaled ``sq_run`` command: did Squadron actually start this
run? The question is answered by scanning the runs directory and matching run
files against the entry — never by launching anything.

The matching rule (D5) is biased entirely toward escalation. A run is a
candidate only when **all four** conditions hold, and the only path to
``Adopt`` is exactly one candidate. Zero candidates, several candidates, an
unreadable directory, or a parse failure all become ``Unknown``, which blocks
the node for a human. A wrong adoption is silent; a human interruption is not.

Subset matching on ``params`` is not looseness for its own sake: Squadron
persists the pipeline definition's defaults *merged with* the caller's
overrides, so exact equality would never match. The looseness is safe because a
wider net can only turn a would-be single match into several — and several is
escalated, never guessed.

No code here compares an upstream version number. The run file's own
``schema_version`` is recorded on adoption as provenance and nothing more.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from amoeba.process.recovery import Adopt, Observation, Unknown
from amoeba.store.journal_models import JournalEntry

logger = logging.getLogger(__name__)

#: Journal parameter keys this observer matches on. Both are required at issue
#: time by ``REQUIRED_PARAMETER_KEYS``, so an entry always carries them.
PARAM_PIPELINE = "pipeline"
PARAM_PARAMS = "params"

#: Result keys recorded on adoption. Defined once so the observer that writes
#: them and anything reading them back agree by construction.
RESULT_RUN_ID = "run_id"
RESULT_SCHEMA_VERSION = "schema_version"
RESULT_STATUS = "status"


class SquadronRun(BaseModel):
    """The six header fields of a Squadron run-state file.

    Unknown fields are **ignored**, so an upstream that adds fields does not
    break recovery. A missing required field is a validation error, which the
    caller turns into a parse failure — never an exception escaping the
    observer, and never a match.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    schema_version: int
    run_id: str
    pipeline: str
    params: Mapping[str, object]
    started_at: datetime
    status: str


def parse_run_file(path: Path) -> SquadronRun | None:
    """Parse one run file, or return ``None`` if it cannot be parsed.

    Returns ``None`` — rather than raising — for every expected failure: an
    unreadable file, malformed JSON, or a missing required field. The caller
    counts these and names them in the escalation reason, so a parse failure is
    never silently skipped into a confident answer.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        # Specific: a file that vanished or cannot be read between listing and
        # reading. Counted and surfaced by the caller, not swallowed.
        logger.warning("cannot read squadron run file %s", path, exc_info=True)
        return None

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Squadron writes atomically (temp file, then rename), so a partially
        # written file should never be observed; this is still reported rather
        # than assumed impossible.
        logger.warning("squadron run file %s is not valid JSON", path)
        return None

    try:
        return SquadronRun.model_validate(payload)
    except ValidationError:
        # Specific: a required field is missing or mistyped. This is upstream
        # drift, which must degrade to a human escalation rather than a match.
        logger.warning("squadron run file %s is missing a required field", path)
        return None


class RunsDirectoryScan:
    """One pass over the runs directory, parsed once per recovery.

    Recovery reconciles many entries against the same directory, so the scan is
    performed once and reused rather than repeated per entry. ``unreadable`` is
    ``True`` when the directory itself could not be listed, which is an answer
    (``Unknown``) rather than an error.
    """

    def __init__(
        self,
        runs: tuple[SquadronRun, ...],
        unparseable: tuple[str, ...],
        unreadable: bool,
    ) -> None:
        self.runs = runs
        self.unparseable = unparseable
        self.unreadable = unreadable


def scan_runs_directory(runs_dir: Path) -> RunsDirectoryScan:
    """Read and parse every run file in the directory, once.

    A missing or unlistable directory is reported, not raised: the observer
    turns it into ``Unknown`` for every entry it is asked about.
    """
    if not runs_dir.is_dir():
        logger.warning("squadron runs directory %s does not exist", runs_dir)
        return RunsDirectoryScan(runs=(), unparseable=(), unreadable=True)

    try:
        paths = sorted(runs_dir.glob("*.json"))
    except OSError:
        # Specific: the directory exists but cannot be listed (permissions, a
        # broken mount). Reported as unreadable, which escalates.
        logger.warning(
            "cannot list squadron runs directory %s", runs_dir, exc_info=True
        )
        return RunsDirectoryScan(runs=(), unparseable=(), unreadable=True)

    parsed: list[SquadronRun] = []
    unparseable: list[str] = []
    for path in paths:
        run = parse_run_file(path)
        if run is None:
            unparseable.append(path.name)
        else:
            parsed.append(run)

    return RunsDirectoryScan(
        runs=tuple(parsed), unparseable=tuple(unparseable), unreadable=False
    )


def _params_are_subset(
    journaled: Mapping[str, object], persisted: Mapping[str, object]
) -> bool:
    """Whether every journaled param appears in the run with an equal value.

    Subset, not equality: Squadron persists definition defaults merged with the
    caller's overrides, so the persisted mapping is normally a superset.
    """
    return all(
        key in persisted and persisted[key] == value for key, value in journaled.items()
    )


def _journaled_params(entry: JournalEntry) -> Mapping[str, object]:
    """The entry's journaled params, or an empty mapping if malformed.

    ``journal_issue`` requires the key, so absence means the stored value was
    not a mapping — which cannot match anything and therefore escalates.
    """
    params = entry.parameters.get(PARAM_PARAMS)
    if isinstance(params, Mapping):
        narrowed: dict[str, object] = dict(params)  # pyright: ignore[reportUnknownArgumentType]
        return narrowed
    return {}


class SquadronRunsObserver:
    """Matches journaled ``sq_run`` commands against Squadron's run files."""

    def __init__(
        self,
        runs_dir: Path,
        *,
        clock_tolerance_seconds: float,
        claimed_run_ids: Mapping[str, str] | None = None,
        scan: RunsDirectoryScan | None = None,
    ) -> None:
        """Build an observer over one runs directory.

        Args:
            runs_dir: The directory Squadron writes run-state files into.
            clock_tolerance_seconds: How much earlier than the entry's
                ``issued_at`` a run may have started and still be a candidate,
                absorbing clock skew between the two writers.
            claimed_run_ids: Run ids already recorded in another journal
                entry's result, mapped to that entry's id. Such a run is not a
                candidate for any other entry.
            scan: A pre-computed directory scan. Supplied by recovery so the
                directory is read **once per pass** rather than once per entry;
                when omitted, the scan happens on first use.
        """
        self._runs_dir = runs_dir
        self._clock_tolerance = timedelta(seconds=clock_tolerance_seconds)
        self._claimed_run_ids = dict(claimed_run_ids or {})
        self._scan = scan

    @property
    def scan(self) -> RunsDirectoryScan:
        """The directory scan, performed once and reused."""
        if self._scan is None:
            self._scan = scan_runs_directory(self._runs_dir)
        return self._scan

    def observe(self, entry: JournalEntry) -> Observation:
        """Report what the runs directory shows for one journaled command."""
        scan = self.scan
        if scan.unreadable:
            return Unknown(
                reason=(
                    f"squadron runs directory {self._runs_dir} is missing or unreadable"
                )
            )

        candidates = tuple(self._candidates(entry, scan.runs))

        if len(candidates) == 1:
            matched = candidates[0]
            return Adopt(
                result={
                    RESULT_RUN_ID: matched.run_id,
                    RESULT_SCHEMA_VERSION: matched.schema_version,
                    RESULT_STATUS: matched.status,
                }
            )

        return Unknown(
            reason=self._unmatched_reason(len(candidates), scan.unparseable),
            candidates=tuple(run.run_id for run in candidates),
        )

    def _candidates(
        self, entry: JournalEntry, runs: Iterable[SquadronRun]
    ) -> Iterable[SquadronRun]:
        """Every run satisfying all four of D5's conditions."""
        journaled_pipeline = entry.parameters.get(PARAM_PIPELINE)
        if not isinstance(journaled_pipeline, str):
            return ()

        # Squadron lower-cases the pipeline before persisting it, so the
        # comparison is lower-cased on both sides rather than assuming the
        # journaled value already is.
        pipeline = journaled_pipeline.lower()
        journaled_params = _journaled_params(entry)
        earliest = self._earliest_start(entry)

        return [
            run
            for run in runs
            if run.pipeline.lower() == pipeline
            and _params_are_subset(journaled_params, run.params)
            and (earliest is None or run.started_at >= earliest)
            and run.run_id not in self._claimed_run_ids
        ]

    def _earliest_start(self, entry: JournalEntry) -> datetime | None:
        """The earliest start time a candidate may carry, or ``None``.

        ``None`` when the entry has no ``issued_at`` to compare against, which
        leaves the other three conditions to do the filtering.
        """
        if entry.issued_at is None:
            return None
        return entry.issued_at - self._clock_tolerance

    def _unmatched_reason(self, count: int, unparseable: tuple[str, ...]) -> str:
        """Compose an escalation reason naming the count and any bad files."""
        if count == 0:
            reason = "no squadron run matches this entry"
        else:
            reason = f"{count} squadron runs match this entry"

        if unparseable:
            reason += (
                f"; {len(unparseable)} run file(s) could not be parsed: "
                f"{', '.join(unparseable)}"
            )
        return reason
