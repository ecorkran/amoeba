#!/usr/bin/env python3
"""Build the throwaway environment for the question-answerer walkthrough (slice 145).

    uv run python scripts/answerer_walkthrough.py setup --dir D --env-file F

`D` must not exist. It receives a scratch git checkout (`D/checkout`), a throwaway
Context Forge registry (`D/cf`), an Amoeba store directory (`D/store`) and a project
config (`D/projects.yaml`). `F` holds the provider keys; it is copied into the
checkout as `.env`, which git ignores. The script prints the `export` lines and the
`amoeba start` command, then stops. The cases are driven by hand, following
`docs/answerer-walkthrough.md`.

The script never opens the store: it calls the `amoeba`, `cf` and `git` commands.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

TREE = Path(__file__).parent / "answerer_walkthrough" / "project"
PROJECT_ID = "scratch"
SUBMITTER = "walkthrough"
#: git identity for the scratch checkout; passed with -c so no global config is read.
GIT_IDENTITY = (
    "-c",
    "user.name=Answerer Walkthrough",
    "-c",
    "user.email=walkthrough@example.invalid",
)
STORE_DIR_VAR = "AMOEBA_STORE_DIR"
REGISTRY_DIR_VAR = "CONTEXT_FORGE_DATA_DIR"
ANSWER_MODEL_VAR = "AMOEBA_LIVE_ANSWER_MODEL"
CHECK_MODEL_VAR = "AMOEBA_LIVE_CHECK_MODEL"
MAX_COST_VAR = "AMOEBA_LIVE_MAX_COST_USD"

#: Written literally; the config loader does not expand variables (slice 145, D5).
CONFIG_TEMPLATE = """\
projects:
  {project}:
    pipeline: p4
    answerer:
      answer_limit: 1
      reserved_terms: [push, merge, release, DROP]
      rules_paths: [CLAUDE.md]
      passages_max_chars: 100000
      answer_model: {answer_model}
      check_model: {check_model}
      max_concurrent_runs: 1
      max_cost_usd: {max_cost}
"""


@dataclass(frozen=True)
class LiveSettings:
    """The three values 140's live tier already uses, read from the environment."""

    answer_model: str
    check_model: str
    max_cost_usd: str


@dataclass(frozen=True)
class Layout:
    """Where everything lives under the walkthrough directory."""

    root: Path

    @property
    def checkout(self) -> Path:
        return self.root / "checkout"

    @property
    def registry(self) -> Path:
        return self.root / "cf"

    @property
    def store(self) -> Path:
        return self.root / "store"

    @property
    def config(self) -> Path:
        return self.root / "projects.yaml"


def read_live_settings(environ: Mapping[str, str]) -> LiveSettings:
    """Return the live settings; exit naming the first variable unset or empty."""
    values: dict[str, str] = {}
    for name in (ANSWER_MODEL_VAR, CHECK_MODEL_VAR, MAX_COST_VAR):
        value = environ.get(name, "").strip()
        if not value:
            raise SystemExit(f"{name} is not set; export it before running setup")
        values[name] = value
    try:
        cost = float(values[MAX_COST_VAR])
    except ValueError:
        raise SystemExit(
            f"{MAX_COST_VAR} is not a number: {values[MAX_COST_VAR]}"
        ) from None
    if not cost > 0:
        raise SystemExit(f"{MAX_COST_VAR} must be above zero: {values[MAX_COST_VAR]}")
    return LiveSettings(
        answer_model=values[ANSWER_MODEL_VAR],
        check_model=values[CHECK_MODEL_VAR],
        max_cost_usd=values[MAX_COST_VAR],
    )


