"""The hub container's files say what D17 says (slice 260)."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml

from amoeba.config.user_config import IMAGE_CONTRACT_DOC

ROOT = Path(__file__).parents[1]
DOCKERFILE = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
COMPOSE_TEXT = (ROOT / "docker" / "compose.example.yaml").read_text(encoding="utf-8")
COMPOSE = yaml.safe_load(COMPOSE_TEXT)


def _instructions(name: str) -> list[str]:
    return [
        line[len(name) :].strip()
        for line in DOCKERFILE.splitlines()
        if line.startswith(f"{name} ")
    ]


def test_the_entry_point_is_the_exec_form_of_hub_serve() -> None:
    (entry,) = _instructions("ENTRYPOINT")

    assert json.loads(entry) == ["amoeba", "hub", "serve"]


def test_the_image_runs_as_a_non_root_user_with_no_amoeba_home() -> None:
    assert _instructions("USER") == ["amoeba"]
    assert "AMOEBA_HOME" not in DOCKERFILE.replace("AMOEBA_HOME is not set", "")


def test_the_three_volumes_are_the_default_homes_and_the_backups() -> None:
    (volumes,) = _instructions("VOLUME")

    assert json.loads(volumes) == [
        "/home/amoeba/.config/amoeba",
        "/home/amoeba/.local/state/amoeba",
        "/backups",
    ]


def test_the_two_examples_are_copied_to_usr_share_amoeba() -> None:
    copies = " ".join(_instructions("COPY"))

    assert (
        "src/amoeba/hub/hub.yaml.example /usr/share/amoeba/hub.yaml.example" in copies
    )
    assert f"docs/config-contract.md {IMAGE_CONTRACT_DOC}" in copies


def test_the_build_stage_copies_every_file_pyproject_names() -> None:
    # hatchling reads the license and readme named in pyproject.toml while it
    # generates metadata, so the build stage fails if either is not copied.
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    named = [project["license"]["file"], project["readme"], "uv.lock"]
    (project_copy,) = [c for c in _instructions("COPY") if "pyproject.toml" in c]

    assert all(name in project_copy.split() for name in named)


def test_the_image_installs_from_the_lock_file_and_fails_when_it_is_stale() -> None:
    runs = " ".join(_instructions("RUN"))

    assert "uv sync --locked" in runs
    assert "pip install" not in runs


def test_the_compose_example_has_one_service_named_hub() -> None:
    assert list(COMPOSE["services"]) == ["hub"]
    hub = COMPOSE["services"]["hub"]
    # No build context: the file works from wherever it is copied; the comment gives
    # the build command.
    assert "build" not in hub
    assert hub["image"] == "amoeba-hub"
    assert "docker build -f docker/Dockerfile -t amoeba-hub ." in COMPOSE_TEXT
    assert hub["restart"] == "always"
    assert hub["ports"]


def test_the_three_mounts_are_under_amoeba_hub_in_the_home() -> None:
    volumes: list[str] = COMPOSE["services"]["hub"]["volumes"]

    hosts = [volume.split(":")[0] for volume in volumes]
    targets = [volume.split(":")[1] for volume in volumes]
    assert all(host.startswith("~/amoeba-hub/") for host in hosts)
    assert sorted(targets) == sorted(
        [
            "/home/amoeba/.config/amoeba",
            "/home/amoeba/.local/state/amoeba",
            "/backups",
        ]
    )


def test_the_comment_gives_both_restore_commands_and_the_flag_is_never_configured() -> (
    None
):
    assert "docker compose stop" in COMPOSE_TEXT
    assert re.search(
        r"docker compose run --rm --service-ports hub --from-backup", COMPOSE_TEXT
    )
    assert "--from-backup" not in json.dumps(COMPOSE)
    assert "command" not in COMPOSE["services"]["hub"]
