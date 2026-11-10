"""The contract docs name every table, column and config field the code has."""

from __future__ import annotations

from pathlib import Path

from amoeba.config.user_config import NotAuthorizedItem, UserConfig
from amoeba.store.store import Store

DOCS = Path(__file__).parents[1] / "docs"
STORE_CONTRACT = DOCS / "store-contract.md"
CONFIG_CONTRACT = DOCS / "config-contract.md"
INTERNAL_TABLE_PREFIX = "sqlite_"


def _schema(tmp_path: Path) -> dict[str, list[str]]:
    """Each table of a fresh store and its column names, from ``PRAGMA table_info``."""
    with Store.open(tmp_path / "amoeba.sqlite3") as store, store.read() as transaction:
        tables = [
            row[0]
            for row in transaction.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            if not row[0].startswith(INTERNAL_TABLE_PREFIX)
        ]
        return {
            table: [
                row[1] for row in transaction.execute(f"PRAGMA table_info({table})")
            ]
            for table in tables
        }


def test_the_store_contract_names_every_table_and_column(tmp_path: Path) -> None:
    text = STORE_CONTRACT.read_text(encoding="utf-8")
    schema = _schema(tmp_path)
    assert len(schema) == 8

    missing = [
        f"{table}.{column}" if column else table
        for table, columns in schema.items()
        for column in (None, *columns)
        if f"`{column or table}`" not in text
    ]

    assert not missing, f"store-contract.md does not name {missing}"


def test_the_store_contract_states_both_derivations() -> None:
    text = STORE_CONTRACT.read_text(encoding="utf-8")

    assert "answering_dir() / <answering_run_id>" in text
    assert "answering_enabled" in text
    assert "No edits to `001`" in text
    assert "AMOEBA_HOME" in text


def test_the_config_contract_names_every_user_config_field() -> None:
    text = CONFIG_CONTRACT.read_text(encoding="utf-8")
    fields = [*UserConfig.model_fields, *NotAuthorizedItem.model_fields]

    missing = [field for field in fields if f"`{field}`" not in text]

    assert not missing, f"config-contract.md does not name {missing}"
