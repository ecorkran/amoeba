"""The text of the registered views, exact (slice 229, D3, task 8.4)."""

from __future__ import annotations

from amoeba.cli.render.registry import (
    NO_DEPENDENCIES,
    NO_MEMBERS,
    NO_PATH,
    NO_PROGRAMS,
    NOT_IN_CF,
    render_dependencies,
    render_members,
    render_programs,
)
from amoeba.cli.render.text import COLUMNS
from amoeba.operations.list_registry import (
    ConceptRow,
    DependenciesView,
    DependencyRef,
    DependencyRow,
    MemberRow,
    MembersView,
    ProgramRow,
    ProgramsView,
)
from amoeba.store.vocabulary import ConsumedMode, RulesFrom

LONG_PATH = "/Users/someone/" + "deeply/nested/" * 12 + "repo"


def _member(project_id: str, **fields: object) -> MemberRow:
    values: dict[str, object] = {
        "project_id": project_id,
        "name": project_id.removeprefix("id-"),
        "path": f"/work/{project_id.removeprefix('id-')}",
        "in_context_forge": True,
        "program": "trading",
        "rules_from": RulesFrom.CONFIG_DEFAULT,
        "rules_paths": ("CLAUDE.md", "AGENTS.md"),
        "authorize_allow": (),
        "authorize_deny": (),
        "depends_on": (),
    }
    return MemberRow.model_validate({**values, **fields})


def test_programs_with_a_concept_and_without_members() -> None:
    view = ProgramsView(
        programs=(
            ProgramRow(
                program="trading",
                concept=ConceptRow(member="id-core", path="docs/concept.md"),
                members=("id-core", "id-lint"),
            ),
            ProgramRow(program="hollow", concept=None, members=()),
        )
    )

    assert render_programs(view) == (
        "trading\n"
        "  concept: id-core (docs/concept.md)\n"
        "  members:\n"
        "    id-core\n"
        "    id-lint\n"
        "hollow\n"
        "  members: none\n"
    )


def test_no_programs() -> None:
    assert render_programs(ProgramsView(programs=())) == NO_PROGRAMS + "\n"


def test_a_default_member_and_a_named_member() -> None:
    view = MembersView(
        members=(
            _member("id-core"),
            _member(
                "id-lint",
                rules_from=RulesFrom.NAMED,
                rules_paths=("CLAUDE.md", "docs/*.md"),
                authorize_allow=("push",),
                authorize_deny=("deploy", "release"),
                depends_on=(
                    DependencyRef(
                        provider="id-core", consumed=ConsumedMode.FROM_RELEASE
                    ),
                ),
            ),
        )
    )

    assert render_members(view) == (
        "core · program trading\n"
        "  path:\n"
        "    /work/core\n"
        "  rules: default (CLAUDE.md, AGENTS.md)\n"
        "\n"
        "lint · program trading\n"
        "  path:\n"
        "    /work/lint\n"
        "  rules: CLAUDE.md, docs/*.md\n"
        "  allow: push\n"
        "  deny: deploy, release\n"
        "  depends on: core (from_release)\n"
    )


def test_named_empty_rules_say_none() -> None:
    view = MembersView(
        members=(_member("id-core", rules_from=RulesFrom.NAMED, rules_paths=()),)
    )

    assert "  rules: none\n" in render_members(view)


def test_a_project_with_no_path_says_so() -> None:
    view = MembersView(members=(_member("id-core", path=None),))

    assert f"  path: {NO_PATH}\n" in render_members(view)
    assert "  path:\n" not in render_members(view)


def test_a_project_cf_no_longer_lists_shows_its_id_and_the_marker() -> None:
    gone = _member("id-gone", name=None, path=None, in_context_forge=False)

    text = render_members(MembersView(members=(gone,)))

    assert text.splitlines()[0] == f"id-gone {NOT_IN_CF} · program trading"
    assert "path" not in text


def test_a_long_path_is_whole_on_its_own_line() -> None:
    text = render_members(MembersView(members=(_member("id-core", path=LONG_PATH),)))

    assert f"    {LONG_PATH}\n" in text
    assert len(LONG_PATH) > COLUMNS


def test_no_member_line_but_the_path_is_wider_than_the_limit() -> None:
    view = MembersView(
        members=(
            _member(
                "id-core",
                path=LONG_PATH,
                authorize_allow=tuple(f"key-{n}" for n in range(60)),
            ),
        )
    )

    lines = render_members(view).splitlines()

    assert [line for line in lines if len(line) > COLUMNS] == [f"    {LONG_PATH}"]


def test_no_members() -> None:
    assert render_members(MembersView(members=())) == NO_MEMBERS + "\n"


def test_dependencies_use_names_and_mark_a_gone_end() -> None:
    view = DependenciesView(
        dependencies=(
            DependencyRow(
                provider_id="id-core",
                provider_name="core",
                consumer_id="id-lint",
                consumer_name="lint",
                consumed=ConsumedMode.FROM_SOURCE,
            ),
            DependencyRow(
                provider_id="id-gone",
                provider_name=None,
                consumer_id="id-lint",
                consumer_name="lint",
                consumed=ConsumedMode.FROM_RELEASE,
            ),
        )
    )

    assert render_dependencies(view) == (
        f"core -> lint (from_source)\nid-gone {NOT_IN_CF} -> lint (from_release)\n"
    )


def test_no_dependencies() -> None:
    assert render_dependencies(DependenciesView(dependencies=())) == (
        NO_DEPENDENCIES + "\n"
    )


def test_a_provider_cf_does_not_name_is_marked_in_a_members_dependencies() -> None:
    view = MembersView(
        members=(
            _member(
                "id-lint",
                depends_on=(
                    DependencyRef(
                        provider="id-gone", consumed=ConsumedMode.FROM_SOURCE
                    ),
                ),
            ),
        )
    )

    assert f"  depends on: id-gone {NOT_IN_CF} (from_source)\n" in render_members(view)
