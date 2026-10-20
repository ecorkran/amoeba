"""The proof's scenario, as data (slice 110, D4)."""

from __future__ import annotations

from datetime import timedelta

#: The two projects the scenario runs across. `beta` takes part in only three steps.
ALPHA = "alpha"
BETA = "beta"

#: How far before its step's wall-clock time every paused run file the stand-in
#: writes is dated. Far past any retention pruning could plausibly use, so the
#: proof asserts which runs are selected and kept, never the retention itself.
STANDIN_RUN_AGE = timedelta(days=365)
