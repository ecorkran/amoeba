"""``amoeba list``: text and ``-j``, every subject, the exit codes (slice 229, D3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fake_sq import recorded_listing, recorded_warning

from amoeba.cli.exit_codes import EXIT_ERROR, EXIT_OK, EXIT_USAGE
from amoeba.cli.main import main
from amoeba.cli.render.registry import NO_PROGRAMS
from cli.cli_support import (
    PROJECT_ID,
    PROJECT_NAME,
    result_of,
    run_amoeba,
    write_config,
)

LISTING = recorded_listing(stderr=recorded_warning())


def _registered(tmp_path: Path) -> None:
    write_config()
    assert run_amoeba(tmp_path, "add").returncode == EXIT_OK


def test_list_json_is_the_status_document(tmp_path: Path) -> None:
    _registered(tmp_path)

    listed = run_amoeba(tmp_path, "list", listing=LISTING, as_json=True)
    status = run_amoeba(tmp_path, "status", listing=LISTING, as_json=True)

    assert listed.returncode == status.returncode == EXIT_OK
    assert result_of(listed) == result_of(status)
    assert "settled" not in result_of(listed)


def test_list_all_json_adds_only_settled(tmp_path: Path) -> None:
    _registered(tmp_path)

    plain = result_of(run_amoeba(tmp_path, "list", listing=LISTING, as_json=True))
    everything = result_of(
        run_amoeba(tmp_path, "list", "--all", listing=LISTING, as_json=True)
    )

    assert everything.pop("settled") == []
    assert everything == plain


def test_list_text_is_the_status_text(tmp_path: Path) -> None:
    _registered(tmp_path)

    listed = run_amoeba(tmp_path, "list", listing=LISTING)
    status = run_amoeba(tmp_path, "status", listing=LISTING)

    assert listed.returncode == EXIT_OK, listed.stderr
    assert listed.stdout == status.stdout
    assert not listed.stdout.lstrip().startswith("{")


def test_list_all_text_adds_the_other_runs_after_the_sections_of_plain_list(
    tmp_path: Path,
) -> None:
    _registered(tmp_path)

    plain = run_amoeba(tmp_path, "list", listing=LISTING).stdout
    everything = run_amoeba(tmp_path, "list", "--all", listing=LISTING).stdout

    assert everything.startswith(plain)
    extra = everything.removeprefix(plain)
    assert extra.startswith("\nOther runs\n")
    assert f"  {PROJECT_NAME}\n    run-" in extra
    assert "Settled" not in extra  # nothing settled yet


def test_list_programs_text_and_json(tmp_path: Path) -> None:
    _registered(tmp_path)

    text = run_amoeba(tmp_path, "list", "programs").stdout
    document = result_of(run_amoeba(tmp_path, "list", "programs", as_json=True))

    assert text == f"{PROJECT_NAME}\n  members:\n    {PROJECT_ID}\n"
    assert document == {
        "programs": [
            {"program": PROJECT_NAME, "concept": None, "members": [PROJECT_ID]}
        ]
    }


def test_the_singular_subject_is_the_same_view(tmp_path: Path) -> None:
    _registered(tmp_path)

    assert (
        run_amoeba(tmp_path, "list", "program").stdout
        == run_amoeba(tmp_path, "list", "programs").stdout
    )


def test_list_members_text_and_json(tmp_path: Path) -> None:
    _registered(tmp_path)

    text = run_amoeba(tmp_path, "list", "members").stdout
    document = result_of(run_amoeba(tmp_path, "list", "members", as_json=True))

    assert text.splitlines()[0] == f"{PROJECT_NAME} · program {PROJECT_NAME}"
    assert "  rules: default (CLAUDE.md, AGENTS.md)\n" in text
    (member,) = document["members"]
    assert set(member) == {
        "project_id",
        "name",
        "path",
        "in_context_forge",
        "program",
        "rules_from",
        "rules_paths",
        "authorize_allow",
        "authorize_deny",
        "depends_on",
    }
    assert member["rules_from"] == "config_default"
    assert member["rules_paths"] == ["CLAUDE.md", "AGENTS.md"]
    assert member["name"] == PROJECT_NAME


def test_list_dependencies_text_and_json(tmp_path: Path) -> None:
    _registered(tmp_path)

    text = run_amoeba(tmp_path, "list", "dependencies").stdout
    document = result_of(run_amoeba(tmp_path, "list", "dependencies", as_json=True))

    assert text == "No dependencies.\n"
    assert document == {"dependencies": []}


def test_all_with_programs_is_accepted_and_with_members_is_a_usage_error(
    tmp_path: Path,
) -> None:
    write_config()
    accepted = run_amoeba(tmp_path, "list", "programs", "--all")

    assert accepted.returncode == EXIT_OK, accepted.stderr
    assert accepted.stdout == NO_PROGRAMS + "\n"
    for subject in ("members", "dependencies", "member", "dependency"):
        with pytest.raises(SystemExit) as raised:
            main(["list", subject, "--all"])
        assert raised.value.code == EXIT_USAGE


def test_an_unknown_subject_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as raised:
        main(["list", "everything"])

    assert raised.value.code == EXIT_USAGE


@pytest.mark.parametrize("subject", ["members", "dependencies"])
def test_a_failing_cf_exits_three(tmp_path: Path, subject: str) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, "list", subject, cf_fixture=None)

    assert completed.returncode == EXIT_ERROR
    assert "error: ContextForgeError" in completed.stderr
    assert completed.stdout == ""


def test_an_unknown_program_is_rejected_with_exit_one_and_the_known_ones_listed(
    tmp_path: Path,
) -> None:
    _registered(tmp_path)

    completed = run_amoeba(tmp_path, "list", "members", "--program", "typo")

    assert completed.returncode == 1
    assert completed.stdout.startswith("rejected: unknown_program: ")
    assert PROJECT_NAME in completed.stdout
    assert (
        json.loads(
            run_amoeba(
                tmp_path, "list", "members", "--program", "typo", as_json=True
            ).stdout
        )["rejection"]
        == "unknown_program"
    )
