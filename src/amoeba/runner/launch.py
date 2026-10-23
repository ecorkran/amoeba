"""Run ids and the detached launch of ``sq run``."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Final

#: Squadron's run id rule: letters, digits, ``.``, ``_`` and ``-``, a letter or
#: digit first, at most 128 characters.
SQUADRON_RUN_ID_PATTERN: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

#: What every Amoeba-minted run id starts with, so it is recognizable in
#: ``sq runs list``.
RUN_ID_PREFIX: Final = "amoeba-"

#: The timestamp part of a minted id.
RUN_ID_TIMESTAMP_FORMAT: Final = "%Y%m%dT%H%M%SZ"

#: How many hex characters of a ``uuid4`` a minted id carries.
RUN_ID_RANDOM_HEX_LENGTH: Final = 12


def mint_run_id(now: datetime) -> str:
    """Return ``amoeba-<UTC timestamp>-<random hex>`` for a launch at ``now``.

    Sortable by time and unique per call. ``now`` must be timezone-aware; it is
    converted to UTC. The pattern is checked by tests, not at runtime.
    """
    stamp = now.astimezone(UTC).strftime(RUN_ID_TIMESTAMP_FORMAT)
    suffix = uuid.uuid4().hex[:RUN_ID_RANDOM_HEX_LENGTH]
    return f"{RUN_ID_PREFIX}{stamp}-{suffix}"
