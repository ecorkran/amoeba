"""The served list, refusal codes, reply shapes and machine names (slice 260)."""

from __future__ import annotations

import pytest

from amoeba.operations.names import OperationName
from amoeba.wire.protocol import (
    HELLO_CALL,
    REFUSAL_STATUS,
    SERVED_OPERATIONS,
    UNKNOWN_ADVICE,
    WRITING_CALLS,
    DoneReply,
    RefusalCode,
    RefusedReply,
    done_reply,
    is_machine_name,
    parse_reply,
    refused_reply,
)


def test_each_served_name_is_an_operation_name() -> None:
    names = {name.value for name in OperationName}

    assert set(SERVED_OPERATIONS) <= names


def test_hello_is_not_an_operation() -> None:
    assert HELLO_CALL not in SERVED_OPERATIONS
    assert HELLO_CALL not in {name.value for name in OperationName}


def test_writing_calls_are_served_and_decisions_is_not_one() -> None:
    assert WRITING_CALLS <= set(SERVED_OPERATIONS)
    assert "decisions" not in WRITING_CALLS
    assert len(WRITING_CALLS) == 5


def test_every_writing_call_has_advice() -> None:
    assert set(UNKNOWN_ADVICE) == WRITING_CALLS


def test_every_refusal_code_has_a_status() -> None:
    assert set(REFUSAL_STATUS) == set(RefusalCode)
    assert len(RefusalCode) == 7


def test_a_done_reply_round_trips() -> None:
    parsed = parse_reply(done_reply({"outcome": "given", "id": 3}))

    assert parsed == DoneReply(outcome="done", result={"outcome": "given", "id": 3})


def test_a_refused_reply_round_trips() -> None:
    parsed = parse_reply(refused_reply(RefusalCode.BAD_TOKEN, "no"))

    assert parsed == RefusedReply(
        outcome="refused", code=RefusalCode.BAD_TOKEN, message="no"
    )


@pytest.mark.parametrize(
    "body",
    [
        b"<html>502 Bad Gateway</html>",
        b'{"result": {}}',
        b'{"outcome": "maybe", "result": {}}',
        b'{"outcome": "refused", "code": "unheard_of", "message": "x"}',
        b"",
    ],
)
def test_a_body_that_is_not_a_reply_parses_to_none(body: bytes) -> None:
    assert parse_reply(body) is None


@pytest.mark.parametrize("name", ["alpha", "a", "laptop-2", "a.b_c", "0x"])
def test_valid_machine_names(name: str) -> None:
    assert is_machine_name(name)


@pytest.mark.parametrize("name", ["Alpha", "-alpha", "", "a b", "a" * 65, ".a"])
def test_invalid_machine_names(name: str) -> None:
    assert not is_machine_name(name)


def test_a_machine_name_of_64_characters_is_valid() -> None:
    assert is_machine_name("a" * 64)
