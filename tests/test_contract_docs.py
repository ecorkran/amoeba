"""The contract docs name every table, column and config field the code has."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import cast

from amoeba.answering.import_follow import IMPORT_DEPTH
from amoeba.answering.passages import SourcesProblemKind
from amoeba.answering.values import DeclineReason
from amoeba.cli import main as cli
from amoeba.cli.parser import build_parser
from amoeba.config.user_config import NotAuthorizedItem, UserConfig
from amoeba.operations.add import AddRequest
from amoeba.operations.answer import AnswerRejection
from amoeba.operations.changes_models import ChangesOutcome, ChangesWarningCode
from amoeba.operations.decisions import DecisionsOutcome
from amoeba.operations.dismiss import DismissOutcome, DismissRejection
from amoeba.operations.list_registry import (
    ConceptRow,
    DependencyRow,
    MemberRow,
    ProgramRow,
)
from amoeba.operations.list_view import ListRequest, SettledEntry
from amoeba.operations.mark_read import MarkReadOutcome
from amoeba.operations.names import OperationName
from amoeba.operations.pause_class import PauseClass
from amoeba.operations.pause_models import HandlePauseOutcome, SkipReason
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.report_release_models import ReportMode, ReportOutcome
from amoeba.operations.retract import RetractOutcome, RetractRejection
from amoeba.operations.rm import RmRequest
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
IGNORED_FLAGS = ("--help", "--json")
RULES_DOC = DOCS / "rules.md"
MCP_DOC = DOCS / "mcp-server.md"
HOOK_DOC = DOCS / "squadron-hook.md"
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
    commands = [name.cli_name for name in OperationName]
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
        *(outcome.value for outcome in ReportOutcome),
        *(mode.value for mode in ReportMode),
        *(outcome.value for outcome in ChangesOutcome),
        *(code.value for code in ChangesWarningCode),
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


def _option_flags(command: str) -> set[str]:
    """Every ``--flag`` the parser gives ``command``, from the parser itself."""
    for action in build_parser()._actions:  # pyright: ignore[reportPrivateUsage]
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict) and command in choices:
            subparser = cast("argparse.ArgumentParser", choices[command])  # pyright: ignore[reportUnknownVariableType]
            options = [
                option
                for sub_action in subparser._actions  # pyright: ignore[reportPrivateUsage]
                for option in sub_action.option_strings
            ]
            return {o for o in options if o.startswith("--") and o not in IGNORED_FLAGS}
    raise AssertionError(f"no command {command}")


def test_the_cli_contract_names_every_flag_of_add_rm_and_list() -> None:
    text = CLI_CONTRACT.read_text(encoding="utf-8")
    flags = [
        flag
        for command in ("add", "rm", "list")
        for flag in sorted(_option_flags(command))
    ]

    missing = [flag for flag in flags if flag not in text]

    assert not missing, f"cli-contract.md does not name {missing}"
    assert "`-j`" in text and "`--json`" in text


def _shape(text: str, anchor: str) -> str:
    """The paragraph of ``text`` that starts at ``anchor`` (a view's JSON shape)."""
    start = text.index(anchor)
    return " ".join(text[start:].split("\n\n", 1)[0].split())


def _in_order(shape: str, fields: list[str]) -> list[str]:
    """The fields that do not appear, as whole words, in this order in ``shape``."""
    missing: list[str] = []
    position = 0
    for field in fields:
        found = re.compile(rf"\b{re.escape(field)}\b").search(shape, position)
        if found is None:
            missing.append(field)
        else:
            position = found.end()
    return missing


def test_the_cli_contract_gives_each_registered_view_its_fields_in_order() -> None:
    text = CLI_CONTRACT.read_text(encoding="utf-8")
    views = {
        # concept's own fields follow it in the shape: {member, path}
        "**`programs`**": [
            name
            for field in ProgramRow.model_fields
            for name in (
                [field, *ConceptRow.model_fields] if field == "concept" else [field]
            )
        ],
        "**`members`**": list(MemberRow.model_fields),
        "**`dependencies`**": list(DependencyRow.model_fields),
    }

    for anchor, fields in views.items():
        shape = _shape(text, anchor)
        assert _in_order(shape, fields) == [], (anchor, shape)


def test_the_cli_contract_names_each_request_and_settled_field_in_backticks() -> None:
    text = CLI_CONTRACT.read_text(encoding="utf-8")
    fields = [
        *SettledEntry.model_fields,
        *AddRequest.model_fields,
        *RmRequest.model_fields,
        *ListRequest.model_fields,
    ]

    missing = [field for field in dict.fromkeys(fields) if f"`{field}" not in text]

    assert not missing, f"cli-contract.md does not name {missing}"


def test_the_rules_doc_names_the_flags_keys_codes_and_limits() -> None:
    text = RULES_DOC.read_text(encoding="utf-8")
    names = [
        "--rules",
        "--default-rules",
        "--no-rules",
        "default_rules_paths",
        "passages_max_chars",
        "amoeba list members",
        SourcesProblemKind.MISSING.value,
        SourcesProblemKind.TOO_LARGE.value,
        SourcesProblemKind.UNREADABLE.value,
        f"at most {IMPORT_DEPTH} imports deep",
        "git ls-tree",
    ]

    missing = [name for name in names if name not in text]

    assert not missing, f"rules.md does not say {missing}"
    assert text.startswith("---\n")


def test_the_mcp_doc_names_every_tool_and_the_restart_note() -> None:
    text = MCP_DOC.read_text(encoding="utf-8")

    missing = [
        f"`{name.value}`" for name in OperationName if f"`{name.value}`" not in text
    ]

    assert not missing, f"mcp-server.md does not name {missing}"
    flat = " ".join(text.split())
    assert "Restart the client session after every reinstall" in flat
    assert "`set_up` instead of `add`, `rm` and `list`" in flat


def test_the_hook_doc_names_the_kebab_command() -> None:
    text = HOOK_DOC.read_text(encoding="utf-8")

    assert 'sq config set pipeline.on_pause_command "amoeba handle-pause"' in text
