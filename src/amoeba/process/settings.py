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
from pathlib import Path

#: Where Squadron writes its run-state files. Not overridable by environment —
#: Squadron itself offers no such override, and inventing one here would be a
#: second source of truth. The CLI's ``--sq-runs-dir`` flag overrides it.
DEFAULT_SQ_RUNS_DIR = Path.home() / ".config" / "squadron" / "runs"


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
        clock_tolerance_seconds: How much earlier than a journal entry's
            ``issued_at`` a Squadron run may have started and still be a
            candidate, absorbing clock skew between the two writers.
        cf_timeout_seconds: How long to wait for a ``cf`` invocation before
            treating it as unobservable.
        sq_runs_dir: The Squadron runs directory the observer scans.
        inbox_batch_size: The most inbox files one ``InboxTenant`` tick
            handles. Each is one short transaction and ``stop_requested`` is
            checked between them, so this bounds a tick, not shutdown latency.
        inbox_max_attempts: How many consecutive failed applies of one file
            before it is parked in ``inbox/failed/``. Small on purpose: the
            first failures stop the process so a sick store stays loud; this
            bounds that loop rather than retrying a corrupt store into working.
    """

    idle_interval_seconds: float = 1.0
    shutdown_grace_seconds: float = 10.0
    stop_timeout_seconds: float = 30.0
    clock_tolerance_seconds: float = 5.0
    cf_timeout_seconds: float = 10.0
    sq_runs_dir: Path = DEFAULT_SQ_RUNS_DIR
    inbox_batch_size: int = 100
    inbox_max_attempts: int = 3
