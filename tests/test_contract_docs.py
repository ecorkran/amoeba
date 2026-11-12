"""The contract docs name every table, column and config field the code has."""

from __future__ import annotations

from pathlib import Path

from amoeba.answering.values import DeclineReason
from amoeba.cli import main as cli
from amoeba.config.user_config import NotAuthorizedItem, UserConfig
from amoeba.operations.answer import AnswerRejection
from amoeba.operations.decisions import DecisionsOutcome
from amoeba.operations.dismiss import DismissOutcome, DismissRejection
from amoeba.operations.mark_read import MarkReadOutcome
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.pause_models import HandlePauseOutcome, SkipReason
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.retract import RetractOutcome, RetractRejection
from amoeba.operations.set_up_models import RemoveRequest, SetUpProblemCode
from amoeba.operations.status_models import (
    ClosedNowEntry,
    RunEntry,
    RunFileUnreadable,
    StatusResult,
    UnplacedReason,
    WaitingRunState,
)
from amoeba.store.errors import StoreRelocateError
from amoeba.store.store import Store
from amoeba.store.vocabulary import ClosedReason, QuestionState

DOCS = Path(__file__).parents[1] / "docs"
STORE_CONTRACT = DOCS / "store-contract.md"
CONFIG_CONTRACT = DOCS / "config-contract.md"
CLI_CONTRACT = DOCS / "cli-contract.md"
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


def test_the_store_contract_names_every_decline_reason() -> None:
    text = STORE_CONTRACT.read_text(encoding="utf-8")

    missing = [
        reason.value for reason in DeclineReason if f"`{reason.value}`" not in text
    ]

    assert not missing, f"store-contract.md does not name {missing}"


def test_the_cli_contract_names_every_command_exit_code_and_result_value() -> None:
    text = CLI_CONTRACT.read_text(encoding="utf-8")
    commands = [
        cli.SET_UP_COMMAND,
        cli.HANDLE_PAUSE_COMMAND,
        cli.ANSWER_COMMAND,
        cli.STATUS_COMMAND,
        cli.DECISIONS_COMMAND,
        cli.MARK_READ_COMMAND,
        cli.DISMISS_COMMAND,
        cli.RETRACT_COMMAND,
    ]
    exit_codes = [cli.EXIT_OK, cli.EXIT_REJECTED, cli.EXIT_USAGE, cli.EXIT_ERROR]
    values = [
        *(outcome.value for outcome in HandlePauseOutcome),
        *(reason.value for reason in SkipReason),
        *(rejection.value for rejection in AnswerRejection),
        *(pause.value for pause in PauseClass if pause is not PauseClass.NOT_PAUSED),
        RunFileUnreadable.RUN_FILE_UNREADABLE.value,
        *(code.value for code in RejectCode),
        *(reason.value for reason in UnplacedReason),
        *(state.value for state in WaitingRunState),
        *(outcome.value for outcome in MarkReadOutcome),
        *(outcome.value for outcome in DecisionsOutcome),
        *(outcome.value for outcome in DismissOutcome),
        *(rejection.value for rejection in DismissRejection),
        *(outcome.value for outcome in RetractOutcome),
        *(rejection.value for rejection in RetractRejection),
        *(code.value for code in SetUpProblemCode),
        *(reason.value for reason in ClosedReason),
    ]

    missing = [f"amoeba {name}" for name in commands if f"amoeba {name}" not in text]
    missing += [f"exit {code}" for code in exit_codes if f"| {code} |" not in text]
    missing += [value for value in values if f"`{value}`" not in text]

    assert not missing, f"cli-contract.md does not name {missing}"


def test_the_cli_contract_names_the_new_status_fields_and_the_remove_section() -> None:
    text = CLI_CONTRACT.read_text(encoding="utf-8")
    assert "last_call" in RunEntry.model_fields
    fields = [
        *(name for name in StatusResult.model_fields if name != "programs"),
        *ClosedNowEntry.model_fields,
        "last_call",
        *(f"remove.{name}" for name in RemoveRequest.model_fields),
    ]

    missing = [field for field in fields if f"`{field}`" not in text]
    missing += [
        phrase
        for phrase in ("StoreRelocateError", "concept: null", "logs/calls/")
        if phrase not in text
    ]

    assert not missing, f"cli-contract.md does not name {missing}"


def test_the_store_contract_names_the_lifecycle_vocabulary_and_the_migration() -> None:
    text = STORE_CONTRACT.read_text(encoding="utf-8")
    names = [
        *(state.value for state in QuestionState),
        *(reason.value for reason in ClosedReason),
        "003_question_lifecycle.sql",
        "legacy-<UTC stamp>",
        ".state-move.lock",
        "~/.local/state/amoeba/",
        "XDG_STATE_HOME",
        "the one exception",
    ]

    missing = [name for name in names if name.lower() not in text.lower()]

    assert not missing, f"store-contract.md does not say {missing}"
    assert StoreRelocateError.__name__ in text


def test_the_config_contract_names_both_homes() -> None:
    text = CONFIG_CONTRACT.read_text(encoding="utf-8")

    assert "~/.config/amoeba/" in text
    assert "~/.local/state/amoeba/" in text
