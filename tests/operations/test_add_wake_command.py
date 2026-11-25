"""``add`` sets, clears and keeps a member's wake command (slice 244, D1)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import DEFAULT_WORKTREE, fixture_document
from store.message_support import seed_members
from store.seed import mark_wake_wanted
from store.wake_support import seed_waking_member
from store_open import open_local_store
from user_configs import user_config

from amoeba.operations.caller import find_member
from amoeba.operations.list_registry import members_view
from amoeba.operations.names import Door
from amoeba.operations.set_up_models import (
    SetUpOutcome,
    SetUpProblemCode,
    SetUpResult,
)
from amoeba.store.checkouts import checkout_at
from amoeba.store.machines import acting_machine_id
from amoeba.store.store import Store
from amoeba.store.wakes import WakeLimits, claim_wake
from amoeba.wire.times import DOOR_VERSION
from operations.add_placed import add
from operations.set_up_support import (
    DIRECTORY,
    RECORDED_ID,
    RECORDED_NAME,
    FakeCf,
    row_counts,
    seed_member,
)

COMMAND = "wake-agent --max-seconds 60"
OTHER_COMMAND = "other-agent --cap 5"
FIELD = "wake_command"
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
RECORDED_PATH = str(fixture_document(DEFAULT_WORKTREE)["projectPath"])


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with open_local_store(tmp_path / "amoeba.sqlite3") as opened:
        yield opened


def _add(
    store: Store, document: dict[str, Any] | None = None, door: Door = Door.CLI
) -> SetUpResult:
    return add(
        store,
        user_config(),
        document or {},
        directory=DIRECTORY,
        run=FakeCf(directory_fixture=DEFAULT_WORKTREE),
        door=door,
    )


def _stored(store: Store) -> str | None:
    with store.read() as transaction:
        checkout = checkout_at(transaction, acting_machine_id(transaction), RECORDED_ID)
    assert checkout is not None
    return checkout.wake_command


def test_a_wake_command_is_set(store: Store) -> None:
    result = _add(store, {FIELD: COMMAND})

    assert result.outcome is SetUpOutcome.APPLIED
    assert _stored(store) == COMMAND


def test_null_clears_it(store: Store) -> None:
    _add(store, {FIELD: COMMAND})

    result = _add(store, {FIELD: None})

    assert result.outcome is SetUpOutcome.APPLIED
    assert _stored(store) is None


def test_omitted_leaves_an_existing_value(store: Store) -> None:
    _add(store, {FIELD: COMMAND})

    result = _add(store, {})

    assert result.outcome is SetUpOutcome.UNCHANGED
    assert _stored(store) == COMMAND


def test_a_second_add_of_other_settings_leaves_it(store: Store) -> None:
    _add(store, {FIELD: COMMAND})

    _add(store, {"rules_paths": ["docs/rules.md"]})

    assert _stored(store) == COMMAND


def test_a_new_command_replaces_the_old_one(store: Store) -> None:
    _add(store, {FIELD: COMMAND})

    _add(store, {FIELD: OTHER_COMMAND})

    assert _stored(store) == OTHER_COMMAND


def test_a_bulk_member_sets_and_a_bulk_null_clears(store: Store) -> None:
    bulk = {"program": "demo", "members": [{FIELD: COMMAND}]}
    _add(store, {"bulk": bulk})
    assert _stored(store) == COMMAND

    _add(store, {"bulk": {"program": "demo", "members": [{FIELD: None}]}})

    assert _stored(store) is None


@pytest.mark.parametrize(
    "text",
    ["", "   ", "agent 'unbalanced", "agent\0name", "agent\nsecond-line"],
    ids=["blank", "whitespace", "unbalanced-quote", "nul", "newline"],
)
def test_an_unusable_text_is_rejected_naming_the_field(store: Store, text: str) -> None:
    result = _add(store, {FIELD: text})

    assert result.outcome is SetUpOutcome.REJECTED
    assert [problem.detail.split(":")[0] for problem in result.problems] == [FIELD]


def test_a_bulk_member_with_an_unusable_text_names_its_location(store: Store) -> None:
    bulk = {"program": "demo", "members": [{FIELD: "agent 'unbalanced"}]}

    result = _add(store, {"bulk": bulk})

    assert result.outcome is SetUpOutcome.REJECTED
    assert result.problems[0].detail.startswith(f"bulk.members.0.{FIELD}")


def test_an_executable_that_does_not_exist_is_accepted(store: Store) -> None:
    result = _add(store, {FIELD: "no-such-agent-installed --flag"})

    assert result.outcome is SetUpOutcome.APPLIED


def test_list_members_returns_the_command_and_null_for_none(store: Store) -> None:
    with store.write() as transaction:
        seed_members(transaction)
        seed_waking_member(transaction, "with-command", COMMAND)
        seed_waking_member(transaction, "without-command", None)
    view = members_view(store, user_config(), program=None)

    assert {row.project_id: row.wake_command for row in view.members} == {
        "with-command": COMMAND,
        "without-command": None,
    }


@pytest.mark.parametrize(
    "document",
    [
        {FIELD: COMMAND},
        {"bulk": {"program": "demo", "members": [{FIELD: COMMAND}]}},
    ],
    ids=["single", "bulk"],
)
def test_the_operation_itself_refuses_a_door_that_may_not_set_it(
    store: Store, document: dict[str, Any]
) -> None:
    result = _add(store, document, door=Door.MCP)

    assert result.outcome is SetUpOutcome.REJECTED
    assert result.problems[0].detail.endswith("Extra inputs are not permitted")
    assert row_counts(store)["members"] == 0


def test_a_bulk_entry_for_another_member_with_a_wake_command_is_malformed(
    store: Store,
) -> None:
    seed_member(store, "demo", "other-id", "other-repo")
    other = {"program": "demo", "members": [{"project": "other-id", FIELD: COMMAND}]}

    result = add(
        store,
        user_config(),
        {"bulk": other},
        directory=DIRECTORY,
        run=FakeCf(
            directory_fixture=DEFAULT_WORKTREE, projects=[("other-id", "other-repo")]
        ),
        door=Door.CLI,
    )

    assert result.outcome is SetUpOutcome.REJECTED
    assert [problem.code for problem in result.problems] == [SetUpProblemCode.MALFORMED]
    assert "its own checkout" in result.problems[0].detail
    assert row_counts(store)["members"] == 1


def test_the_claim_after_an_add_uses_the_checkouts_path_and_command(
    store: Store,
) -> None:
    _add(store, {FIELD: COMMAND})

    with store.write() as transaction:
        member = find_member(transaction, RECORDED_NAME)
        assert member is not None
        mark_wake_wanted(transaction, member.project_id, NOW)
        wake = claim_wake(
            transaction,
            member.project_id,
            NOW,
            WakeLimits(
                timeout_seconds=60,
                max_per_day=3,
                session_stale_seconds=90,
                door_version=DOOR_VERSION,
            ),
            "w1",
            "/logs/w1",
        )

    assert wake is not None
    assert wake.command == COMMAND
    assert wake.directory == RECORDED_PATH
