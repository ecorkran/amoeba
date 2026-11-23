"""``amoeba init``: a new machine goes from nothing to a working Amoeba, twice over."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from amoeba.cli.main import EXIT_ERROR, EXIT_OK, main
from amoeba.config.home import config_path, store_path
from amoeba.config.starter import starter_values
from amoeba.config.user_config import UserConfig, load_user_config

REPOSITORY_ROOT = Path(__file__).parents[2]


def _run(capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main(["init"])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_init_on_a_new_machine_writes_a_valid_config_and_the_store(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert not config_path().exists()

    code, out, _ = _run(capsys)

    assert code == EXIT_OK
    load_user_config(config_path())  # every required key is there and valid
    assert store_path().is_file()
    assert str(config_path()) in out
    assert main(["status"]) == EXIT_OK  # the command that failed before init


def test_init_twice_changes_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    _run(capsys)
    written = config_path().read_bytes()

    code, out, _ = _run(capsys)

    assert code == EXIT_OK
    assert config_path().read_bytes() == written
    assert "already" in out


def test_init_adds_the_keys_an_older_config_lacks_and_keeps_its_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    older = {**starter_values(), "max_cost_usd": 9.5}
    del older["max_wakes_per_day"]
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(yaml.safe_dump(older, sort_keys=False), encoding="utf-8")

    code, out, _ = _run(capsys)

    assert code == EXIT_OK
    config = load_user_config(config_path())
    assert config.max_cost_usd == 9.5
    assert config.max_wakes_per_day == starter_values()["max_wakes_per_day"]
    assert "max_wakes_per_day" in out


def test_init_reports_a_config_it_cannot_fix_and_leaves_it_alone(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    broken = yaml.safe_dump({**starter_values(), "no_such_key": 1}, sort_keys=False)
    config_path().write_text(broken, encoding="utf-8")

    code, _, err = _run(capsys)

    assert code == EXIT_ERROR
    assert config_path().read_text(encoding="utf-8") == broken
    assert "no_such_key" in err


def test_the_starter_config_has_every_key_and_matches_the_documented_example() -> None:
    contract = (REPOSITORY_ROOT / "docs" / "config-contract.md").read_text("utf-8")
    block = re.search(
        r"```yaml\n(.*?)```", contract.split("## Example", 1)[1], re.DOTALL
    )
    assert block is not None

    assert set(starter_values()) == set(UserConfig.model_fields)
    assert yaml.safe_load(block.group(1)) == starter_values()


def test_a_missing_config_says_to_run_init(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["status"])
    err = capsys.readouterr().err

    assert code == EXIT_ERROR
    assert "amoeba init" in err
    assert "Traceback" not in err
