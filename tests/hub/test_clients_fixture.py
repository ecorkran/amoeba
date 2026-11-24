"""Each client machine of the two-machine fixture has its own ``cf`` and ``sq`` stubs
and its own clones; the hub has none of ``cf``, ``sq`` or ``git`` (slice 261, 15.1)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from hub_clients import HTTPS_ORIGIN, SSH_ORIGIN
from hub_fixture import FIRST, SECOND, hub_path, two_machine_hub


@pytest.mark.parametrize("program", ["cf", "sq", "git"])
def test_the_hubs_path_holds_none_of_cf_sq_or_git(program: str) -> None:
    assert shutil.which(program, path=hub_path()) is None


def test_a_client_has_its_own_cf_and_sq_first_on_its_path_and_the_real_git(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        for name in (FIRST, SECOND):
            home = hub.clients[name].home
            path = hub.env_for(home)["PATH"]
            assert shutil.which("cf", path=path) == str(home / "bin" / "cf")
            assert shutil.which("sq", path=path) == str(home / "bin" / "sq")
            assert shutil.which("git", path=path) is not None
        hub_env_path = hub.env_for(hub.home)["PATH"]
        assert shutil.which("cf", path=hub_env_path) is None


def test_one_repo_has_a_different_project_id_and_origin_form_on_each_machine(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        alpha, beta = hub.clients[FIRST], hub.clients[SECOND]
        on_alpha = alpha.clone("shared", SSH_ORIGIN, "cf-id-on-alpha", "shared-repo")
        on_beta = beta.clone("shared", HTTPS_ORIGIN, "cf-id-on-beta", "shared-repo")

        ids = {}
        for client, repo in ((alpha, on_alpha), (beta, on_beta)):
            done = subprocess.run(
                ["cf", "get", "--json"],
                cwd=repo,
                env=hub.env_for(client.home),
                capture_output=True,
                text=True,
                check=True,
            )
            ids[client.name] = json.loads(done.stdout)["id"]
        origins = [
            subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            for repo in (on_alpha, on_beta)
        ]

    assert ids == {FIRST: "cf-id-on-alpha", SECOND: "cf-id-on-beta"}
    assert origins == [SSH_ORIGIN, HTTPS_ORIGIN]


def test_outside_every_project_is_not_a_project_and_a_worktree_shares_the_id(
    tmp_path: Path,
) -> None:
    with two_machine_hub(tmp_path) as hub:
        alpha = hub.clients[FIRST]
        repo = alpha.clone("shared", SSH_ORIGIN, "cf-id", "shared-repo")
        tree = alpha.worktree(repo, "shared-tree")
        outside = tmp_path / "elsewhere"
        outside.mkdir()
        env = hub.env_for(alpha.home)

        def get(directory: Path) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["cf", "get", "--json"],
                cwd=directory,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        in_repo, in_tree, in_nothing = get(repo), get(tree), get(outside)

    assert json.loads(in_repo.stdout)["id"] == json.loads(in_tree.stdout)["id"]
    assert json.loads(in_tree.stdout)["projectPath"] == str(tree)
    assert in_nothing.returncode != 0
    assert "PROJECT_NOT_FOUND" in in_nothing.stderr


def _runs_dir_of(env: dict[str, str]) -> Path:
    """Where amoeba on that machine looks for Squadron's run files."""
    printed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from amoeba.config.home import squadron_runs_dir; "
            "print(squadron_runs_dir())",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(printed.stdout.strip())


def test_a_run_created_on_alpha_is_not_visible_on_beta(tmp_path: Path) -> None:
    with two_machine_hub(tmp_path) as hub:
        alpha = hub.env_for(hub.clients[FIRST].home)
        beta = hub.env_for(hub.clients[SECOND].home)
        alpha_runs, beta_runs = _runs_dir_of(alpha), _runs_dir_of(beta)
        alpha_runs.mkdir(parents=True)
        (alpha_runs / "run-alpha.json").write_text("{}", encoding="utf-8")

        assert alpha["HOME"] != beta["HOME"]
        assert alpha_runs != beta_runs
        assert not (beta_runs / "run-alpha.json").exists()
