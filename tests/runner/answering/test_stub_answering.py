"""The stub `sq` plays the answering pipeline apart from slice runs (144, D13)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from sq_stub import (
    ANSWER_OUTCOME_ENV,
    ANSWER_PIPELINE_NAME,
    ANSWER_SCRIPT_ENV,
    RUN_SCRIPT_ENV,
    RUN_SECONDS_ENV,
    STUB_STATE_RELATIVE,
    write_run_script,
    write_sq_stub,
)
from sq_stub_scripts import (
    answering_run,
    check_reply,
    declining_answer_reply,
    proposed_answer_reply,
)

from amoeba.runner.answering.pipeline_file import (
    ANSWER_REPLY_FILE,
    CHECK_REPLY_FILE,
    PIPELINE_FILE_NAME,
    answering_pipeline_path,
)


def _sq(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *arguments: str
) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    bin_dir = write_sq_stub(tmp_path / "bin")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv(RUN_SECONDS_ENV, "0")
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    return subprocess.run(
        ["sq", *arguments],
        cwd=scratch,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_stub_names_the_shipped_pipeline_file() -> None:
    assert ANSWER_PIPELINE_NAME == PIPELINE_FILE_NAME
    assert answering_pipeline_path().name == ANSWER_PIPELINE_NAME


def test_an_answering_run_writes_its_scripted_replies_and_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = answering_run(
        proposed_answer_reply("use main", ["P1"]), check_reply("yes", "ok")
    )
    path = write_run_script(
        tmp_path / "script.json", files=script.files, document=script.document
    )
    monkeypatch.setenv(ANSWER_SCRIPT_ENV, str(path))
    monkeypatch.setenv(ANSWER_OUTCOME_ENV, "paused")
    monkeypatch.setenv(RUN_SCRIPT_ENV, str(tmp_path / "must-not-be-read.json"))

    done = _sq(
        tmp_path,
        monkeypatch,
        "run",
        f"/pkg/{PIPELINE_FILE_NAME}",
        "model-a",
        "--run-id",
        "run-ans-1",
        "-p",
        "check-model=model-b",
    )

    assert done.returncode == 0, done.stderr
    scratch = tmp_path / "scratch"
    assert json.loads((scratch / ANSWER_REPLY_FILE).read_text())["answer"] == "use main"
    assert json.loads((scratch / CHECK_REPLY_FILE).read_text())["verdict"] == "yes"
    state = tmp_path / "home" / STUB_STATE_RELATIVE / "run-ans-1.json"
    assert json.loads(state.read_text())["outcome"] == "paused"


def test_a_scripted_none_writes_no_file_and_a_string_is_written_verbatim() -> None:
    script = answering_run("not json {", None)

    assert script.files == {ANSWER_REPLY_FILE: "not json {"}
    assert declining_answer_reply("no basis")["kind"] == "decline"
