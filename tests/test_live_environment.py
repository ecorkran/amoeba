"""A live pipeline run gets named variables only, never the whole environment."""

from __future__ import annotations

from live_environment import pipeline_environment


def test_named_variables_pass_and_others_are_dropped() -> None:
    environ = {
        "PATH": "/usr/bin",
        "OPENROUTER_API_KEY": "key-value",
        "DATABASE_URL": "postgres://production",
        "AMOEBA_LIVE_REQUEST_MODEL": "alias",
    }
    assert pipeline_environment(environ) == {
        "PATH": "/usr/bin",
        "OPENROUTER_API_KEY": "key-value",
    }


def test_unset_variables_are_absent_not_empty() -> None:
    assert pipeline_environment({}) == {}
