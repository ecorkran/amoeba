"""``list``'s registered views against a stub ``cf`` (slice 229, D3, task 7.6)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from store.question_support import NOW
from store.seed import insert_member, insert_pair, insert_program
from user_configs import user_config

from amoeba.operations.list_registry import (
    DependenciesView,
    MembersView,
    ProgramsView,
    dependencies_view,
    members_view,
    programs_view,
)
from amoeba.operations.members import ContextForgeError
from amoeba.store.programs import remove_member
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import ConsumedMode, RulesFrom
from operations.list_support import ListCf, project_entry

CONFIG = user_config()
PROJECTS = [
    project_entry("with-path-id", "with-path", "/work/with-path"),
    project_entry("no-path-id", "no-path"),
    project_entry("consumer-id", "consumer", "/work/consumer"),
]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    """``demo``: with-path (concept, named rules), no-path (default rules),
    a member CF forgot, a removed member and a consumer; ``hollow``: nothing."""
    with Store.open(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as tx:
            _seed(tx)
        yield opened


def _seed(tx: Transaction) -> None:
    _program(tx, "demo", concept=("with-path-id", "docs/concept.md"))
    _program(tx, "hollow")
    _member(tx, "with-path-id", rules=("CLAUDE.md", "docs/*.md"), allow=("push",))
    _member(tx, "no-path-id", from_default=True, deny=("deploy",))
    _member(tx, "forgotten-id", from_default=True)
    _member(tx, "removed-id")
    _member(tx, "consumer-id")
    insert_pair(
        tx,
        program_id="demo",
        provider_id="with-path-id",
        consumer_id="consumer-id",
        consumed=ConsumedMode.FROM_RELEASE,
        registered_at=NOW,
        updated_at=NOW,
    )
    remove_member(tx, "removed-id", now=NOW)


def _program(
    tx: Transaction, name: str, concept: tuple[str, str] | None = None
) -> None:
    insert_program(
        tx,
        program_id=name,
        concept_member=None if concept is None else concept[0],
        concept_path=None if concept is None else concept[1],
        registered_at=NOW,
        updated_at=NOW,
    )


def _member(  # noqa: PLR0913 - a test row's named columns
    tx: Transaction,
    project_id: str,
    *,
    rules: tuple[str, ...] = (),
    from_default: bool = False,
    allow: tuple[str, ...] = (),
    deny: tuple[str, ...] = (),
) -> None:
    insert_member(
        tx,
        project_id=project_id,
        program_id="demo",
        rules_paths=rules,
        authorize_allow=allow,
        authorize_deny=deny,
        registered_at=NOW,
        updated_at=NOW,
        rules_from=RulesFrom.CONFIG_DEFAULT if from_default else RulesFrom.NAMED,
    )


def _members(store: Store, cf: ListCf) -> MembersView:
    return members_view(store, CONFIG, cf, program=None)


def _row(view: MembersView, project_id: str) -> Any:
    (row,) = [row for row in view.members if row.project_id == project_id]
    return row


def test_a_project_with_no_path_has_a_name_and_a_null_path(store: Store) -> None:
    row = _row(_members(store, ListCf(PROJECTS)), "no-path-id")

    assert (row.name, row.path, row.in_context_forge) == ("no-path", None, True)


def test_a_project_cf_no_longer_lists_is_marked_and_has_no_name_or_path(
    store: Store,
) -> None:
    row = _row(_members(store, ListCf(PROJECTS)), "forgotten-id")

    assert (row.name, row.path, row.in_context_forge) == (None, None, False)


def test_a_removed_member_is_not_listed(store: Store) -> None:
    view = _members(store, ListCf(PROJECTS))

    assert "removed-id" not in [row.project_id for row in view.members]
    assert [row.project_id for row in view.members] == [
        "consumer-id",
        "forgotten-id",
        "no-path-id",
        "with-path-id",
    ]


def test_a_named_member_shows_its_stored_rules_and_a_default_member_the_configs(
    store: Store,
) -> None:
    view = _members(store, ListCf(PROJECTS))

    named = _row(view, "with-path-id")
    default = _row(view, "no-path-id")
    assert (named.rules_from, named.rules_paths) == (
        RulesFrom.NAMED,
        ("CLAUDE.md", "docs/*.md"),
    )
    assert (default.rules_from, default.rules_paths) == (
        RulesFrom.CONFIG_DEFAULT,
        CONFIG.default_rules_paths,
    )


def test_a_default_member_follows_a_config_edit(store: Store) -> None:
    edited = CONFIG.model_copy(update={"default_rules_paths": ("RULES.md",)})

    view = members_view(store, edited, ListCf(PROJECTS), program=None)

    assert _row(view, "no-path-id").rules_paths == ("RULES.md",)
    assert _row(view, "with-path-id").rules_paths == ("CLAUDE.md", "docs/*.md")


def test_a_member_row_carries_its_lists_and_dependencies(store: Store) -> None:
    view = _members(store, ListCf(PROJECTS))

    assert _row(view, "with-path-id").authorize_allow == ("push",)
    assert _row(view, "no-path-id").authorize_deny == ("deploy",)
    consumer = _row(view, "consumer-id")
    assert [(d.provider, d.consumed) for d in consumer.depends_on] == [
        ("with-path-id", ConsumedMode.FROM_RELEASE)
    ]
    assert _row(view, "with-path-id").depends_on == ()


def test_members_cost_one_cf_listing(store: Store) -> None:
    cf = ListCf(PROJECTS)

    _members(store, cf)

    assert cf.listings == 1


def test_the_program_filter_narrows_members(store: Store) -> None:
    view = members_view(store, CONFIG, ListCf(PROJECTS), program="hollow")

    assert view.members == ()


def test_a_program_with_no_members_is_hidden_then_shown_with_all(store: Store) -> None:
    hidden = programs_view(store, program=None, show_empty=False)
    shown = programs_view(store, program=None, show_empty=True)

    assert [row.program for row in hidden.programs] == ["demo"]
    assert [row.program for row in shown.programs] == ["demo", "hollow"]
    hollow = shown.programs[1]
    assert (hollow.concept, hollow.members) == (None, ())


def test_a_hidden_program_is_refilled_by_a_member(store: Store) -> None:
    with store.write() as tx:
        insert_member(
            tx,
            project_id="newcomer-id",
            program_id="hollow",
            rules_paths=(),
            authorize_allow=(),
            authorize_deny=(),
            registered_at=NOW,
            updated_at=NOW,
        )

    view = programs_view(store, program=None, show_empty=False)

    assert [row.program for row in view.programs] == ["demo", "hollow"]


def test_a_program_lists_its_concept_and_its_active_members_only(
    store: Store,
) -> None:
    (demo,) = programs_view(store, program="demo", show_empty=False).programs

    assert demo.concept is not None
    assert (demo.concept.member, demo.concept.path) == (
        "with-path-id",
        "docs/concept.md",
    )
    assert demo.members == ("consumer-id", "forgotten-id", "no-path-id", "with-path-id")


def test_a_program_with_only_a_concept_is_not_hidden(store: Store) -> None:
    with store.write() as tx:
        _program(tx, "conceptual", concept=("somebody", "docs/c.md"))

    view = programs_view(store, program=None, show_empty=False)

    assert "conceptual" in [row.program for row in view.programs]


def test_dependencies_name_both_ends_and_mark_a_gone_one(store: Store) -> None:
    with store.write() as tx:
        insert_pair(
            tx,
            program_id="demo",
            provider_id="forgotten-id",
            consumer_id="no-path-id",
            consumed=ConsumedMode.FROM_SOURCE,
            registered_at=NOW,
            updated_at=NOW,
        )

    view = dependencies_view(store, ListCf(PROJECTS), program=None)

    rows = {(r.provider_id, r.consumer_id): r for r in view.dependencies}
    known = rows[("with-path-id", "consumer-id")]
    assert (known.provider_name, known.consumer_name, known.consumed) == (
        "with-path",
        "consumer",
        ConsumedMode.FROM_RELEASE,
    )
    gone = rows[("forgotten-id", "no-path-id")]
    assert (gone.provider_name, gone.consumer_name) == (None, "no-path")


@pytest.mark.parametrize("view", ["members", "dependencies"])
def test_cf_failing_raises_with_no_partial_view(store: Store, view: str) -> None:
    cf = ListCf(None)

    with pytest.raises(ContextForgeError):
        if view == "members":
            _members(store, cf)
        else:
            dependencies_view(store, cf, program=None)


def test_each_views_json_has_its_documented_shape(store: Store) -> None:
    cf = ListCf(PROJECTS)

    programs = programs_view(store, program=None, show_empty=False)
    members = _members(store, cf)
    dependencies = dependencies_view(store, cf, program=None)

    assert set(programs.model_dump(mode="json")) == {"programs"}
    assert set(programs.model_dump(mode="json")["programs"][0]) == {
        "program",
        "concept",
        "members",
    }
    assert set(members.model_dump(mode="json")["members"][0]) == {
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
    assert set(dependencies.model_dump(mode="json")["dependencies"][0]) == {
        "provider_id",
        "provider_name",
        "consumer_id",
        "consumer_name",
        "consumed",
    }
    for model in (ProgramsView, MembersView, DependenciesView):
        view = {
            ProgramsView: programs,
            MembersView: members,
            DependenciesView: dependencies,
        }[model]
        assert model.model_validate(view.model_dump(mode="json")) == view
