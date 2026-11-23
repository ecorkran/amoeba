"""``hub.yaml``: eight required keys, every problem in one pass (slice 260, D14)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from amoeba.config.user_config import IMAGE_CONTRACT_DOC, ConfigError
from amoeba.hub import hub_config
from amoeba.hub.hub_config import HubConfig, HubConfigError, load_hub_config

EXAMPLE = Path(hub_config.__file__).with_name("hub.yaml.example")
KEYS = tuple(HubConfig.model_fields)


def _write(tmp_path: Path, document: dict[str, object]) -> Path:
    path = tmp_path / "hub.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def _example() -> dict[str, object]:
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def test_the_example_loads_as_a_valid_config() -> None:
    config = load_hub_config(EXAMPLE)

    assert config.backup_dir == "/backups"
    assert config.bind == "0.0.0.0"
    assert set(_example()) == set(KEYS)


def test_there_are_eight_keys() -> None:
    assert len(KEYS) == 8


@pytest.mark.parametrize("key", KEYS)
def test_a_missing_key_fails_naming_it(tmp_path: Path, key: str) -> None:
    document = _example()
    del document[key]
    path = _write(tmp_path, document)

    with pytest.raises(HubConfigError, match=key) as raised:
        load_hub_config(path)

    assert str(path) in str(raised.value)


def test_an_unknown_key_fails_naming_it(tmp_path: Path) -> None:
    path = _write(tmp_path, {**_example(), "colour": "blue"})

    with pytest.raises(HubConfigError, match="colour"):
        load_hub_config(path)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("backup_dir", "relative/path"),
        ("backup_hours", 0),
        ("backups_kept", 0),
        ("hub_log_max_bytes", 0),
        ("hub_logs_kept", 1),
        ("port", 0),
        ("port", 70000),
        ("address", "no-port-here"),
        ("bind", "   "),
    ],
)
def test_a_bad_value_fails_naming_the_key(
    tmp_path: Path, key: str, value: object
) -> None:
    path = _write(tmp_path, {**_example(), key: value})

    with pytest.raises(HubConfigError, match=key):
        load_hub_config(path)


def test_two_problems_are_reported_together(tmp_path: Path) -> None:
    path = _write(tmp_path, {**_example(), "backups_kept": 0, "hub_logs_kept": 1})

    with pytest.raises(HubConfigError) as raised:
        load_hub_config(path)

    assert "backups_kept" in str(raised.value)
    assert "hub_logs_kept" in str(raised.value)


def test_a_fractional_backup_interval_is_allowed(tmp_path: Path) -> None:
    path = _write(tmp_path, {**_example(), "backup_hours": 0.5})

    assert load_hub_config(path).backup_hours == 0.5


def test_a_missing_file_is_a_hub_config_error_naming_it(tmp_path: Path) -> None:
    path = tmp_path / "hub.yaml"

    with pytest.raises(HubConfigError, match="hub config") as raised:
        load_hub_config(path)

    assert str(path) in str(raised.value)
    assert isinstance(raised.value, ConfigError)
    # Inside the hub image there is no docs/ directory: the message names where the
    # contract is there.
    assert IMAGE_CONTRACT_DOC in str(raised.value)


def test_a_file_that_is_not_a_mapping_fails(tmp_path: Path) -> None:
    path = tmp_path / "hub.yaml"
    path.write_text("- 1\n- 2\n", encoding="utf-8")

    with pytest.raises(HubConfigError, match="mapping"):
        load_hub_config(path)
