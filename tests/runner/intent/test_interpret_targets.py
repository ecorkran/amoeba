"""``interpret``: body and target rules, and the rejection reasons (D2, D3)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from amoeba.runner.intent.apply import Interpretation, interpret
from amoeba.runner.intent.vocabulary import REASON_DETAIL_LIMIT, IntentRejection
from amoeba.store import AcknowledgmentOutcome, Channel, Message, Node
from runner.lifecycle.tree_support import PROJECT, TreeBuilder

REJECTED = AcknowledgmentOutcome.REJECTED


@dataclass
class World:
    builder: TreeBuilder
    initiative: Node
    slice: Node
    orphan: Node
    step: Node

    def ask(self, payload: Any, node: Node | None = None) -> Interpretation:
        message = Message(
            seq=1,
            id="m-1",
            project_id=PROJECT,
            channel=Channel.INTENT,
            node_id=None if node is None else node.id,
            payload=payload,
        )
        return interpret(message, self.builder.tree(), None)


@pytest.fixture
def world() -> Iterator[World]:
    builder = TreeBuilder()
    initiative = builder.initiative(140)
    sliced = builder.slice(initiative, 141)
    orphan = builder.slice(initiative, 142)
    builder.orphan(orphan)
    step = builder.phase_node(sliced)
    yield World(builder, initiative, sliced, orphan, step)
    builder.close()


def _code(result: Interpretation) -> IntentRejection:
    assert result.outcome is REJECTED
    assert result.reason is not None
    return IntentRejection(result.reason.split(": ", 1)[0])


@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "launch"},
        {"intent": "drive", "untill": "tasks"},
        {"intent": "pause", "until": "tasks"},
        ["drive"],
    ],
)
def test_malformed_body_is_rejected(world: World, payload: Any) -> None:
    assert _code(world.ask(payload)) is IntentRejection.MALFORMED_BODY


def test_malformed_body_is_checked_before_the_target(world: World) -> None:
    result = world.ask({"intent": "launch"}, world.step)
    assert _code(result) is IntentRejection.MALFORMED_BODY


def test_a_step_node_target_is_rejected(world: World) -> None:
    result = world.ask({"intent": "drive"}, world.step)
    assert _code(result) is IntentRejection.TARGET_NOT_INITIATIVE_OR_SLICE


def test_an_unlinked_target_is_rejected(world: World) -> None:
    result = world.ask({"intent": "drive"}, world.orphan)
    assert _code(result) is IntentRejection.TARGET_UNLINKED


def test_an_until_is_a_malformed_body_on_any_target(world: World) -> None:
    for target in (None, world.slice):
        result = world.ask({"intent": "drive", "until": "tasks"}, target)
        assert _code(result) is IntentRejection.MALFORMED_BODY


def test_a_long_malformed_detail_is_cut(world: World) -> None:
    result = world.ask({"intent": "drive", "k" * 2000: 1})
    assert result.reason is not None
    prefix = f"{IntentRejection.MALFORMED_BODY.value}: "
    assert result.reason.startswith(prefix)
    assert len(result.reason) == len(prefix) + REASON_DETAIL_LIMIT


@pytest.mark.parametrize("target", ["project", "initiative", "slice"])
def test_a_valid_body_on_a_linked_target_is_not_rejected(
    world: World, target: str
) -> None:
    node = {"project": None, "initiative": world.initiative, "slice": world.slice}
    result = world.ask({"intent": "drive"}, node[target])
    assert result.outcome is not REJECTED
