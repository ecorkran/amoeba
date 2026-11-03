"""Live run: a check step on an SDK-session alias is refused (Task 9.4).

Squadron fails a step that declares no tools when its model would run with tools,
file access or a persistent session. The check step must not dispatch, so no
``check.json`` or ``check.prompt.md`` appears.
"""

from __future__ import annotations

import os

from live_settings import SDK_MODEL_VARIABLE, require_variable

from amoeba.runner.answering.inputs import QuestionInput
from amoeba.runner.answering.pipeline_file import CHECK_PROMPT_FILE, CHECK_REPLY_FILE
from live.answering.harness import LiveHarness, passage


def test_sdk_alias_for_the_check_step_is_refused_before_dispatch(
    live_harness: LiveHarness,
) -> None:
    sdk_alias = require_variable(os.environ, SDK_MODEL_VARIABLE)
    rule = passage(
        1,
        "rule",
        "2026-10-01T00:00:00Z",
        "Commit messages use the form `type: summary`.",
        source="docs/commit-rules.md",
    )
    result = live_harness.run(
        "sdk-refusal",
        QuestionInput(
            "140 answering-pipeline", "What form must a commit message take?"
        ),
        rule,
        check_model=sdk_alias,
    )
    assert not result.succeeded, result.report
    # The refusal is the no-tools guard, not some other failure of the step.
    assert "allowed_tools" in result.report, result.report
    assert not (result.directory / CHECK_REPLY_FILE).exists()
    assert not (result.directory / CHECK_PROMPT_FILE).exists()
