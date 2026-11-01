"""Settings of the live tier (slice 140, D10), read from the environment.

Pure and importable by unit tests; ``tests/live/conftest.py`` calls it at
collection. Nothing is skipped and nothing has a default: a missing or invalid
variable fails with its name.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

import pytest

ANSWER_MODEL_VARIABLE: Final = "AMOEBA_LIVE_ANSWER_MODEL"
CHECK_MODEL_VARIABLE: Final = "AMOEBA_LIVE_CHECK_MODEL"
MAX_COST_VARIABLE: Final = "AMOEBA_LIVE_MAX_COST_USD"
# Read only by the SDK-alias refusal test (Task 9.4), not at collection.
SDK_MODEL_VARIABLE: Final = "AMOEBA_LIVE_SDK_MODEL"


@dataclass(frozen=True)
class LiveSettings:
    answer_model: str
    check_model: str
    max_cost_usd: float


def require_variable(environ: Mapping[str, str], name: str) -> str:
    """The variable's value.

    Raises:
        pytest.UsageError: When it is unset or blank, naming it.
    """
    value = environ.get(name, "").strip()
    if not value:
        raise pytest.UsageError(
            f"live tier: set {name} (no default, tests spend money)"
        )
    return value


def _read_cost(environ: Mapping[str, str]) -> float:
    raw = require_variable(environ, MAX_COST_VARIABLE)
    try:
        cost = float(raw)
    except ValueError:
        cost = math.nan
    if not (math.isfinite(cost) and cost > 0):
        raise pytest.UsageError(
            f"live tier: {MAX_COST_VARIABLE} must be a positive number, got {raw!r}"
        )
    return cost


def read_live_settings(environ: Mapping[str, str]) -> LiveSettings:
    """Read the three collection-time variables.

    Raises:
        pytest.UsageError: For the first unset variable, or a cost that is not a
            positive number, naming the variable.
    """
    return LiveSettings(
        answer_model=require_variable(environ, ANSWER_MODEL_VARIABLE),
        check_model=require_variable(environ, CHECK_MODEL_VARIABLE),
        max_cost_usd=_read_cost(environ),
    )
