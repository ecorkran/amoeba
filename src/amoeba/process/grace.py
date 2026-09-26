"""The shutdown grace period: a watchdog that bounds how long stop can take.

Extracted from ``host.py`` so the loop module stays within its line budget. The
watchdog owns no store and only observes; the loop it bounds runs on the
caller's thread.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)

#: How often the watchdog checks whether the loop finished before stop was
#: requested, so it does not outlive a loop that returned on its own.
_POLL_SECONDS = 0.05


def run_with_grace(
    loop: Callable[[], None],
    *,
    stop_event: threading.Event,
    grace_seconds: float,
    current_tenant: Callable[[], str],
    on_expiry: Callable[[], None] | None,
) -> bool:
    """Run ``loop`` on **this** thread, with a watchdog bounding shutdown.

    The loop stays on the calling thread because the stores live there:
    ``sqlite3`` connections may only be used by the thread that created them,
    so moving the loop off this thread would move every tenant write off it
    too.

    The watchdog starts timing when ``stop_event`` is set and, if the loop has
    not returned once ``grace_seconds`` pass, logs at ERROR naming the tenant.
    A tenant mid-tick is **abandoned in place**, never interrupted — safe
    precisely because of crash-only: an abandoned tick is indistinguishable
    from ``kill -9`` and is reconciled by the same recovery path on the next
    start. ``on_expiry`` then runs on the watchdog thread; the CLI passes
    :func:`abandon_process`, because a tenant that never returns would
    otherwise hold the process forever.

    Returns:
        Whether the grace period expired before the loop returned.
    """
    expired = threading.Event()
    finished = threading.Event()

    def _watch() -> None:
        # Wait for shutdown to begin; nothing is bounded before that, because
        # there is no per-tick timeout by decision.
        while not stop_event.wait(timeout=_POLL_SECONDS):
            if finished.is_set():
                return

        if finished.wait(timeout=grace_seconds):
            return

        expired.set()
        logger.error(
            "tenant %r did not return within the %ss grace period; abandoning it",
            current_tenant(),
            grace_seconds,
        )
        if on_expiry is not None:
            on_expiry()

    watchdog = threading.Thread(target=_watch, name="amoeba-grace", daemon=True)
    watchdog.start()
    try:
        loop()
    finally:
        finished.set()
    return expired.is_set()


def abandon_process(exit_status: int) -> None:
    """Exit immediately, abandoning a tenant that will not return.

    ``os._exit`` is deliberate: the loop thread is stuck inside a tenant, so no
    orderly unwinding is possible, and any ``atexit`` or buffered-output
    handling would run against a thread that is not coming back. The lock is
    released by the kernel, and the PID file left behind is harmless because
    nothing trusts it — exactly the state a ``kill -9`` leaves, and the one the
    next start recovers from.

    The status is supplied by the caller, so this module names no exit code of
    its own — mapping a lifecycle failure to a status is the CLI's job.
    """
    sys.stderr.flush()
    sys.stdout.flush()
    os._exit(exit_status)
