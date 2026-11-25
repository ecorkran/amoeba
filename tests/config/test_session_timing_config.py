"""The three session timing keys (slice 241, D7): required, positive, and in step.

``session_heartbeat_seconds`` is at least ``notify_poll_seconds``, and
``session_stale_seconds`` at least ``STALE_HEARTBEATS_MIN`` heartbeats; each failure
names both keys. Values come from the contract's example so they live only there.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from user_configs import example_config_text

from amoeba.config.user_config import (
    STALE_HEARTBEATS_MIN,
    ConfigError,
    load_user_config,
)

POLL = "notify_poll_seconds"
HEARTBEAT = "session_heartbeat_seconds"
STALE = "session_stale_seconds"
TIMING_KEYS = (POLL, HEARTBEAT, STALE)


def _example() -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(example_config_text())
    return document


def _load(tmp_path: Path, document: dict[str, Any]) -> object:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return load_user_config(path)


def _timed(poll: float, heartbeat: float, stale: float) -> dict[str, Any]:
    return {**_example(), POLL: poll, HEARTBEAT: heartbeat, STALE: stale}


def test_the_contract_example_carries_and_loads_the_three_keys(
    tmp_path: Path,
) -> None:
    example = _example()

    config = _load(tmp_path, example)

    for key in TIMING_KEYS:
        assert getattr(config, key) == example[key]


@pytest.mark.parametrize("key", TIMING_KEYS)
def test_each_key_missing_fails_naming_it(tmp_path: Path, key: str) -> None:
    document = _example()
    del document[key]

    with pytest.raises(ConfigError, match=key):
        _load(tmp_path, document)


@pytest.mark.parametrize("key", TIMING_KEYS)
@pytest.mark.parametrize("value", [0, -1, -0.5])
def test_zero_or_negative_fails_naming_the_key(
    tmp_path: Path, key: str, value: float
) -> None:
    with pytest.raises(ConfigError, match=key):
        _load(tmp_path, {**_example(), key: value})


def test_a_stale_limit_under_the_minimum_heartbeats_fails_naming_both(
    tmp_path: Path,
) -> None:
    heartbeat = 10
    stale = STALE_HEARTBEATS_MIN * heartbeat - 1

    with pytest.raises(ConfigError) as raised:
        _load(tmp_path, _timed(1, heartbeat, stale))

    assert STALE in str(raised.value)
    assert HEARTBEAT in str(raised.value)


def test_a_heartbeat_under_the_poll_interval_fails_naming_both(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigError) as raised:
        _load(tmp_path, _timed(10, 9, 100))

    assert HEARTBEAT in str(raised.value)
    assert POLL in str(raised.value)


def test_values_equal_to_all_three_limits_load(tmp_path: Path) -> None:
    heartbeat = 7
    least = max(STALE_HEARTBEATS_MIN * heartbeat, heartbeat + 2 * heartbeat)

    config = _load(tmp_path, _timed(heartbeat, heartbeat, least))

    assert getattr(config, STALE) == least


def test_heartbeat_and_two_polls_over_the_stale_limit_fails_naming_three_keys(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigError) as raised:
        _load(tmp_path, _timed(5, 5, 10))

    for key in TIMING_KEYS:
        assert key in str(raised.value)


def test_stale_exactly_at_heartbeat_plus_two_polls_passes_and_one_below_fails(
    tmp_path: Path,
) -> None:
    at_sum = 20 + 2 * 20

    assert getattr(_load(tmp_path, _timed(20, 20, at_sum)), STALE) == at_sum
    with pytest.raises(ConfigError, match=STALE):
        _load(tmp_path, _timed(20, 20, at_sum - 1))
