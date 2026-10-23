"""The fault vocabulary the Runner's modules share.

Defined once so the observe, act and tenant modules import the same values.
Escalation writes join this module in a later task.
"""

from __future__ import annotations

import sqlite3
from enum import StrEnum
from typing import Final

from amoeba.store import (
    StoreBusyError,
    StoreCorruptError,
    StorePermissionError,
    StoreSchemaError,
)


class FaultKind(StrEnum):
    """Why the Runner raised an escalation or blocked a node."""

    RUN_OBSERVATION_FAILED = "run_observation_failed"
    LAUNCH_OVERDUE = "launch_overdue"
    CF_PROBE_FAILED = "cf_probe_failed"
    UNEXPECTED_FAULT = "unexpected_fault"


class LaunchFailure(StrEnum):
    """How a detached launch failed before its run was confirmed."""

    SPAWN_ERROR = "spawn_error"
    EXITED_BEFORE_LINE = "exited_before_line"
    USAGE_ERROR = "usage_error"


#: A failure of the store itself. These are never a per-project fault: the
#: Runner re-raises them so the process stops rather than running blind.
STORE_FAILURES: Final = (
    StoreBusyError,
    StoreCorruptError,
    StorePermissionError,
    StoreSchemaError,
    sqlite3.Error,
)
