"""A throwaway program member and the calls the pause live tests make (slice 223, D15).

The member is a git repository registered as a Context Forge project (its own data
directory, so the developer's projects are untouched) and as the only member of a
program under the test's ``AMOEBA_HOME``. Everything runs the real ``sq``, ``cf`` and
``amoeba`` with real models; the environment is the named list of
``live_environment``, never the whole shell's.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from git_repo import git
from live_environment import pipeline_environment
from live_harness import PipelineRun, watch_run
from live_settings import LiveSettings
from process_containment import contained_popen
from user_configs import example_config_text

from amoeba.config.home import STORE_FILE_NAME
from amoeba.operations.answering_run import NO_PAUSE_HOOK_FLAG
from amoeba.upstream.squadron.launch import TARGET_PARAM_KEY, build_argv

AMOEBA: Final = Path(sys.executable).with_name("amoeba")
PAUSE_PIPELINE: Final = Path(__file__).parent / "asks_question.yaml"
PIPELINE_MODEL_PARAM: Final = "model"
SLICE_PARAM: Final = TARGET_PARAM_KEY
CF_TIMEOUT_SECONDS: Final = 60
AMOEBA_TIMEOUT_SECONDS: Final = 900
SQ_RUN_TIMEOUT_SECONDS: Final = 600
#: The launcher gets this long to exit by itself, so a pause hook it starts has
#: started before the launcher's session is killed.
LAUNCHER_EXIT_GRACE_SECONDS: Final = 30.0
ANSWERING_WAIT_SECONDS: Final = 600
RESUME_WAIT_SECONDS: Final = 120
RULE_FILE: Final = "CLAUDE.md"
RULE_TEXT: Final = (
    "# Rules\n\nSource files are kept to about 300 lines. Split a file that grows "
    "past that into modules.\n"
)


@dataclass(frozen=True)
class PauseWorld:
    """A registered member and what it takes to run commands in it."""

    repo: Path
    environ: dict[str, str]
    amoeba_home: Path
    settings: LiveSettings

    @property
    def store(self) -> Path:
        return self.amoeba_home / STORE_FILE_NAME


def build_world(
    parent: Path,
    amoeba_home: Path,
    settings: LiveSettings,
    *,
    repo: Path | None = None,
    passages_max_chars: int | None = None,
) -> PauseWorld:
    """Make the member repo, register it with Context Forge and as a program member.

    ``repo`` is an existing committed git repository to use as the member (its plan
    files are what Context Forge reads); without one a repo holding only the rules
    file is made. ``passages_max_chars`` overrides the example config's value.
    """
    if repo is None:
        repo = parent / "member"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        (repo / RULE_FILE).write_text(RULE_TEXT, encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "rules")
    data_dir = parent / "cf-data"
    data_dir.mkdir()
    environ = {
        **pipeline_environment(os.environ),
        "CONTEXT_FORGE_DATA_DIR": str(data_dir),
        "AMOEBA_HOME": str(amoeba_home),
    }
    _run(["cf", "init", "--lite", "--name", "amoeba-live-pause"], repo, environ)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "cf init", check=False)
    world = PauseWorld(repo, environ, amoeba_home, settings)
    _write_config(world, passages_max_chars)
    request = parent / "set_up.yaml"
    request.write_text(
        yaml.safe_dump(
            {"program": "live-pause", "members": [{"rules_paths": [RULE_FILE]}]}
        ),
        encoding="utf-8",
    )
    registered = run_amoeba(world, "set_up", "--file", str(request))
    assert registered.returncode == 0, registered.stderr + registered.stdout
    return world


def _write_config(world: PauseWorld, passages_max_chars: int | None) -> None:
    config = yaml.safe_load(example_config_text())
    if passages_max_chars is not None:
        config["passages_max_chars"] = passages_max_chars
    config.update(
        answer_model=world.settings.answer_model,
        check_model=world.settings.check_model,
        max_cost_usd=world.settings.max_cost_usd,
        answering_wait_seconds=ANSWERING_WAIT_SECONDS,
        resume_wait_seconds=RESUME_WAIT_SECONDS,
    )
    world.amoeba_home.mkdir(parents=True, exist_ok=True)
    (world.amoeba_home / "config.yaml").write_text(
        yaml.safe_dump(config), encoding="utf-8"
    )


def _run(argv: list[str], cwd: Path, environ: dict[str, str]) -> None:
    subprocess.run(
        argv,
        cwd=cwd,
        env=environ,
        capture_output=True,
        text=True,
        timeout=CF_TIMEOUT_SECONDS,
        check=True,
    )


def run_amoeba(world: PauseWorld, *arguments: str) -> subprocess.CompletedProcess[str]:
    """``amoeba <arguments>`` in the member checkout, with the world's environment."""
    child = contained_popen(
        [str(AMOEBA), *arguments],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=world.repo,
        env=world.environ,
    )
    stdout, stderr = child.communicate(timeout=AMOEBA_TIMEOUT_SECONDS)
    return subprocess.CompletedProcess(
        child.args, child.returncode, stdout.decode(), stderr.decode()
    )


