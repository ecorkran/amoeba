"""``plan_member``: which member a checkout belongs to, by D7's steps (slice 261)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from store.seed import insert_checkout, insert_member, insert_program
from store_open import open_local_store

from amoeba.operations.add_member import (
    MemberPlan,
    OriginAction,
    plan_member,
)
from amoeba.operations.here_document import HereCheckout
from amoeba.operations.set_up_models import SetUpProblem, SetUpProblemCode
from amoeba.store.programs import remove_member
from amoeba.store.store import Store, Transaction

NOW = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)
ORIGIN = "github.com/org/forge"
OTHER_ORIGIN = "gitlab.example/org/forge"
FORGE_ID = "5f0c1e0000000000000000000000abcd"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        with opened.write() as transaction:
            insert_program(
                transaction,
                program_id="demo",
                concept_member=None,
                concept_path=None,
                registered_at=NOW,
                updated_at=NOW,
            )
        yield opened


def _member(
    transaction: Transaction,
    member_id: str,
    name: str,
    origin: str | None = None,
    *,
    checkout: tuple[str, str] | None = None,
    removed: bool = False,
) -> None:
    insert_member(
        transaction,
        project_id=member_id,
        program_id="demo",
        rules_paths=(),
        authorize_allow=(),
        authorize_deny=(),
        registered_at=NOW,
        updated_at=NOW,
        name=name,
        origin=origin,
    )
    if checkout is not None:
        insert_checkout(
            transaction,
            member_id=member_id,
            cf_project_id=checkout[0],
            path=checkout[1],
            now=NOW,
        )
    if removed:
        remove_member(transaction, member_id, NOW + timedelta(hours=1))


def _here(
    origin: str | None = ORIGIN, *, project: str = "cf-new", name: str = "forge"
) -> HereCheckout:
    return HereCheckout(
        project_id=project, name=name, path=f"/work/{project}", origin=origin
    )


def _plan(
    store: Store,
    here: HereCheckout,
    *,
    name: str | None = None,
    attach_to: str | None = None,
    new_member: bool = False,
    program: str | None = None,
) -> MemberPlan | SetUpProblem:
    with store.write() as transaction:
        return plan_member(
            transaction,
            here,
            name=name,
            attach_to=attach_to,
            new_member=new_member,
            program=program,
        )


def _is_plan(result: MemberPlan | SetUpProblem) -> MemberPlan:
    assert isinstance(result, MemberPlan), result
    return result


def _problem(result: MemberPlan | SetUpProblem, code: SetUpProblemCode) -> SetUpProblem:
    assert isinstance(result, SetUpProblem), result
    assert result.code is code, result
    return result


# --- --project is not planned here: it names a member (the engine's find_member) ---


# --- step 1: this checkout is on record -------------------------------------------


def test_a_checkout_on_record_is_its_members_and_attaches_nothing(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(
            transaction, FORGE_ID, "forge", ORIGIN, checkout=("cf-new", "/old/path")
        )

    plan = _is_plan(_plan(store, _here()))

    assert (plan.member_id, plan.name, plan.is_new) == (FORGE_ID, "forge", False)
    assert plan.attach is None
    assert plan.origin is None


def test_a_second_worktree_on_record_keeps_the_first_path(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, checkout=("cf-new", "/first"))
    here = HereCheckout(
        project_id="cf-new", name="forge", path="/second-worktree", origin=ORIGIN
    )

    plan = _is_plan(_plan(store, here))

    assert plan.attach is None  # the stored path stays


def test_a_missing_origin_is_recorded(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", None, checkout=("cf-new", "/p"))

    plan = _is_plan(_plan(store, _here()))

    assert plan.origin is not None
    assert (plan.origin.action, plan.origin.old, plan.origin.new) == (
        OriginAction.RECORD,
        None,
        ORIGIN,
    )


def test_a_checkout_with_no_origin_keeps_the_members(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, checkout=("cf-new", "/p"))

    plan = _is_plan(_plan(store, _here(origin=None)))

    assert plan.origin is None


def test_a_changed_origin_is_replaced_with_both_values(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, checkout=("cf-new", "/p"))

    plan = _is_plan(_plan(store, _here(origin=OTHER_ORIGIN)))

    assert plan.origin is not None
    assert (plan.origin.action, plan.origin.old, plan.origin.new) == (
        OriginAction.REPLACE,
        ORIGIN,
        OTHER_ORIGIN,
    )


def test_a_replace_to_an_origin_another_member_has_is_origin_taken(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, checkout=("cf-new", "/p"))
        _member(transaction, "lib-id", "lib", OTHER_ORIGIN)

    problem = _problem(
        _plan(store, _here(origin=OTHER_ORIGIN)), SetUpProblemCode.ORIGIN_TAKEN
    )

    assert "forge" in problem.detail
    assert "lib" in problem.detail
    assert "amoeba rm" in problem.detail
    assert OTHER_ORIGIN in problem.detail


def test_a_checkout_of_a_removed_member_is_stale_and_goes_on_to_step_two(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(
            transaction,
            FORGE_ID,
            "forge",
            ORIGIN,
            checkout=("cf-new", "/p"),
            removed=True,
        )

    plan = _is_plan(_plan(store, _here()))

    assert plan.stale_checkout_id is not None
    assert plan.reregister
    assert plan.member_id == FORGE_ID


# --- step 2: an active member has this origin --------------------------------------


@pytest.mark.parametrize("origin", [ORIGIN])
def test_the_checkout_attaches_to_the_member_with_its_origin(
    store: Store, origin: str
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "Forge-Renamed", origin, checkout=("cf-a", "/a"))

    plan = _is_plan(_plan(store, _here(origin=origin, name="forge")))

    assert (plan.member_id, plan.name, plan.is_new) == (
        FORGE_ID,
        "Forge-Renamed",
        False,
    )
    assert plan.attach is not None
    assert plan.attach.project_id == "cf-new"


# --- step 3: a removed member has this origin --------------------------------------


def test_the_most_recent_removed_member_comes_back_in_its_program(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, removed=True)

    plan = _is_plan(_plan(store, _here()))

    assert plan.reregister
    assert (plan.member_id, plan.name, plan.program_id) == (FORGE_ID, "forge", "demo")
    assert plan.attach is not None


def test_a_removed_member_comes_back_in_the_program_given(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, removed=True)

    plan = _is_plan(_plan(store, _here(), program="other"))

    assert plan.program_id == "other"


@pytest.mark.parametrize("taker", ["forge", "FORGE"])
def test_a_removed_member_whose_name_is_taken_now_is_name_taken(
    store: Store, taker: str
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, removed=True)
        _member(transaction, "other-id", taker, None)

    _problem(_plan(store, _here()), SetUpProblemCode.NAME_TAKEN)


def test_a_removed_member_whose_name_is_another_members_id_is_name_taken(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, removed=True)
        _member(transaction, "FORGE", "someone", None)

    _problem(_plan(store, _here()), SetUpProblemCode.NAME_TAKEN)


# --- step 4: a free name makes a new member ----------------------------------------


def test_a_new_member_has_a_32_hex_id_that_is_not_the_context_forge_id(
    store: Store,
) -> None:
    plan = _is_plan(_plan(store, _here(origin=None, project="project_1_x")))

    assert plan.is_new
    assert len(plan.member_id) == 32
    assert int(plan.member_id, 16) >= 0
    assert plan.member_id != "project_1_x"
    assert (plan.name, plan.program_id) == ("forge", "forge")
    assert plan.origin is None


def test_a_new_member_records_its_origin_and_takes_the_program_given(
    store: Store,
) -> None:
    plan = _is_plan(_plan(store, _here(), program="group"))

    assert plan.origin is not None
    assert plan.origin.new == ORIGIN
    assert plan.program_id == "group"


def test_name_overrides_the_context_forge_name(store: Store) -> None:
    plan = _is_plan(_plan(store, _here(), name="forge-two"))

    assert plan.name == "forge-two"


@pytest.mark.parametrize("taker", ["forge", "FORGE"])
@pytest.mark.parametrize("origin", [ORIGIN, None], ids=["with origin", "no origin"])
def test_a_context_forge_name_that_is_another_members_id_is_name_taken(
    store: Store, taker: str, origin: str | None
) -> None:
    with store.write() as transaction:
        _member(transaction, taker, "someone-else", None)

    problem = _problem(
        _plan(store, _here(origin=origin, name="forge")), SetUpProblemCode.NAME_TAKEN
    )

    assert "--name" in problem.detail
    with store.read() as transaction:
        assert transaction.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 1


def test_a_context_forge_name_with_a_space_is_malformed_naming_name(
    store: Store,
) -> None:
    problem = _problem(
        _plan(store, _here(name="has a space")), SetUpProblemCode.MALFORMED
    )

    assert "--name" in problem.detail


# --- step 5: the name is taken by an active member ---------------------------------


def test_a_taken_name_with_an_origin_shows_both_remotes_and_the_ways_on(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", OTHER_ORIGIN, checkout=("cf-a", "/a"))

    problem = _problem(_plan(store, _here()), SetUpProblemCode.NAME_TAKEN)

    assert OTHER_ORIGIN in problem.detail
    assert ORIGIN in problem.detail
    assert "--name" in problem.detail


def test_a_taken_name_whose_member_has_no_origin_says_none_recorded(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", None, checkout=("cf-a", "/a"))

    problem = _problem(_plan(store, _here()), SetUpProblemCode.NAME_TAKEN)

    assert "none recorded" in problem.detail
    assert "origin remote" in problem.detail


def test_a_taken_name_whose_member_has_no_checkout_points_at_attach_to(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", None)

    problem = _problem(_plan(store, _here()), SetUpProblemCode.NAME_TAKEN)

    assert "--attach-to forge" in problem.detail


def test_a_taken_name_with_no_origin_is_no_origin_with_the_two_ways_on(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", None, checkout=("cf-a", "/a"))

    problem = _problem(_plan(store, _here(origin=None)), SetUpProblemCode.NO_ORIGIN)

    assert "one checkout" in problem.detail
    assert "--name" in problem.detail


def test_after_a_remote_is_added_the_second_checkout_attaches(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", None, checkout=("cf-a", "/a"))
    # `add` run in the member's checkout, now that it has a remote, records the origin.
    first = _is_plan(_plan(store, _here(project="cf-a")))
    assert first.origin is not None
    with store.write() as transaction:
        transaction.execute(
            "UPDATE members SET origin = ? WHERE project_id = ?", (ORIGIN, FORGE_ID)
        )

    second = _is_plan(_plan(store, _here(project="cf-b")))

    assert second.member_id == FORGE_ID
    assert second.attach is not None


# --- --attach-to, --new-member, --name ---------------------------------------------


def test_attach_to_a_member_with_no_checkout_and_no_origin(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", None)

    plan = _is_plan(_plan(store, _here(origin=None), attach_to="forge"))

    assert (plan.member_id, plan.is_new) == (FORGE_ID, False)
    assert plan.attach is not None


def test_attach_to_a_member_that_has_a_checkout_is_member_has_checkouts(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", None, checkout=("cf-a", "/a"))

    _problem(
        _plan(store, _here(), attach_to="forge"), SetUpProblemCode.MEMBER_HAS_CHECKOUTS
    )


def test_attach_to_an_unknown_member_is_not_a_member(store: Store) -> None:
    _problem(_plan(store, _here(), attach_to="nobody"), SetUpProblemCode.NOT_A_MEMBER)


@pytest.mark.parametrize("flag", ["attach_to", "new_member"])
def test_a_flag_when_the_checkout_is_on_record_is_malformed_naming_rm_checkout(
    store: Store, flag: str
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, checkout=("cf-new", "/p"))

    result = (
        _plan(store, _here(), attach_to="forge")
        if flag == "attach_to"
        else _plan(store, _here(), new_member=True)
    )

    problem = _problem(result, SetUpProblemCode.MALFORMED)
    assert "amoeba rm --checkout" in problem.detail


def test_attach_to_an_origin_another_member_has_is_origin_taken(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", None)
        _member(transaction, "lib-id", "lib", ORIGIN, checkout=("cf-l", "/l"))

    problem = _problem(
        _plan(store, _here(), attach_to="forge"), SetUpProblemCode.ORIGIN_TAKEN
    )

    assert "forge" in problem.detail
    assert "lib" in problem.detail


def test_new_member_skips_the_origin_steps_and_needs_a_free_name(
    store: Store,
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, checkout=("cf-a", "/a"))

    taken = _plan(store, _here(), new_member=True)
    free = _is_plan(_plan(store, _here(), new_member=True, name="forge-two"))

    _problem(taken, SetUpProblemCode.NAME_TAKEN)
    assert free.is_new
    assert free.member_id != FORGE_ID
    # Another active member has this origin: the new member is created with none.
    assert free.origin is None


@pytest.mark.parametrize("given", ["FORGE-ID", "forge-id"])
def test_name_that_is_another_members_id_is_name_taken(
    store: Store, given: str
) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, checkout=("cf-a", "/a"))
        _member(transaction, "Forge-Id", "someone", None)

    _problem(_plan(store, _here(), name=given), SetUpProblemCode.NAME_TAKEN)


@pytest.mark.parametrize("bad", ["a b", "x:y", "a" * 65, ".hidden"])
def test_a_name_that_is_not_a_member_name_is_malformed_and_writes_nothing(
    store: Store, bad: str
) -> None:
    problem = _problem(_plan(store, _here(), name=bad), SetUpProblemCode.MALFORMED)

    assert "name" in problem.detail
    with store.read() as transaction:
        assert transaction.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 0


def test_name_renames_the_member_found_by_origin(store: Store) -> None:
    with store.write() as transaction:
        _member(transaction, FORGE_ID, "forge", ORIGIN, checkout=("cf-a", "/a"))

    plan = _is_plan(_plan(store, _here(), name="forge-renamed"))

    assert (plan.name, plan.renamed_from) == ("forge-renamed", "forge")
