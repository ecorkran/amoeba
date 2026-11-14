"""``set_up`` and the rules choice: default, named, none (slice 229, D4, D7)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from amoeba.operations.set_up_models import (
    Change,
    ChangeSubject,
    ChangeVerb,
    SetUpOutcome,
    SetUpProblemCode,
    SetUpResult,
)
from amoeba.store.models import MemberSettings
from amoeba.store.programs import get_member
from amoeba.store.store import Store
from amoeba.store.vocabulary import RulesFrom
from operations.set_up_support import run_set_up

PROJECTS = [("provider-id", "provider")]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _member(**fields: Any) -> dict[str, Any]:
    return {"program": "demo", "members": [{"project": "provider", **fields}]}


def _run(store: Store, document: dict[str, Any]) -> SetUpResult:
    return run_set_up(store, document, projects=PROJECTS)


def _stored(store: Store) -> MemberSettings:
    with store.read() as transaction:
        member = get_member(transaction, "provider-id")
    assert member is not None
    return member.settings


def test_a_new_member_with_no_rules_field_is_added_on_the_default(
    store: Store,
) -> None:
    result = _run(store, _member())

    assert result.outcome is SetUpOutcome.APPLIED
    assert (_stored(store).rules_from, _stored(store).rules_paths) == (
        RulesFrom.CONFIG_DEFAULT,
        (),
    )
    assert result.program is not None
    assert result.program.members[0].rules_from is RulesFrom.CONFIG_DEFAULT


def test_rules_default_returns_a_named_member_to_the_default(store: Store) -> None:
    _run(store, _member(rules_paths=["CLAUDE.md"]))
    assert _stored(store).rules_from is RulesFrom.NAMED

    result = _run(store, _member(rules_default=True))

    assert result.changes == ("updated member provider-id",)
    assert (_stored(store).rules_from, _stored(store).rules_paths) == (
        RulesFrom.CONFIG_DEFAULT,
        (),
    )


def test_an_empty_rules_paths_is_a_named_choice_of_no_rules(store: Store) -> None:
    _run(store, _member())

    _run(store, _member(rules_paths=[]))

    assert (_stored(store).rules_from, _stored(store).rules_paths) == (
        RulesFrom.NAMED,
        (),
    )


def test_rules_paths_given_names_them(store: Store) -> None:
    _run(store, _member(rules_paths=["docs/rules.md"]))

    assert (_stored(store).rules_from, _stored(store).rules_paths) == (
        RulesFrom.NAMED,
        ("docs/rules.md",),
    )


def test_both_rules_fields_together_are_malformed(store: Store) -> None:
    result = _run(store, _member(rules_paths=["CLAUDE.md"], rules_default=True))

    assert result.outcome is SetUpOutcome.REJECTED
    assert [problem.code for problem in result.problems] == [SetUpProblemCode.MALFORMED]
    assert "rules_default" in result.problems[0].detail


@pytest.mark.parametrize("fields", [{}, {"rules_default": True}])
def test_a_repeat_changes_nothing(store: Store, fields: dict[str, Any]) -> None:
    _run(store, _member(**fields))

    assert _run(store, _member(**fields)).outcome is SetUpOutcome.UNCHANGED


def test_an_existing_members_rules_survive_a_request_that_omits_both(
    store: Store,
) -> None:
    _run(store, _member(rules_paths=["CLAUDE.md", "docs/*.md"]))

    result = _run(store, _member(authorize_deny=["push"]))

    assert result.outcome is SetUpOutcome.APPLIED
    assert (_stored(store).rules_from, _stored(store).rules_paths) == (
        RulesFrom.NAMED,
        ("CLAUDE.md", "docs/*.md"),
    )


def test_a_default_member_stays_default_when_a_request_omits_both(
    store: Store,
) -> None:
    _run(store, _member())

    _run(store, _member(authorize_deny=["push"]))

    assert _stored(store).rules_from is RulesFrom.CONFIG_DEFAULT


@pytest.mark.parametrize("verb", list(ChangeVerb))
@pytest.mark.parametrize("subject", list(ChangeSubject))
def test_a_change_record_reads_as_its_line(
    verb: ChangeVerb, subject: ChangeSubject
) -> None:
    record = Change(verb=verb, subject=subject, detail="x on y (from_source)")

    assert record.line == f"{verb.value} {subject.value} x on y (from_source)"


def test_the_result_carries_records_and_its_changes_are_their_lines(
    store: Store,
) -> None:
    result = _run(store, _member())

    assert [(c.verb, c.subject) for c in result.change_records] == [
        (ChangeVerb.ADDED, ChangeSubject.PROGRAM),
        (ChangeVerb.ADDED, ChangeSubject.MEMBER),
    ]
    assert result.changes == tuple(c.line for c in result.change_records)
    document = result.model_dump(mode="json")
    assert document["changes"] == list(result.changes)
    assert document["change_records"][0] == {
        "verb": "added",
        "subject": "program",
        "detail": "demo",
    }