def question_pipeline(
    directory: Path, run_id: str, question: str, *, sliced: bool
) -> Path:
    """A pause pipeline whose one step is told to reply with ``question``.

    Same shape as ``asks_question.yaml`` (a ``dispatch`` that declares an artifact and
    writes none, so a reply ending on a question pauses the run). ``sliced`` adds a
    required ``slice`` parameter, the run parameter ``handle_pause`` reads.
    """
    params = (
        {"slice": "required", PIPELINE_MODEL_PARAM: "required"}
        if sliced
        else {PIPELINE_MODEL_PARAM: "required"}
    )
    document = {
        "name": "asks-question",
        "description": "Stop on a given question",
        "params": params,
        "steps": [
            {
                "dispatch": {
                    "name": "ask",
                    "model": "{" + PIPELINE_MODEL_PARAM + "}",
                    "artifact": "design",
                    "prompt": (
                        "Do not edit any file and do not run any command. Reply "
                        "with exactly the text between the markers and no other "
                        f"words.\n<<<\n{question}\n>>>"
                    ),
                }
            }
        ],
    }
    path = directory / f"{run_id}.yaml"
    # Declaration order matters: Squadron takes the first required parameter as the
    # positional target.
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def start_pause(
    world: PauseWorld,
    run_id: str,
    *,
    opt_out: bool,
    pipeline: Path | None = None,
    slice_index: str | None = None,
) -> PipelineRun:
    """Run a question-asking pipeline in the member until it pauses.

    Without ``pipeline`` it is ``asks_question.yaml``. ``slice_index`` is passed as the
    run's ``slice`` parameter (the pipeline must declare it).
    """
    params = {PIPELINE_MODEL_PARAM: world.settings.answer_model}
    if slice_index is not None:
        params[SLICE_PARAM] = slice_index
    argv = build_argv(
        str(pipeline or PAUSE_PIPELINE),
        run_id,
        params,
        target_key=SLICE_PARAM if slice_index is not None else PIPELINE_MODEL_PARAM,
    )
    return watch_run(
        [*argv, NO_PAUSE_HOOK_FLAG] if opt_out else argv,
        run_id,
        world.repo,
        SQ_RUN_TIMEOUT_SECONDS,
        LAUNCHER_EXIT_GRACE_SECONDS,
        world.environ,
    )


def store_rows(world: PauseWorld, statement: str) -> list[tuple[object, ...]]:
    """Rows of a read-only query against the world's store."""
    with sqlite3.connect(f"file:{world.store}?mode=ro", uri=True) as connection:
        return [tuple(row) for row in connection.execute(statement).fetchall()]


def result_of(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    document: dict[str, object] = json.loads(completed.stdout)
    return document
