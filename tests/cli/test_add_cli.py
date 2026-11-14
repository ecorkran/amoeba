"""``amoeba add``: its flags, the request each builds and the command run for real
(slice 229, D4, D14, task 9.5)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml
from cf_fixtures import DEFAULT_WORKTREE
from operations.set_up_support import DIRECTORY, FakeCf
from user_configs import example_config_text, user_config

from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK, EXIT_REJECTED, EXIT_USAGE
from amoeba.cli.main import main
from amoeba.cli.parser import build_parser
from amoeba.cli.registration_arguments import add_document
from amoeba.config.home import config_path, store_path
from amoeba.operations.set_up import set_up
from amoeba.store.store import Store
from cli.cli_support import (
    PROJECT_ID,
    PROJECT_NAME,
    request_file,
    result_of,
    run_amoeba,
    write_config,
)

REQUEST = {"program": "demo", "members": [{"rules_paths": ["CLAUDE.md"]}]}


def _document(*flags: str) -> dict[str, Any]:
    arguments = build_parser().parse_args(["add", *flags])
    return add_document(arguments, lambda _source: pytest.fail("no file expected"))


@pytest.mark.parametrize(
    ("flags", "document"),
    [
        ([], {}),
        (["--program", "group"], {"program": "group"}),
        (["--project", "other"], {"project": "other"}),
        (
            ["--rules", "CLAUDE.md", "--rules", "docs/*.md"],
            {"rules_paths": ["CLAUDE.md", "docs/*.md"]},
        ),
        (["--default-rules"], {"rules_default": True}),
        (["--no-rules"], {"rules_paths": []}),
        (
            ["--allow", "push", "--allow", "deploy"],
            {"authorize_allow": ["push", "deploy"]},
        ),
        (["--no-allow"], {"authorize_allow": []}),
        (["--deny", "push"], {"authorize_deny": ["push"]}),
        (["--no-deny"], {"authorize_deny": []}),
        (
            ["--depends-on", "lib", "--depends-on", "tool:from_release"],
            {
                "depends_on": [
                    {"provider": "lib"},
                    {"provider": "tool", "consumed": "from_release"},
                ]
            },
        ),
        (
            ["--concept", "me:docs/a:b.md"],
            {"concept": {"member": "me", "path": "docs/a:b.md"}},
        ),
    ],
)
def test_each_flag_builds_the_request_field_the_mapping_names(
    flags: list[str], document: dict[str, Any]
) -> None:
    assert _document(*flags) == document


def test_flags_not_given_leave_their_fields_out_of_the_request() -> None:
    document = _document("--program", "group")

    assert set(document) == {"program"}


@pytest.mark.parametrize(
    "flags",
    [
        ["--rules", "a.md", "--default-rules"],
        ["--rules", "a.md", "--no-rules"],
        ["--default-rules", "--no-rules"],
        ["--allow", "push", "--no-allow"],
        ["--deny", "push", "--no-deny"],
        ["--concept", ":docs/c.md"],
        ["--concept", "me:"],
        ["--concept", "nocolon"],
        ["--depends-on", "lib:from_nowhere"],
        ["--file", "x.yaml", "--program", "p"],
        ["--file", "x.yaml", "--no-rules"],
        ["--file", "x.yaml", "--concept", "a:b"],
        ["--file", "x.yaml", "--depends-on", "lib"],
    ],
)
def test_a_bad_flag_combination_exits_two(flags: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["add", *flags])

    assert raised.value.code == EXIT_USAGE


def test_file_alone_builds_the_bulk_request(tmp_path: Path) -> None:
    path = request_file(tmp_path, REQUEST)
    arguments = build_parser().parse_args(["add", "--file", str(path)])

    document = add_document(
        arguments, lambda source: yaml.safe_load(Path(source).read_text("utf-8"))
    )

    assert document == {"bulk": REQUEST}


def test_add_with_no_flag_registers_the_repo_in_a_program_named_for_its_project(
    tmp_path: Path,
) -> None:
    write_config()

    completed = run_amoeba(tmp_path, "add")

    assert completed.returncode == EXIT_OK, completed.stderr
    assert completed.stdout == (
        "added\n"
        f"  created program {PROJECT_NAME}\n"
        f"  added member {PROJECT_NAME}\n"
        "    rules: default (CLAUDE.md, AGENTS.md)\n"
    )


def test_add_with_no_flag_and_json_prints_the_result_document(tmp_path: Path) -> None:
    write_config()

    completed = run_amoeba(tmp_path, "add", as_json=True)

    result = result_of(completed)
    assert result["outcome"] == "applied"
    assert result["program"]["program_id"] == PROJECT_NAME
    (member,) = result["program"]["members"]
    assert (member["project_id"], member["rules_from"]) == (
        PROJECT_ID,
        "config_default",
    )


def test_a_rerun_says_unchanged(tmp_path: Path) -> None:
    write_config()
    run_amoeba(tmp_path, "add")

    completed = run_amoeba(tmp_path, "add")

    assert completed.returncode == EXIT_OK
    assert completed.stdout == "unchanged\n"


def test_rules_flags_change_the_stored_choice_and_the_text_says_so(
    tmp_path: Path,
) -> None:
    write_config()
    run_amoeba(tmp_path, "add")

    named = run_amoeba(tmp_path, "add", "--rules", "docs/rules.md")
    none = run_amoeba(tmp_path, "add", "--no-rules")
    default = run_amoeba(tmp_path, "add", "--default-rules")

    assert "    rules: docs/rules.md\n" in named.stdout
    assert named.stdout.startswith("changed\n  changed member")
    assert "    rules: none\n" in none.stdout
    assert "    rules: default (CLAUDE.md, AGENTS.md)\n" in default.stdout


def test_a_directory_with_no_project_prints_the_fix_and_exits_one(
    tmp_path: Path,
) -> None:
    write_config()

    completed = run_amoeba(tmp_path, "add", cf_fixture="outside_any_project")

    assert completed.returncode == EXIT_REJECTED
    assert completed.stdout.startswith("rejected: not_a_project: ")
    assert "    cf init\n" in completed.stdout
    assert "    amoeba add --project NAME\n" in completed.stdout
    assert not store_path().exists() or _row_count("programs") == 0


def _row_count(table: str) -> int:
    with sqlite3.connect(store_path()) as connection:
        return int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def test_file_gives_the_result_the_old_set_up_gave_for_the_same_document(
    tmp_path: Path,
) -> None:
    write_config()
    path = request_file(tmp_path, REQUEST)
    with Store.open(tmp_path / "reference.sqlite3") as reference_store:
        expected = set_up(
            reference_store,
            user_config(),
            REQUEST,
            directory=DIRECTORY,
            run=FakeCf(directory_fixture=DEFAULT_WORKTREE),
        ).model_dump(mode="json")

    completed = run_amoeba(tmp_path, "add", "--file", str(path), as_json=True)

    assert completed.returncode == EXIT_OK, completed.stderr
    assert result_of(completed) == expected


def test_a_request_from_stdin_applies(tmp_path: Path) -> None:
    write_config()

    completed = run_amoeba(
        tmp_path,
        "add",
        "--file",
        "-",
        stdin=yaml.safe_dump(REQUEST).encode(),
        as_json=True,
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    assert result_of(completed)["outcome"] == "applied"


def test_a_rejected_request_exits_one_with_the_result(tmp_path: Path) -> None:
    write_config()
    path = request_file(tmp_path, {"program": "demo"})

    completed = run_amoeba(tmp_path, "add", "--file", str(path), as_json=True)

    assert completed.returncode == EXIT_REJECTED
    assert result_of(completed)["problems"][0]["code"] == "empty_program"


def test_an_empty_request_file_is_malformed_and_registers_nothing(
    tmp_path: Path,
) -> None:
    write_config()
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")

    completed = run_amoeba(tmp_path, "add", "--file", str(path), as_json=True)

    assert completed.returncode == EXIT_REJECTED
    assert result_of(completed)["problems"][0]["code"] == "malformed"
    assert _row_count("members") == 0


def test_conflicting_single_member_flags_are_malformed_not_a_traceback(
    tmp_path: Path,
) -> None:
    write_config()

    completed = run_amoeba(
        tmp_path, "add", "--allow", "push", "--deny", "push", as_json=True
    )

    assert completed.returncode == EXIT_REJECTED
    assert result_of(completed)["problems"][0]["code"] == "malformed"
    assert "Traceback" not in completed.stderr


def test_a_non_mapping_document_is_rejected_as_malformed(tmp_path: Path) -> None:
    write_config()
    path = request_file(tmp_path, [1, 2])

    completed = run_amoeba(tmp_path, "add", "--file", str(path), as_json=True)

    assert completed.returncode == EXIT_REJECTED
    assert result_of(completed)["problems"][0]["code"] == "malformed"


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (None, "cannot read"),
        (b"program: \xff\xfe\n", "not UTF-8"),
        (b"program: [unclosed\n", "not YAML"),
    ],
)
def test_an_unusable_request_exits_two_and_creates_no_store(
    tmp_path: Path, content: bytes | None, reason: str
) -> None:
    request = tmp_path / "request.yaml"
    if content is not None:
        request.write_bytes(content)

    completed = run_amoeba(tmp_path, "add", "--file", str(request))

    assert completed.returncode == EXIT_USAGE
    assert completed.stdout == ""
    assert f"error: RequestDocumentError: {request}: {reason}" in completed.stderr
    assert not store_path().exists()


def test_a_missing_config_exits_three_naming_the_file(tmp_path: Path) -> None:
    completed = run_amoeba(tmp_path, "add")

    assert completed.returncode == EXIT_ERROR
    assert f"error: ConfigError: no config at {config_path()}" in completed.stderr


@pytest.mark.parametrize(
    "key", ["answer_limit", "default_rules_paths", "default_consumed"]
)
def test_a_config_missing_a_key_exits_three_naming_the_key(
    tmp_path: Path, key: str
) -> None:
    document = yaml.safe_load(example_config_text())
    del document[key]
    write_config(yaml.safe_dump(document))

    completed = run_amoeba(tmp_path, "add")

    assert completed.returncode == EXIT_ERROR
    assert key in completed.stderr
    assert str(config_path()) in completed.stderr


def test_a_failing_cf_exits_three_and_writes_nothing(tmp_path: Path) -> None:
    write_config()

    completed = run_amoeba(tmp_path, "add", cf_fixture=None)

    assert completed.returncode == EXIT_ERROR
    assert "error: ContextForgeError" in completed.stderr
    assert _row_count("programs") == 0
    assert _row_count("members") == 0


def test_a_store_stamped_higher_exits_three(tmp_path: Path) -> None:
    write_config()
    Store.open(store_path()).close()
    with sqlite3.connect(store_path()) as connection:
        connection.execute("UPDATE schema_meta SET version = 99")
    connection.close()

    completed = run_amoeba(tmp_path, "add")

    assert completed.returncode == EXIT_ERROR
    assert "error: StoreSchemaError" in completed.stderr


def test_a_relative_home_exits_three(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AMOEBA_HOME", "relative/home")

    completed = run_amoeba(tmp_path, "add")

    assert completed.returncode == EXIT_ERROR
    assert "error: AmoebaHomeError" in completed.stderr


def test_an_old_command_name_exits_two() -> None:
    with pytest.raises(SystemExit) as raised:
        main(["set_up", "--file", "x"])  # old-name-case

    assert raised.value.code == EXIT_USAGE


def test_cf_failing_to_list_names_still_prints_ids_and_says_so(
    tmp_path: Path,
) -> None:
    write_config()

    completed = run_amoeba(tmp_path, "add", projects=False)

    assert completed.returncode == EXIT_OK, completed.stderr
    assert f"added member {PROJECT_ID}\n" in completed.stdout
    assert "note: Context Forge names unavailable" in completed.stderr
