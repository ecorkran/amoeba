"""The text of the registered views, exact (slice 229, D3, task 8.4)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from amoeba.cli.render.registry import (
    NAMED_BY_ID,
    NO_CHECKOUT,
    NO_DEPENDENCIES,
    NO_MEMBERS,
    NO_PROGRAMS,
    render_dependencies,
    render_members,
    render_programs,
    render_standing_view,
)
from amoeba.cli.render.text import COLUMNS, ELLIPSIS
from amoeba.operations.list_registry import (
    CheckoutRow,
    ConceptRow,
    DependenciesView,
    DependencyRef,
    DependencyRow,
    MemberRow,
    MembersView,
    ProgramRow,
    ProgramsView,
    StandingRow,
    StandingView,
)
from amoeba.store.vocabulary import ConsumedMode, RulesFrom, StandingReach

LONG_PATH = "/Users/someone/" + "deeply/nested/" * 12 + "repo"


def _member(project_id: str, **fields: object) -> MemberRow:
    values: dict[str, object] = {
        "project_id": project_id,
        "name": project_id.removeprefix("id-"),
        "path": f"/work/{project_id.removeprefix('id-')}",
        "in_context_forge": True,
        "origin": None,
        "checkouts": (
            CheckoutRow(
                machine="local",
                path=f"/work/{project_id.removeprefix('id-')}",
                cf_project_id=f"cf-{project_id}",
                wake_command=None,
            ),
        ),
        "program": "trading",
        "rules_from": RulesFrom.CONFIG_DEFAULT,
        "rules_paths": ("CLAUDE.md", "AGENTS.md"),
        "authorize_allow": (),
        "authorize_deny": (),
        "wake_command": None,
        "depends_on": (),
    }
    return MemberRow.model_validate({**values, **fields})


def test_programs_with_a_concept_and_without_members() -> None:
    view = ProgramsView(
        programs=(
            ProgramRow(
                program="trading",
                concept=ConceptRow(member="id-core", path="docs/concept.md"),
                members=("id-core", "id-lint", "id-gone"),
                names={"id-core": "core", "id-lint": "lint", "id-gone": "gone"},
            ),
            ProgramRow(program="hollow", concept=None, members=(), names={}),
        )
    )

    assert render_programs(view) == (
        "trading\n"
        "  concept: core (docs/concept.md)\n"
        "  members:\n"
        "    core\n"
        "    lint\n"
        "    gone\n"
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
        "  id: id-core\n"
        "  origin: none\n"
        "  rules: default (CLAUDE.md, AGENTS.md)\n"
        "  checkouts:\n"
        "    local, Context Forge id cf-id-core\n"
        "      /work/core\n"
        "\n"
        "lint · program trading\n"
        "  id: id-lint\n"
        "  origin: none\n"
        "  rules: CLAUDE.md, docs/*.md\n"
        "  allow: push\n"
        "  deny: deploy, release\n"
        "  depends on: core (from_release)\n"
        "  checkouts:\n"
        "    local, Context Forge id cf-id-lint\n"
        "      /work/lint\n"
    )


def test_named_empty_rules_say_none() -> None:
    view = MembersView(
        members=(_member("id-core", rules_from=RulesFrom.NAMED, rules_paths=()),)
    )

    assert "  rules: none\n" in render_members(view)


def test_an_origin_and_a_checkout_on_each_machine_are_listed() -> None:
    row = _member(
        "id-core",
        origin="github.com/org/core",
        checkouts=(
            CheckoutRow(
                machine="alpha",
                path="/a/core",
                cf_project_id="cf-a",
                wake_command="wake-it",
            ),
            CheckoutRow(
                machine="beta", path="/b/core", cf_project_id="cf-b", wake_command=None
            ),
        ),
    )

    text = render_members(MembersView(members=(row,)))

    assert "  origin: github.com/org/core\n" in text
    assert (
        "  checkouts:\n"
        "    alpha, Context Forge id cf-a\n"
        "      /a/core\n"
        "      wake command:\n"
        "        wake-it\n"
        "    beta, Context Forge id cf-b\n"
        "      /b/core\n"
    ) in text


def test_a_member_with_no_checkout_is_marked() -> None:
    bare = _member("id-core", path=None, in_context_forge=False, checkouts=())

    text = render_members(MembersView(members=(bare,)))

    assert text.splitlines()[0] == f"core {NO_CHECKOUT} · program trading"
    assert "  checkouts: none\n" in text


def test_a_member_named_by_its_id_says_how_to_rename_it() -> None:
    by_id = _member("5f0c1e", name="5f0c1e")

    text = render_members(MembersView(members=(by_id,)))

    assert text.splitlines()[0] == f"5f0c1e {NAMED_BY_ID} · program trading"
    assert "  to give it a name:\n    amoeba add --project 5f0c1e --name NAME\n" in text


def test_a_long_path_is_whole_on_its_own_line() -> None:
    long = CheckoutRow(
        machine="local", path=LONG_PATH, cf_project_id="cf", wake_command=None
    )
    text = render_members(MembersView(members=(_member("id-core", checkouts=(long,)),)))

    assert f"      {LONG_PATH}\n" in text
    assert len(LONG_PATH) > COLUMNS


def test_no_member_line_but_the_path_is_wider_than_the_limit() -> None:
    long = CheckoutRow(
        machine="local", path=LONG_PATH, cf_project_id="cf", wake_command=None
    )
    view = MembersView(
        members=(
            _member(
                "id-core",
                checkouts=(long,),
                authorize_allow=tuple(f"key-{n}" for n in range(60)),
            ),
        )
    )

    lines = render_members(view).splitlines()

    assert [line for line in lines if len(line) > COLUMNS] == [f"      {LONG_PATH}"]


def test_no_members() -> None:
    assert render_members(MembersView(members=())) == NO_MEMBERS + "\n"


def test_dependencies_use_names() -> None:
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
                provider_name="gone",
                consumer_id="id-lint",
                consumer_name="lint",
                consumed=ConsumedMode.FROM_RELEASE,
            ),
        )
    )

    assert render_dependencies(view) == (
        "core -> lint (from_source)\ngone -> lint (from_release)\n"
    )


def test_no_dependencies() -> None:
    assert render_dependencies(DependenciesView(dependencies=())) == (
        NO_DEPENDENCIES + "\n"
    )


def test_a_wake_command_is_on_its_own_line_and_a_member_without_one_has_none() -> None:
    with_command = _member("id-core", wake_command="wake-agent --max-seconds 60")
    without = _member("id-lint")

    text = render_members(MembersView(members=(with_command, without)))

    assert "  wake command:\n    wake-agent --max-seconds 60\n" in text
    assert text.count("wake command") == 1


def _standing_row(text: str) -> StandingRow:
    return StandingRow(
        standing_id=1,
        reach=StandingReach.ALL,
        program=None,
        member=None,
        member_name=None,
        given_at=datetime(2026, 11, 20, 12, 0, tzinfo=UTC),
        text=text,
        withdrawn_at=None,
        withdraw_reason=None,
    )


def test_a_long_ruling_is_wrapped_to_the_width_and_never_cut() -> None:
    ruling = " ".join(["word"] * 60) + "\n\nSecond paragraph."

    text = render_standing_view(StandingView(standing=(_standing_row(ruling),)))

    body = text.splitlines()[1:]
    assert all(len(line) <= COLUMNS for line in body)
    assert " ".join(" ".join(body).split()) == " ".join(ruling.split())
    assert "" in body
    assert ELLIPSIS not in text


def test_a_withdrawn_row_without_a_reason_is_an_error() -> None:
    row = _standing_row("rule").model_copy(
        update={"withdrawn_at": datetime(2026, 11, 20, 13, 0, tzinfo=UTC)}
    )

    with pytest.raises(ValueError, match="no withdraw reason"):
        render_standing_view(StandingView(standing=(row,)))
