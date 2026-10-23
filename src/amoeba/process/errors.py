"""Typed lifecycle failures raised by the resident process.

Separate from ``host.py`` so the CLI's process-boundary handler can import the
error vocabulary without importing the loop, and so ``host.py`` stays near its
line budget.

These carry **no exit codes**. Mapping a lifecycle failure to an exit status is
the CLI's job, at the one documented process boundary; nothing under
``amoeba.process`` references ``ExitCode``.
"""

from __future__ import annotations


class ProcessError(Exception):
    """Base class for the lifecycle failures the resident process raises."""


class AlreadyRunningError(ProcessError):
    """Another resident process holds this supervisor's instance lock.

    The running process is not disturbed in any way.
    """


class StartupFailedError(ProcessError):
    """Startup could not complete; the loop was never entered.

    Raised when a store cannot be opened or recovery cannot complete for
    **any** project. The process never skips a project and never falls back to
    a different store: running while blind to one project is worse than not
    running.
    """


class UpstreamShapeError(ProcessError):
    """An upstream tool lacks a shape the Runner needs.

    Raised when a probe finds that ``sq`` or ``cf`` is missing a command or
    option the Runner depends on. The tool is present but unusable, so the
    process stops rather than running with a launch surface it cannot trust.
    """


class GraceExpiredError(ProcessError):
    """A tenant did not return within the shutdown grace period.

    The stores are closed and the tenant is abandoned mid-tick rather than
    interrupted. That is safe precisely because of crash-only: an abandoned
    tick is indistinguishable from ``kill -9`` and is reconciled by the same
    recovery path on the next start. The process never escalates to killing
    its own thread.
    """

    def __init__(self, tenant_name: str) -> None:
        super().__init__(
            f"tenant {tenant_name!r} did not return within the grace period"
        )
        self.tenant_name = tenant_name
