"""``CFWatchTenant`` — notices Context Forge pointer moves nobody told Amoeba about.

Context Forge keeps every project in one file, replaced by temp-file-and-rename
on each write, so any write gives it a new inode. Once per
``cf_scan_interval_seconds`` the tenant takes one ``stat`` of that file. Only
when the signature or the set of links changed does it read the file and compare
each linked project's projection with that link's stored snapshots; a link whose
projection moved gets a new snapshot, and migration 008's trigger puts the
change on the feed. Nothing is held in memory that a restart cannot rebuild: the
baseline is always the stored snapshot.

A file Amoeba cannot read, or no longer recognizes, is recorded as an outcome
once per transition and logged once going bad and once recovering; the process
keeps running. A store that cannot record a snapshot does stop it: the error is
logged and re-raised. No tick starts a subprocess.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol

from amoeba.process.settings import ProcessSettings
from amoeba.store import CFSnapshot, CFSnapshotInput, CFSnapshotOutcome, Store
from amoeba.upstream.context_forge import (
    CFProjectState,
    CFReadFailure,
    CFReadOutcome,
    diff_states,
    parse,
)

logger = logging.getLogger(__name__)

#: How this tenant appears in logs, including a grace-expiry ERROR.
CF_WATCH_TENANT_NAME: Final = "cf-watch"

#: The one place that knows both vocabularies: the parser's failure words are
#: strings to the store, which imports nothing from ``amoeba.upstream``.
_PARSER_OUTCOMES: Final = {
    CFReadOutcome.UNRECOGNIZED: CFSnapshotOutcome.UNRECOGNIZED,
    CFReadOutcome.MISSING: CFSnapshotOutcome.MISSING,
}

type LinkKey = tuple[str, str]
type Signature = tuple[int, int, int]
#: What one ``stat`` gave: the signature, or the detail of the OS error.
type FileState = Signature | str


class CFWatchHost(Protocol):
    """What the tenant needs from its host — ``ResidentProcess`` provides it."""

    @property
    def settings(self) -> ProcessSettings: ...

    @property
    def stop_requested(self) -> bool: ...

    @property
    def project_ids(self) -> tuple[str, ...]: ...

    def store_for(self, project_id: str) -> Store: ...


@dataclass(frozen=True)
class _Failure:
    """A link that could not be observed, in the store's vocabulary."""

    outcome: CFSnapshotOutcome
    detail: str
    file_wide: bool


type Observation = CFProjectState | _Failure


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _os_detail(error: OSError) -> str:
    return f"{type(error).__name__}: {error.strerror}"


