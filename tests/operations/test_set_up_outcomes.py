"""``set_up`` outcomes: applied, unchanged, the read-back, and the working directory."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import (
    NON_DEFAULT_WORKTREE,
    OUTSIDE_ANY_PROJECT,
    SUBDIRECTORY,
)

from amoeba.operations.set_up import SetUpResult
from amoeba.operations.set_up_models import (
    SetUpOutcome,
    WorkingDirectoryMember,
    WorkingDirectoryNotAProject,
    WorkingDirectoryNotInProgram,
)
from amoeba.store.programs import get_member, get_pair, get_program
from amoeba.store.store import Store
from amoeba.store.vocabulary import ConsumedMode
from operations.set_up_support import RECORDED_ID, row_counts, run_set_up

PROJECTS = [("provider-id", "provider"), ("consumer-id", "consumer")]
CONCEPT_PATH = "project-documents/user/project-guides/000-concept.demo.md"


def _request(**changes: Any) -> dict[str, Any]:
    return {
        "program": "demo",
        "concept": {"member": "provider", "path": CONCEPT_PATH},
        "members": [
            {"project": "provider", "rules_paths": ["CLAUDE.md"]},
            {
                "project": "consumer",
                "rules_paths": ["CLAUDE.md", "docs/*.md"],
                "authorize_allow": ["merge_to_main"],
                "authorize_deny": ["deploy"],
                "depends_on": [{"provider": "provider", "consumed": "from_release"}],
            },
        ],
        **changes,
    }


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _run(store: Store, document: object, **options: Any) -> SetUpResult:
    return run_set_up(store, document, projects=PROJECTS, **options)


def _updated_at(store: Store) -> dict[str, datetime]:
    with store.read() as transaction:
        program = get_program(transaction, "demo")
        provider = get_member(transaction, "provider-id")
        consumer = get_member(transaction, "consumer-id")
        pair = get_pair(transaction, "provider-id", "consumer-id")
    assert program and provider and consumer and pair
    return {
        "program": program.updated_at,
        "provider": provider.updated_at,
        "consumer": consumer.updated_at,
        "pair": pair.updated_at,
    }


def test_a_valid_request_creates_everything_and_reports_one_line_per_row(
    store: Store,
) -> None:
    result = _run(store, _request())

    assert result.outcome is SetUpOutcome.APPLIED
    assert result.problems == ()
    assert len(result.changes) == 4
    assert row_counts(store) == {"programs": 1, "members": 2, "dependency_pairs": 1}
    assert result.program is not None
    assert result.program.concept is not None
    assert result.program.concept.member == "provider-id"
    consumer = next(m for m in result.program.members if m.project_id == "consumer-id")
    assert consumer.rules_paths == ("CLAUDE.md", "docs/*.md")
    assert consumer.authorize_allow == ("merge_to_main",)
    assert consumer.authorize_deny == ("deploy",)
    assert [(d.provider, d.consumed) for d in consumer.depends_on] == [
        ("provider-id", ConsumedMode.FROM_RELEASE)
    ]


def test_the_same_request_again_is_unchanged_and_keeps_every_updated_at(
    store: Store,
) -> None:
    _run(store, _request())
    before = _updated_at(store)

    result = _run(store, _request())

    assert result.outcome is SetUpOutcome.UNCHANGED
    assert result.changes == ()
    assert _updated_at(store) == before


def test_changing_one_value_changes_only_that_row(store: Store) -> None:
    _run(store, _request())
    before = _updated_at(store)
    changed = _request()
    changed["members"][1]["depends_on"][0]["consumed"] = "from_source"

    result = _run(store, changed)

    after = _updated_at(store)
    assert result.outcome is SetUpOutcome.APPLIED
    assert len(result.changes) == 1
    assert after["pair"] > before["pair"]
    assert {key: after[key] for key in ("program", "provider", "consumer")} == {
        key: before[key] for key in ("program", "provider", "consumer")
    }


def test_a_given_list_replaces_whole_and_an_omitted_one_stays(store: Store) -> None:
    _run(store, _request())

    result = _run(
        store,
        {
            "program": "demo",
            "members": [{"project": "consumer", "rules_paths": ["AGENTS.md"]}],
        },
    )

    assert result.program is not None
    consumer = next(m for m in result.program.members if m.project_id == "consumer-id")
    assert consumer.rules_paths == ("AGENTS.md",)
    assert consumer.authorize_allow == ("merge_to_main",)
    assert len(consumer.depends_on) == 1


def test_a_program_only_request_is_the_read_back(store: Store) -> None:
    _run(store, _request())

    result = _run(store, {"program": "demo"})

    assert result.outcome is SetUpOutcome.UNCHANGED
    assert result.program is not None
    assert len(result.program.members) == 2


def test_concept_null_clears_and_omitted_leaves(store: Store) -> None:
    _run(store, _request())

    omitted = _run(store, {"program": "demo"})
    cleared = _run(store, {"program": "demo", "concept": None})

    assert omitted.program is not None and omitted.program.concept is not None
    assert cleared.outcome is SetUpOutcome.APPLIED
    assert cleared.program is not None and cleared.program.concept is None


def test_the_working_directory_reports_not_in_program(store: Store) -> None:
    result = _run(store, _request())

    assert result.working_directory == WorkingDirectoryNotInProgram(
        not_in_program=RECORDED_ID
    )


def test_the_working_directory_reports_not_a_project(store: Store) -> None:
    result = _run(store, _request(), directory_fixture=OUTSIDE_ANY_PROJECT)

    assert isinstance(result.working_directory, WorkingDirectoryNotAProject)
    assert result.working_directory.not_a_project


def test_the_working_directory_reports_its_member_after_the_writes(
    store: Store,
) -> None:
    document = {
        "program": "demo",
        "members": [{"rules_paths": ["CLAUDE.md"]}],
    }

    result = _run(store, document)

    assert isinstance(result.working_directory, WorkingDirectoryMember)
    assert result.working_directory.program == "demo"
    assert result.working_directory.member.project_id == RECORDED_ID


@pytest.mark.parametrize("fixture", [NON_DEFAULT_WORKTREE, SUBDIRECTORY])
def test_an_omitted_project_from_another_view_of_the_repo_is_the_same_member(
    store: Store, fixture: str
) -> None:
    document = {"program": "demo", "members": [{"rules_paths": ["CLAUDE.md"]}]}
    first = _run(store, document)

    again = _run(store, document, directory_fixture=fixture)

    assert first.outcome is SetUpOutcome.APPLIED
    assert again.outcome is SetUpOutcome.UNCHANGED
    assert isinstance(again.working_directory, WorkingDirectoryMember)
    assert again.working_directory.member.project_id == RECORDED_ID
    assert row_counts(store)["members"] == 1
