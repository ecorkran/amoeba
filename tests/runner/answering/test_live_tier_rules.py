"""The live tier's own rules: no default, no skip, failure names the variable."""

from __future__ import annotations

import pytest
from live_settings import (
    ANSWER_MODEL_VARIABLE,
    CHECK_MODEL_VARIABLE,
    MAX_COST_VARIABLE,
    LiveSettings,
    read_live_settings,
    require_variable,
)

COMPLETE = {
    ANSWER_MODEL_VARIABLE: "answer-alias",
    CHECK_MODEL_VARIABLE: "check-alias",
    MAX_COST_VARIABLE: "2.5",
}


def test_all_set_returns_the_values() -> None:
    assert read_live_settings(COMPLETE) == LiveSettings(
        "answer-alias", "check-alias", 2.5
    )


@pytest.mark.parametrize("missing", list(COMPLETE))
def test_each_missing_variable_is_named(missing: str) -> None:
    environ = {name: value for name, value in COMPLETE.items() if name != missing}
    with pytest.raises(pytest.UsageError, match=missing):
        read_live_settings(environ)


def test_blank_variable_counts_as_missing() -> None:
    with pytest.raises(pytest.UsageError, match=ANSWER_MODEL_VARIABLE):
        read_live_settings({**COMPLETE, ANSWER_MODEL_VARIABLE: "  "})


@pytest.mark.parametrize("cost", ["abc", "0", "-1", "nan", "inf"])
def test_bad_cost_names_the_cost_variable(cost: str) -> None:
    with pytest.raises(pytest.UsageError, match=MAX_COST_VARIABLE):
        read_live_settings({**COMPLETE, MAX_COST_VARIABLE: cost})


def test_require_variable_names_an_unset_variable() -> None:
    with pytest.raises(pytest.UsageError, match="SOME_OTHER_VARIABLE"):
        require_variable({}, "SOME_OTHER_VARIABLE")
