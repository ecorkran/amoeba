"""``list``'s registered views, read from the store alone (slice 229, D3; 261 D13)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from store.question_support import NOW
from store.seed import insert_checkout, insert_member, insert_pair, insert_program
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.list_registry import (
    DependenciesView,
    MembersView,
    ProgramsView,
    dependencies_view,
    members_view,
    programs_view,
)
from amoeba.store.programs import remove_member
from amoeba.store.store import Store, Transaction
from amoeba.store.vocabulary import ConsumedMode, RulesFrom

CONFIG = user_config()
#: The member ids that have a checkout on the local machine, with its path.
CHECKOUT_PATHS = {
    "with-path-id": "/work/with-path",
    "no-path-id": "/work/no-path",
    "consumer-id": "/work/consumer",
}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    """``demo``: with-path (concept, named rules), no-path (default rules),
    a member with no checkout, a removed member and a consumer; ``hollow``: nothing."""
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
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
        name=project_id.removesuffix("-id"),
    )
    path = CHECKOUT_PATHS.get(project_id)
    if path is not None:
        insert_checkout(
            tx,
            member_id=project_id,
            cf_project_id=f"cf-{project_id}",
            path=path,
            now=NOW,
        )


def _members(store: Store) -> MembersView:
    return members_view(store, CONFIG, program=None)


def _row(view: MembersView, project_id: str) -> Any:
    (row,) = [row for row in view.members if row.project_id == project_id]
    return row


def test_a_member_with_a_checkout_here_has_its_name_and_path(store: Store) -> None:
    row = _row(_members(store), "no-path-id")

    assert (row.name, row.path, row.in_context_forge) == (
        "no-path",
        "/work/no-path",
        True,
    )
    assert [(c.machine, c.path, c.cf_project_id) for c in row.checkouts] == [
        ("local", "/work/no-path", "cf-no-path-id")
    ]


def test_a_member_with_no_checkout_is_marked_and_still_has_its_name(
    store: Store,
) -> None:
    row = _row(_members(store), "forgotten-id")

    assert (row.name, row.path, row.in_context_forge) == ("forgotten", None, False)
    assert row.checkouts == ()


def test_the_origin_is_listed(store: Store) -> None:
    with store.write() as tx:
        tx.execute(
            "UPDATE members SET origin = 'github.com/org/repo' "
            "WHERE project_id = 'with-path-id'"
        )

    view = _members(store)

    assert _row(view, "with-path-id").origin == "github.com/org/repo"
    assert _row(view, "no-path-id").origin is None


def test_a_removed_member_is_not_listed(store: Store) -> None:
    view = _members(store)

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
    view = _members(store)

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

    view = members_view(store, edited, program=None)

    assert _row(view, "no-path-id").rules_paths == ("RULES.md",)
    assert _row(view, "with-path-id").rules_paths == ("CLAUDE.md", "docs/*.md")


def test_a_member_row_carries_its_lists_and_dependencies(store: Store) -> None:
    view = _members(store)

    assert _row(view, "with-path-id").authorize_allow == ("push",)
    assert _row(view, "no-path-id").authorize_deny == ("deploy",)
    consumer = _row(view, "consumer-id")
    assert [(d.provider, d.consumed) for d in consumer.depends_on] == [
        ("with-path-id", ConsumedMode.FROM_RELEASE)
    ]
    assert _row(view, "with-path-id").depends_on == ()


def test_the_program_filter_narrows_members(store: Store) -> None:
    view = members_view(store, CONFIG, program="hollow")

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
            name="newcomer",
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


def test_a_program_names_its_members(store: Store) -> None:
    (demo,) = programs_view(store, program="demo", show_empty=False).programs

    assert demo.names == {
        "consumer-id": "consumer",
        "forgotten-id": "forgotten",
        "no-path-id": "no-path",
        "with-path-id": "with-path",
    }


def test_a_program_with_only_a_concept_is_not_hidden(store: Store) -> None:
    with store.write() as tx:
        _member(tx, "somebody")
        _program(tx, "conceptual", concept=("somebody", "docs/c.md"))

    view = programs_view(store, program=None, show_empty=False)

    assert "conceptual" in [row.program for row in view.programs]


def test_dependencies_name_both_ends(store: Store) -> None:
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

    view = dependencies_view(store, program=None)

    rows = {(r.provider_id, r.consumer_id): r for r in view.dependencies}
    known = rows[("with-path-id", "consumer-id")]
    assert (known.provider_name, known.consumer_name, known.consumed) == (
        "with-path",
        "consumer",
        ConsumedMode.FROM_RELEASE,
    )
    gone = rows[("forgotten-id", "no-path-id")]
    assert (gone.provider_name, gone.consumer_name) == ("forgotten", "no-path")


def test_each_views_json_has_its_documented_shape(store: Store) -> None:
    programs = programs_view(store, program=None, show_empty=False)
    members = _members(store)
    dependencies = dependencies_view(store, program=None)

    assert set(programs.model_dump(mode="json")) == {"programs"}
    assert set(programs.model_dump(mode="json")["programs"][0]) == {
        "program",
        "concept",
        "members",
        "names",
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
        "wake_command",
        "depends_on",
        "origin",
        "checkouts",
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
