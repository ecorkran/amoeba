"""D9: the merge observation's table, over every row."""

from __future__ import annotations

from dataclasses import replace

import pytest

from amoeba.runner.gates.merge import (
    REASON_NO_GIT,
    REASON_NO_RUN,
    REASON_ON_TARGET,
    Merged,
    NotMerged,
    Unobservable,
    merge_state,
    unobservable_reason,
)
from amoeba.store import CommandKind, JournalEntry, JournalOutcome
from runner.dispatch.dispatch_support import FIRST, entry

SLICE = 125
OWN = "125-slice.some-slice"
HEAD = "abc123"


def _entry(
    branch: str | None = OWN,
    head: str | None = HEAD,
    policy: str | None = "human",
    *,
    with_git: bool = True,
) -> JournalEntry:
    base = entry(
        CommandKind.SQ_RUN,
        "impl",
        FIRST,
        JournalOutcome.COMPLETED,
        outcome_text="completed",
    )
    git: dict[str, object] = {"branch": branch, "head": head}
    observation: dict[str, object] = {"gate": {}, **({"git": git} if with_git else {})}
    result = {**(base.result or {}), "outcome_observation": observation}
    parameters = dict(base.parameters)
    if policy is not None:
        parameters["merge_policy"] = policy
    return replace(base, result=result, parameters=parameters)


@pytest.mark.parametrize(
    ("branch", "policy", "ancestor", "expected"),
    [
        (OWN, "human", 0, Merged(HEAD)),
        (OWN, "auto", 0, Merged(HEAD)),
        ("main", "auto", 0, Merged(HEAD)),
        (OWN, "human", 1, NotMerged()),
        (OWN, "auto", 1, NotMerged()),
        ("main", "auto", 1, NotMerged()),
        ("main", "human", 0, Unobservable(REASON_ON_TARGET)),
        ("main", "human", 1, Unobservable(REASON_ON_TARGET)),
        ("main", "human", None, Unobservable(REASON_ON_TARGET)),
        (OWN, "human", 128, None),
        (OWN, "human", 2, None),
        (OWN, "human", None, None),
        (OWN, "auto", None, None),
    ],
)
def test_the_table(
    branch: str, policy: str, ancestor: int | None, expected: object
) -> None:
    assert merge_state(_entry(branch, policy=policy), SLICE, ancestor) == expected


def test_a_foreign_slice_branch_is_not_the_slices_own() -> None:
    other = _entry("126-slice.another", policy="human")

    assert merge_state(other, SLICE, 0) == Unobservable(REASON_ON_TARGET)


def test_a_slash_prefixed_branch_is_not_the_slices_own() -> None:
    prefixed = _entry(f"dev/{OWN}", policy="human")

    assert merge_state(prefixed, SLICE, 0) == Unobservable(REASON_ON_TARGET)


@pytest.mark.parametrize(
    "recorded",
    [
        _entry(None, HEAD),
        _entry(OWN, None),
        _entry(None, None),
        _entry(with_git=False),
    ],
    ids=["no branch", "no head", "neither", "no git section"],
)
def test_no_recorded_head_or_branch_is_unobservable(recorded: JournalEntry) -> None:
    assert merge_state(recorded, SLICE, 0) == Unobservable(REASON_NO_GIT)
    assert unobservable_reason(recorded, SLICE) == REASON_NO_GIT


def test_no_completed_run_is_unobservable() -> None:
    assert merge_state(None, SLICE, 0) == Unobservable(REASON_NO_RUN)


def test_an_entry_with_no_recorded_policy_is_treated_as_human() -> None:
    legacy = _entry("main", policy=None)

    assert merge_state(legacy, SLICE, 0) == Unobservable(REASON_ON_TARGET)
    assert merge_state(_entry(OWN, policy=None), SLICE, 0) == Merged(HEAD)


def test_the_unobservable_check_needs_no_read() -> None:
    assert unobservable_reason(_entry(OWN), SLICE) is None
    assert (
        unobservable_reason(_entry("main", policy="human"), SLICE) == REASON_ON_TARGET
    )
