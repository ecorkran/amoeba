"""The request live tier's rules: no default, no skip, failure names the variable."""

from __future__ import annotations

from pathlib import Path

import pytest
from live_request_settings import (
    REQUEST_MAX_COST_VARIABLE,
    REQUEST_MODEL_VARIABLE,
    RequestLiveSettings,
    read_request_live_settings,
)
from live_settings import (
    ANSWER_MODEL_VARIABLE,
    CHECK_MODEL_VARIABLE,
    MAX_COST_VARIABLE,
    SDK_MODEL_VARIABLE,
)

COMPLETE = {
    REQUEST_MODEL_VARIABLE: "request-alias",
    REQUEST_MAX_COST_VARIABLE: "2.5",
}
SHARED_CONFTEST = Path(__file__).parents[2] / "live" / "conftest.py"


def test_all_set_returns_the_values() -> None:
    assert read_request_live_settings(COMPLETE) == RequestLiveSettings(
        "request-alias", 2.5
    )


@pytest.mark.parametrize("missing", list(COMPLETE))
def test_each_missing_variable_is_named(missing: str) -> None:
    environ = {name: value for name, value in COMPLETE.items() if name != missing}
    with pytest.raises(pytest.UsageError, match=missing):
        read_request_live_settings(environ)


def test_invalid_cost_names_the_request_cost_variable() -> None:
    with pytest.raises(pytest.UsageError, match=REQUEST_MAX_COST_VARIABLE):
        read_request_live_settings({**COMPLETE, REQUEST_MAX_COST_VARIABLE: "-1"})


def test_shared_live_conftest_reads_no_answering_setting() -> None:
    text = SHARED_CONFTEST.read_text(encoding="utf-8")
    for variable in (
        ANSWER_MODEL_VARIABLE,
        CHECK_MODEL_VARIABLE,
        MAX_COST_VARIABLE,
        SDK_MODEL_VARIABLE,
    ):
        assert variable not in text
    assert "read_live_settings" not in text
