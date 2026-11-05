"""Settings of the request live tier (slice 180, D10), read from the environment.

Pure and importable by unit tests; ``tests/live/request_run/conftest.py`` calls it
at collection. Nothing is skipped and nothing has a default: a missing or invalid
variable fails with its name. The shared rules live in ``live_settings``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from live_settings import read_cost, require_variable

REQUEST_MODEL_VARIABLE: Final = "AMOEBA_LIVE_REQUEST_MODEL"
REQUEST_MAX_COST_VARIABLE: Final = "AMOEBA_LIVE_REQUEST_MAX_COST_USD"


@dataclass(frozen=True)
class RequestLiveSettings:
    request_model: str
    max_cost_usd: float


def read_request_live_settings(environ: Mapping[str, str]) -> RequestLiveSettings:
    """Read the two collection-time variables.

    Raises:
        pytest.UsageError: For the first unset variable, or a cost that is not a
            positive number, naming the variable.
    """
    return RequestLiveSettings(
        request_model=require_variable(environ, REQUEST_MODEL_VARIABLE),
        max_cost_usd=read_cost(environ, REQUEST_MAX_COST_VARIABLE),
    )
