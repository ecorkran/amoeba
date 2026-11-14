"""Run the real ``amoeba`` script with a fake ``cf`` and ``sq`` first on ``PATH``.

Shared by the ``add``, ``rm`` and ``list`` CLI tests. ``cf get`` replays a recording
and ``cf list projects`` replays the real recording; ``HOME`` is a temporary directory
so no real Squadron run file is read. ``AMOEBA_HOME`` is the autouse temporary home.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from cf_fixtures import (
    DEFAULT_WORKTREE,
    fixture_document,
    write_fake_cf,
    write_fake_cf_with_projects,
)
from fake_sq import (
    RUN_FILE,
    SQUADRON_FIXTURES,
    FakeListing,
    recorded_listing,
    write_fake_sq,
)
from live_environment import process_environment
from process_containment import contained_popen
from user_configs import example_config_text

from amoeba.config.home import config_path

AMOEBA = Path(sys.executable).with_name("amoeba")
RUN_TIMEOUT_SECONDS = 60
SYSTEM_PATH = "/usr/bin:/bin"
#: The id and name of the project the default recording is in.
PROJECT_ID: str = fixture_document(DEFAULT_WORKTREE)["id"]
PROJECT_NAME: str = fixture_document(DEFAULT_WORKTREE)["name"]


def write_config(text: str | None = None) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(
        example_config_text() if text is None else text, encoding="utf-8"
    )


def request_file(tmp_path: Path, document: object) -> Path:
    path = tmp_path / "request.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def run_amoeba(  # noqa: PLR0913 - the fakes a subprocess run can be given
    tmp_path: Path,
    *arguments: str,
    stdin: bytes | None = None,
    cf_fixture: str | None = DEFAULT_WORKTREE,
    projects: bool = True,
    listing: FakeListing | None = None,
    as_json: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run ``amoeba``; ``as_json`` adds ``-j`` after the command name."""
    if as_json and arguments and not arguments[0].startswith("-"):
        arguments = (arguments[0], "-j", *arguments[1:])
    bin_dir = tmp_path / "bin"
    if projects and cf_fixture is not None:
        write_fake_cf_with_projects(bin_dir, cf_fixture)
    else:
        write_fake_cf(bin_dir, cf_fixture)
    write_fake_sq(
        bin_dir,
        waits={},
        run_exit_code=0,
        run_stderr="",
        runs_list=recorded_listing() if listing is None else listing,
    )
    home = tmp_path / "home"
    runs = home / ".config" / "squadron" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    shutil.copy(SQUADRON_FIXTURES / RUN_FILE, runs / "any-run.json")
    environment = process_environment(
        os.environ,
        PATH=f"{bin_dir}{os.pathsep}{SYSTEM_PATH}",
        HOME=str(home),
        AMOEBA_HOME=os.environ["AMOEBA_HOME"],
    )
    child = contained_popen(
        [str(AMOEBA), *arguments],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        env=environment,
    )
    stdout, stderr = child.communicate(stdin, timeout=RUN_TIMEOUT_SECONDS)
    return subprocess.CompletedProcess(
        child.args, child.returncode, stdout.decode(), stderr.decode()
    )


def result_of(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(completed.stdout)
    return document
