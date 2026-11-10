"""``load_user_config``: the documented example loads, every defect is named."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from user_configs import CONFIG_CONTRACT as CONTRACT
from user_configs import example_config_text

from amoeba.config.user_config import ConfigError, load_user_config

TOP_LEVEL_KEYS = [
    "answer_model",
    "check_model",
    "max_cost_usd",
    "answer_limit",
    "passages_max_chars",
    "answering_wait_seconds",
    "resume_wait_seconds",
    "authorize_items",
]
ITEM_KEYS = ["key", "description", "screen_phrases", "denied_by_default"]


def _example() -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(example_config_text())
    return document


def _write(tmp_path: Path, document: object) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_the_documented_example_loads(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(example_config_text(), encoding="utf-8")

    config = load_user_config(path)

    assert [item.key for item in config.authorize_items] == [
        "push",
        "merge_to_main",
        "release",
        "destructive_database_statement",
        "policy_change",
    ]
    assert all(item.denied_by_default for item in config.authorize_items)
    assert config.authorize_items[1].screen_phrases == (
        "merge to main",
        "merge into main",
    )


def test_every_documented_key_is_in_the_doc() -> None:
    text = CONTRACT.read_text(encoding="utf-8")

    assert all(f"`{key}`" in text for key in TOP_LEVEL_KEYS + ITEM_KEYS)


@pytest.mark.parametrize("key", TOP_LEVEL_KEYS)
def test_removing_a_key_names_it(tmp_path: Path, key: str) -> None:
    document = _example()
    del document[key]
    path = _write(tmp_path, document)

    with pytest.raises(ConfigError) as error:
        load_user_config(path)

    assert str(path) in str(error.value)
    assert key in str(error.value)


@pytest.mark.parametrize("key", ITEM_KEYS)
def test_removing_an_item_key_names_it(tmp_path: Path, key: str) -> None:
    document = _example()
    del document["authorize_items"][0][key]

    with pytest.raises(ConfigError, match=f"authorize_items.0.{key}"):
        load_user_config(_write(tmp_path, document))


def _with(key: str, value: object) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        document[key] = value

    return change


@pytest.mark.parametrize(
    ("change", "named"),
    [
        (_with("surprise", 1), "surprise"),
        (_with("max_cost_usd", 0), "max_cost_usd"),
        (_with("answer_limit", 0), "answer_limit"),
        (_with("passages_max_chars", "many"), "passages_max_chars"),
        (_with("answering_wait_seconds", 0), "answering_wait_seconds"),
        (_with("answering_wait_seconds", -5), "answering_wait_seconds"),
        (_with("answering_wait_seconds", "soon"), "answering_wait_seconds"),
        (_with("resume_wait_seconds", 0), "resume_wait_seconds"),
        (_with("resume_wait_seconds", -0.5), "resume_wait_seconds"),
        (_with("resume_wait_seconds", True), "resume_wait_seconds"),
        (_with("answer_model", "a,b"), "answer_model"),
        (_with("check_model", "  "), "check_model"),
        (_with("authorize_items", "none"), "authorize_items"),
    ],
)
def test_a_bad_or_unknown_key_names_it(
    tmp_path: Path, change: Callable[[dict[str, Any]], None], named: str
) -> None:
    document = _example()
    change(document)
    path = _write(tmp_path, document)

    with pytest.raises(ConfigError) as error:
        load_user_config(path)

    assert str(path) in str(error.value)
    assert named in str(error.value)


def test_an_unknown_item_key_is_refused(tmp_path: Path) -> None:
    document = _example()
    document["authorize_items"][0]["severity"] = "high"

    with pytest.raises(ConfigError, match="authorize_items.0.severity"):
        load_user_config(_write(tmp_path, document))


def test_duplicate_item_keys_are_refused(tmp_path: Path) -> None:
    document = _example()
    document["authorize_items"].append(dict(document["authorize_items"][0]))

    with pytest.raises(ConfigError, match=r"authorize_items.*duplicate key 'push'"):
        load_user_config(_write(tmp_path, document))


def test_an_empty_item_list_is_allowed(tmp_path: Path) -> None:
    document = _example()
    document["authorize_items"] = []

    assert load_user_config(_write(tmp_path, document)).authorize_items == ()


def test_two_problems_in_one_file_are_both_listed(tmp_path: Path) -> None:
    document = _example()
    del document["answer_limit"]
    document["max_cost_usd"] = -1

    with pytest.raises(ConfigError) as error:
        load_user_config(_write(tmp_path, document))

    lines = str(error.value).splitlines()
    assert len(lines) == 2
    assert any("answer_limit" in line for line in lines)
    assert any("max_cost_usd" in line for line in lines)


def test_a_missing_file_says_where_to_look(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"

    with pytest.raises(ConfigError) as error:
        load_user_config(path)

    assert str(error.value) == f"no config at {path}; see docs/config-contract.md"


def test_a_file_that_is_not_utf8_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_bytes(b"answer_model: \xff\xfe\n")

    with pytest.raises(ConfigError, match=f"{path}.*UTF-8"):
        load_user_config(path)


def test_a_file_that_is_not_yaml_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("answer_model: [unclosed\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=f"{path}.*not YAML"):
        load_user_config(path)


def test_a_document_that_is_not_a_mapping_names_the_file(tmp_path: Path) -> None:
    path = _write(tmp_path, ["a", "list"])

    with pytest.raises(ConfigError, match=f"{path}.*mapping"):
        load_user_config(path)


@pytest.mark.parametrize("key", ["answering_wait_seconds", "resume_wait_seconds"])
@pytest.mark.parametrize("value", [1, 0.5, 600])
def test_a_positive_wait_is_accepted(tmp_path: Path, key: str, value: float) -> None:
    document = _example()
    document[key] = value

    config = load_user_config(_write(tmp_path, document))

    assert getattr(config, key) == value