def run_step(
    step: str, argv: list[str], *, cwd: Path, env: Mapping[str, str], root: Path
) -> str:
    """Run one command; on a non-zero exit report it, keep ``root`` and stop."""
    result = subprocess.run(
        argv, cwd=cwd, env=dict(env), capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise SystemExit(
            f"step '{step}' failed (exit {result.returncode}): {shlex.join(argv)}\n"
            f"{result.stderr.strip()}\n"
            f"{root} is partly built and was left in place; remove it before a rerun"
        )
    return result.stdout


def build_checkout(layout: Layout, env_file: Path, env: Mapping[str, str]) -> None:
    """Copy the tree, register it with Context Forge, commit it, then add `.env`.

    `cf init` edits `.gitignore`, so it runs before the commit to leave the checkout
    clean. The `.env` is copied last so it is never in history.
    """
    shutil.copytree(TREE, layout.checkout)
    checkout, root = layout.checkout, layout.root
    run_step(
        "git init",
        ["git", "init", "-q", "-b", "main"],
        cwd=checkout,
        env=env,
        root=root,
    )
    run_step(
        "cf init",
        ["cf", "init", "--lite", "--name", PROJECT_ID],
        cwd=checkout,
        env=env,
        root=root,
    )
    run_step("git add", ["git", "add", "-A"], cwd=checkout, env=env, root=root)
    run_step(
        "git commit",
        ["git", *GIT_IDENTITY, "commit", "-q", "-m", "scratch notes project"],
        cwd=checkout,
        env=env,
        root=root,
    )
    shutil.copyfile(env_file, checkout / ".env")


def read_cf_project_id(layout: Layout, env: Mapping[str, str]) -> str:
    """Read the Context Forge project id from `cf get --json`; never invent one."""
    out = run_step(
        "cf get",
        ["cf", "get", "--json"],
        cwd=layout.checkout,
        env=env,
        root=layout.root,
    )
    parsed: object
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        # Reported below as a missing id, naming the step.
        parsed = None
    fields = cast("dict[str, object]", parsed) if isinstance(parsed, dict) else {}
    project_id = fields.get("id")
    if not isinstance(project_id, str) or not project_id:
        raise SystemExit(
            "step 'cf get' printed no project id; "
            f"{layout.root} is partly built and was left in place"
        )
    return project_id


def submit_project(layout: Layout, cf_project_id: str, env: Mapping[str, str]) -> None:
    """Queue the project and its Context Forge link in the store's inbox."""
    common = ["--project", PROJECT_ID, "--by", SUBMITTER]
    steps = {
        "amoeba submit create-project": ["create-project", *common],
        "amoeba submit link-cf-project": [
            "link-cf-project",
            *common,
            "--cf-project-id",
            cf_project_id,
        ],
    }
    for step, args in steps.items():
        run_step(
            step,
            ["amoeba", "submit", *args],
            cwd=layout.checkout,
            env=env,
            root=layout.root,
        )


def write_config(layout: Layout, live: LiveSettings) -> None:
    """Write `projects.yaml` with the live values as literals."""
    layout.config.write_text(
        CONFIG_TEMPLATE.format(
            project=PROJECT_ID,
            answer_model=json.dumps(live.answer_model),
            check_model=json.dumps(live.check_model),
            max_cost=live.max_cost_usd,
        )
    )


def setup(directory: Path, env_file: Path, environ: Mapping[str, str]) -> None:
    """Refuse bad input first, so a refusal creates nothing; then build."""
    if directory.exists():
        raise SystemExit(f"{directory} already exists; choose a new directory")
    if not env_file.is_file():
        raise SystemExit(f"env file {env_file} does not exist")
    live = read_live_settings(environ)
    layout = Layout(directory.resolve())
    layout.root.mkdir(parents=True)
    env = {
        **environ,
        STORE_DIR_VAR: str(layout.store),
        REGISTRY_DIR_VAR: str(layout.registry),
    }
    build_checkout(layout, env_file, env)
    submit_project(layout, read_cf_project_id(layout, env), env)
    write_config(layout, live)
    print_summary(layout)


def print_summary(layout: Layout) -> None:
    print(f"Created {layout.root}")
    print(f"  checkout   {layout.checkout}")
    print(f"  registry   {layout.registry}")
    print(f"  store      {layout.store}")
    print(f"  config     {layout.config}")
    print("\nRun these in the shell you will use for the walkthrough:\n")
    print(f"export {STORE_DIR_VAR}={shlex.quote(str(layout.store))}")
    print(f"export {REGISTRY_DIR_VAR}={shlex.quote(str(layout.registry))}")
    print("\nThen start Amoeba:\n")
    print(
        f"amoeba start --project-config {shlex.quote(str(layout.config))} "
        f"--cf-data-dir {shlex.quote(str(layout.registry))}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    setup_parser = commands.add_parser("setup", help="build the walkthrough directory")
    setup_parser.add_argument("--dir", type=Path, required=True)
    setup_parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args(argv)
    setup(args.dir, args.env_file, os.environ)
    return 0


if __name__ == "__main__":
    sys.exit(main())