class CFWatchTenant:
    """Watches ``projects.json`` for every link of every open project."""

    def __init__(
        self,
        *,
        version_label: str,
        data_file: Path,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """Build the tenant.

        Args:
            version_label: The ``cf --version`` label captured once at start-up,
                or the explicit unavailable marker. Stored on every snapshot.
            data_file: The resolved path of Context Forge's ``projects.json``.
            clock: Monotonic seconds, for the check cadence.
            wall_clock: When the file was read, recorded as ``observed_at``.
        """
        self._version_label = version_label
        self._data_file = data_file
        self._clock = clock
        self._wall_clock = wall_clock
        self._last_check: float | None = None
        # (file state, links) at the last check that recorded everything.
        self._remembered: tuple[FileState, tuple[LinkKey, ...]] | None = None
        # The last file-wide problem logged; absent means the file is fine.
        self._file_problem: str | None = None
        self._announced = False

    @property
    def name(self) -> str:
        return CF_WATCH_TENANT_NAME

    @property
    def version_label(self) -> str:
        return self._version_label

    @property
    def data_file(self) -> Path:
        return self._data_file

    def tick(self, host: CFWatchHost) -> bool:
        """Check the file, at most once per scan interval.

        Returns:
            Whether anything was written.

        Raises:
            Exception: Whatever the store raised while recording; logged first.
        """
        if not self._announced:
            logger.info("watching Context Forge projects at %s", self._data_file)
            self._announced = True
        now = self._clock()
        interval = host.settings.cf_scan_interval_seconds
        if self._last_check is not None and now - self._last_check < interval:
            return False
        self._last_check = now

        links = self._links(host)
        if not links:
            return False
        file_state = self._stat()
        if (file_state, links) == self._remembered:
            return False
        return self._check(host, links, file_state)

    # ----------------------------------------------------------------------
    # The file
    # ----------------------------------------------------------------------

    def _links(self, host: CFWatchHost) -> tuple[LinkKey, ...]:
        return tuple(
            (project_id, link.cf_project_id)
            for project_id in host.project_ids
            for link in host.store_for(project_id).cf_links(project_id)
        )

    def _stat(self) -> FileState:
        try:
            status = self._data_file.stat()
        except OSError as error:
            # Specific: absent, denied, or any other OS error is an outcome.
            return _os_detail(error)
        return (status.st_ino, status.st_size, status.st_mtime_ns)

    def _read(self, file_state: FileState) -> bytes | str:
        """The file's bytes, or the detail of why they cannot be had."""
        if isinstance(file_state, str):
            return file_state
        try:
            return self._data_file.read_bytes()
        except OSError as error:
            # Specific: stat worked and the read did not (permissions). An
            # outcome, not a crash.
            return _os_detail(error)

    # ----------------------------------------------------------------------
    # One check
    # ----------------------------------------------------------------------

    def _check(
        self, host: CFWatchHost, links: tuple[LinkKey, ...], file_state: FileState
    ) -> bool:
        """Read once, then bring every link up to date.

        The remembered signature is the one taken before the read (D1), so a
        file replaced in between is seen as new on the next tick.
        """
        content = self._read(file_state)
        observed_at = self._wall_clock()
        worked = False
        file_problem: str | None = None
        for project_id, cf_project_id in links:
            if host.stop_requested:
                return worked
            observation = self._observe(content, cf_project_id)
            if isinstance(observation, _Failure) and observation.file_wide:
                file_problem = observation.detail
            worked = (
                self._update_link(
                    host.store_for(project_id),
                    project_id,
                    cf_project_id,
                    observation,
                    observed_at,
                )
                or worked
            )
        # A failed read is not remembered: a permission fix leaves the
        # signature unchanged, so the next tick must try again.
        if isinstance(content, bytes) or isinstance(file_state, str):
            self._remembered = (file_state, links)
        self._log_file_problem(file_problem)
        return worked

    def _observe(self, content: bytes | str, cf_project_id: str) -> Observation:
        if isinstance(content, str):
            return _Failure(CFSnapshotOutcome.UNREADABLE, content, file_wide=True)
        parsed = parse(content, cf_project_id)
        if isinstance(parsed, CFReadFailure):
            return _Failure(
                _PARSER_OUTCOMES[parsed.outcome], parsed.detail, parsed.file_wide
            )
        return parsed

    def _log_file_problem(self, problem: str | None) -> None:
        """One ERROR as the file goes bad (or goes bad differently), one INFO after."""
        if problem is not None and problem != self._file_problem:
            logger.error("Context Forge projects file is unusable: %s", problem)
        elif problem is None and self._file_problem is not None:
            logger.info("Context Forge projects file is usable again")
        self._file_problem = problem

    # ----------------------------------------------------------------------
    # One link
    # ----------------------------------------------------------------------

    def _update_link(
        self,
        store: Store,
        project_id: str,
        cf_project_id: str,
        observation: Observation,
        observed_at: datetime,
    ) -> bool:
        """Record a snapshot if this link moved; ``False`` when nothing changed."""
        try:
            latest, baseline = store.latest_cf_snapshots(project_id, cf_project_id)
            snapshot = self._snapshot_for(
                project_id, cf_project_id, observation, observed_at, latest, baseline
            )
            if snapshot is None:
                return False
            store.record_cf_snapshot(snapshot)
        except Exception:
            logger.exception(
                "cannot record Context Forge snapshot for %s in project %s",
                cf_project_id,
                project_id,
            )
            raise
        return True

    def _snapshot_for(
        self,
        project_id: str,
        cf_project_id: str,
        observation: Observation,
        observed_at: datetime,
        latest: CFSnapshot | None,
        baseline: CFSnapshot | None,
    ) -> CFSnapshotInput | None:
        """The row to write, or ``None`` (D3, D4).

        A state is written when it differs from the last ``observed`` one, when
        it is the link's first, or when it follows a failure (recovery is
        visible even if nothing moved). A failure is written only when its
        outcome or detail differs from the link's latest row.
        """
        if isinstance(observation, _Failure):
            if latest is not None and (latest.outcome, latest.detail) == (
                observation.outcome,
                observation.detail,
            ):
                return None
            return CFSnapshotInput(
                project_id=project_id,
                cf_project_id=cf_project_id,
                outcome=observation.outcome,
                state=None,
                changed=None,
                detail=observation.detail,
                cf_updated_at=None,
                cf_version_label=self._version_label,
                observed_at=observed_at,
            )
        changes = diff_states(_previous_state(baseline), observation)
        steady = latest is not None and latest.outcome is CFSnapshotOutcome.OBSERVED
        if steady and not changes:
            return None
        return CFSnapshotInput(
            project_id=project_id,
            cf_project_id=cf_project_id,
            outcome=CFSnapshotOutcome.OBSERVED,
            state=observation.to_json(),
            changed=[change.to_json() for change in changes],
            detail=None,
            cf_updated_at=observation.cf_updated_at,
            cf_version_label=self._version_label,
            observed_at=observed_at,
        )


def _previous_state(baseline: CFSnapshot | None) -> CFProjectState | None:
    if baseline is None:
        return None
    if baseline.state is None:
        raise ValueError(f"observed snapshot {baseline.id} has no state")
    return CFProjectState.from_json(baseline.state, baseline.cf_updated_at)
