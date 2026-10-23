"""One tick's budget. The project tick itself joins this module later."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Protocol


class TickResult(StrEnum):
    """How a stage or project ended."""

    #: Ran to the end.
    COMPLETE = "complete"
    #: Stopped early because the budget refused a call; resume next tick.
    CUT_OFF = "cut_off"


class StopSignal(Protocol):
    """The part of the host the budget reads."""

    @property
    def stop_requested(self) -> bool:
        """Whether the process has been asked to stop."""
        ...


class TickBudget:
    """Whether a tick may still start a subprocess call (D10).

    Checked before every call, ``Popen`` included. It bounds when a call may
    begin, not how long one runs; ``tick_call_timeout_seconds`` bounds that.
    """

    def __init__(
        self, deadline: float, host: StopSignal, clock: Callable[[], float]
    ) -> None:
        """Build a budget.

        Args:
            deadline: The monotonic time after which no call may start.
            host: Consulted for a stop request.
            clock: A monotonic clock, injected so tests never sleep.
        """
        self._deadline = deadline
        self._host = host
        self._clock = clock

    def allows_call(self) -> bool:
        """True while the deadline has not passed and no stop is requested."""
        return self._clock() < self._deadline and not self._host.stop_requested
