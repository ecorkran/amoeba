"""Every tunable the resident process has, defined exactly once.

There is no ``or``-style fallback default at any call site: a caller that wants
a different value constructs a different :class:`ProcessSettings`. That is what
makes changing a default a one-line edit here rather than a search for every
place the literal was repeated.

Deliberately **no environment reads**. ``AMOEBA_STORE_DIR`` in
``amoeba.store.paths`` stays the project's only one (D3), so there is never a
second source of truth to reconcile. The CLI exposes these as flags instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

#: Where Squadron writes its run-state files. Not overridable by environment —
#: Squadron itself offers no such override, and inventing one here would be a
#: second source of truth. The CLI's ``--sq-runs-dir`` flag overrides it.
DEFAULT_SQ_RUNS_DIR = Path.home() / ".config" / "squadron" / "runs"

#: Where Context Forge keeps ``projects.json`` by default: CF's own default. Not
#: overridable by environment (``CONTEXT_FORGE_DATA_DIR`` is deliberately not
#: read): the shell that starts Amoeba need not match the CF clients'. The CLI's
#: ``--cf-data-dir`` flag overrides it.
DEFAULT_CF_DATA_DIR = Path.home() / ".config" / "context-forge"

#: The routing table shipped in the package, resolved once. The CLI's
#: ``--routing-table`` flag points at another file.
DEFAULT_ROUTING_TABLE_PATH = Path(
    str(
        resources.files("amoeba").joinpath(
            "runner", "routing", "tables", "default.yaml"
        )
    )
)


@dataclass(frozen=True)
class ProcessSettings:
    """Tunables for the resident process, its loop, and its observers.

    Attributes:
        idle_interval_seconds: How long the loop waits on the stop event when
            no tenant reported work. Not a poll interval in the busy sense —
            the wait ends immediately when stop is requested.
        shutdown_grace_seconds: How long a stopping process waits for the
            *current* tick to return before logging at ERROR and exiting. It
            bounds one tick, not the whole shutdown.
        stop_timeout_seconds: How long ``amoeba stop`` waits for the lock to be
            released after signalling, before reporting a stop timeout. Never
            followed by an escalation to ``SIGKILL``.
        clock_tolerance_seconds: Used only by legacy matching (entries journaled
            before slice 120, which carry no run id). How much earlier than a
            journal entry's ``issued_at`` a Squadron run may have started and
            still be a candidate, absorbing clock skew between the two writers.
        cf_timeout_seconds: How long to wait for a ``cf`` invocation before
            treating it as unobservable.
        sq_runs_dir: Used only by legacy matching: the Squadron runs directory
            scanned for entries journaled before slice 120. Entries with a run
            id, and pruning, never read it.
        inbox_batch_size: The most inbox files one ``InboxTenant`` tick
            handles. Each is one short transaction and ``stop_requested`` is
            checked between them, so this bounds a tick, not shutdown latency.
        inbox_max_attempts: How many consecutive failed applies of one file
            before it is parked in ``inbox/failed/``. Small on purpose: the
            first failures stop the process so a sick store stays loud; this
            bounds that loop rather than retrying a corrupt store into working.
        review_scan_interval_seconds: How often the review-detection tenant
            scans watched directories. A file settles across two scans, so
            detection latency is about two intervals.
        sq_timeout_seconds: How long to wait for a start-up ``sq`` call, which
            includes the Runner's ``sq`` probe. Tick-time calls are bounded by
            ``tick_call_timeout_seconds`` instead.
        cf_data_dir: The directory holding Context Forge's ``projects.json``,
            which the Context Forge watch reads. Resolved once at start-up and
            logged by the watch.
        cf_scan_interval_seconds: How often the Context Forge watch takes one
            ``stat`` of ``projects.json``. A pointer move is a human-paced
            event, so this bounds how stale the Runner's view can be. No flag.
        launch_grace_seconds: How long after a launch was issued Squadron may
            still be creating the run, so that "no run state yet" is not proof
            the launch never happened. Recovery reads it to decide ``not_applied``
            for an ``sq_run`` entry that carries a run id; the Runner reads the
            same field to confirm launches.
        tick_deadline_seconds: How long one Runner tick may spend before it
            stops starting new calls. Checked before every subprocess call; it
            bounds when a call may begin, not how long a started call runs.
        tick_call_timeout_seconds: The longest a single Runner subprocess call
            may run. The default is larger than ``tick_deadline_seconds``, so a
            call that starts just inside the deadline has room to finish; only
            ``tick_call_timeout_seconds < shutdown_grace_seconds`` is enforced.
        run_poll_interval_seconds: The least time between two polls of the same
            launched run by the Runner.
        plan_read_interval_seconds: The least time between two plan reads of the
            same linked Context Forge project. A change in the project's CF
            snapshot triggers an earlier read.
        routing_table_path: The routing table file, loaded and validated once at
            start-up. Defaults to the table shipped in the package.
    """

    idle_interval_seconds: float = 1.0
    shutdown_grace_seconds: float = 10.0
    stop_timeout_seconds: float = 30.0
    clock_tolerance_seconds: float = 5.0
    cf_timeout_seconds: float = 10.0
    sq_runs_dir: Path = DEFAULT_SQ_RUNS_DIR
    inbox_batch_size: int = 100
    inbox_max_attempts: int = 3
    review_scan_interval_seconds: float = 2.0
    sq_timeout_seconds: float = 10.0
    cf_data_dir: Path = DEFAULT_CF_DATA_DIR
    cf_scan_interval_seconds: float = 1.0
    launch_grace_seconds: float = 60.0
    tick_deadline_seconds: float = 5.0
    tick_call_timeout_seconds: float = 8.0
    run_poll_interval_seconds: float = 15.0
    plan_read_interval_seconds: float = 30.0
    routing_table_path: Path = DEFAULT_ROUTING_TABLE_PATH
