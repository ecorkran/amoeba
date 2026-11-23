"""``amoeba init``: a new machine goes from nothing to a working Amoeba, twice over."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
import yaml
from user_configs import example_config_text

from amoeba.cli.main import EXIT_ERROR, EXIT_OK, main
from amoeba.config.home import config_path, store_path
from amoeba.config.starter import starter_text, starter_values
from amoeba.config.user_config import UserConfig, load_user_config

DROPPED_KEY = "max_wakes_per_day"


def _hand_edited_without(key: str) -> str:
    """The shipped starter as a person would have it: comments kept, one key line
    gone, and no newline at the end."""
    lines = [
        line for line in starter_text().splitlines() if not line.startswith(f"{key}:")
    ]
    return "# my own note\n" + "\n".join(lines)


def _place(text: str, path: Path | None = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


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
    assert set(starter_values()) == set(UserConfig.model_fields)
    assert yaml.safe_load(example_config_text()) == starter_values()


def test_a_missing_config_says_to_run_init(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["status"])
    err = capsys.readouterr().err

    assert code == EXIT_ERROR
    assert "amoeba init" in err
    assert "Traceback" not in err


def test_init_fills_a_hand_edited_config_and_keeps_its_comments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _place(_hand_edited_without(DROPPED_KEY))

    code, out, _ = _run(capsys)

    assert code == EXIT_OK
    text = config_path().read_text(encoding="utf-8")
    assert text.startswith("# my own note\n")
    assert "placeholders" in text  # the starter's own comment is still there
    assert (
        load_user_config(config_path()).max_wakes_per_day
        == (starter_values()[DROPPED_KEY])
    )
    assert DROPPED_KEY in out


def test_init_leaves_a_config_alone_when_adding_keys_would_not_make_it_valid(
    capsys: pytest.CaptureFixture[str],
) -> None:
    broken = _hand_edited_without(DROPPED_KEY).replace(
        "max_cost_usd: 0.5", "max_cost_usd: -1"
    )
    assert "max_cost_usd: -1" in broken
    _place(broken)

    code, _, err = _run(capsys)

    assert code == EXIT_ERROR
    assert config_path().read_text(encoding="utf-8") == broken
    assert "max_cost_usd" in err


@pytest.mark.parametrize("empty", ["", "# nothing set yet\n"])
def test_init_fills_every_key_of_an_empty_config(
    capsys: pytest.CaptureFixture[str], empty: str
) -> None:
    _place(empty)

    code, _, _ = _run(capsys)

    assert code == EXIT_OK
    load_user_config(config_path())
    assert config_path().read_text(encoding="utf-8").startswith(empty)


def test_init_writes_through_a_linked_config(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    real = _place(
        _hand_edited_without(DROPPED_KEY), tmp_path / "dotfiles" / "config.yaml"
    )
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().symlink_to(real)

    code, _, _ = _run(capsys)

    assert code == EXIT_OK
    assert config_path().is_symlink()
    assert f"{DROPPED_KEY}:" in real.read_text(encoding="utf-8")


def test_a_config_home_that_cannot_be_written_is_one_error_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = config_path().parent
    home.mkdir(parents=True, exist_ok=True)
    home.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        code, _, err = _run(capsys)
    finally:
        home.chmod(stat.S_IRWXU)

    assert code == EXIT_ERROR
    assert "cannot write" in err
    assert "Traceback" not in err
