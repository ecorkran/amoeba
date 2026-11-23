"""``handle_call``: one call, one transaction, no network (slice 260, D6 to D9)."""

from __future__ import annotations

import logging
import time
from contextlib import closing
from pathlib import Path

import pytest
from store.decision_support import CORE, FIRST, automatic_answer

from amoeba.config.user_config import ConfigError
from amoeba.hub import calls
from amoeba.hub.calls import DoorHooks, handle_call
from amoeba.hub.store_open import open_hub_store
from amoeba.operations import served
from amoeba.operations.served import SERVED, ServedOperation
from amoeba.store.errors import NoActingMachineError, StoreError
from amoeba.store.machines import (
    ActingMachine,
    hash_token,
    machine_for_token,
    remove_machine,
)
from amoeba.store.store import Store
from amoeba.wire.protocol import (
    HEADER_CALL_ID,
    HEADER_CLIENT_VERSION,
    HEADER_DOOR_VERSION,
    MAX_CALL_BYTES,
    SERVED_OPERATIONS,
    DoneReply,
    RefusalCode,
    RefusedReply,
)
from amoeba.wire.times import CALL_RESULT_LIFETIME_SECONDS, DOOR_VERSION
from hub.call_support import (
    ALPHA_TOKEN,
    BETA_TOKEN,
    HubRig,
    build_rig,
    make_request,
    result_of,
)


@pytest.fixture
def rig(tmp_path: Path) -> HubRig:
    return build_rig(tmp_path)


def _done(reply_bytes: object) -> DoneReply:
    assert isinstance(reply_bytes, DoneReply)
    return reply_bytes


def _refused(parsed: object, code: RefusalCode) -> RefusedReply:
    assert isinstance(parsed, RefusedReply), parsed
    assert parsed.code is code, parsed
    return parsed


def _standing_count(rig: HubRig) -> int:
    return int(rig.rows("SELECT COUNT(*) FROM standing_answers")[0][0])  # type: ignore[arg-type]


def test_hello_returns_the_machine_name_and_keeps_no_result(rig: HubRig) -> None:
    reply = rig.call("hello", {})

    assert _done(result_of(reply)).result == {"machine": "alpha"}
    assert reply.status == 200
    assert rig.rows("SELECT COUNT(*) FROM call_results") == [(0,)]


def test_each_of_the_six_runs_and_returns_its_result_document(rig: HubRig) -> None:
    with open_hub_store(rig.layout) as store:
        with store.read() as tx:
            alpha = machine_for_token(tx, hash_token(ALPHA_TOKEN))
        assert alpha is not None
        store.act_as(alpha)
        answer_seq = automatic_answer(store, FIRST, CORE, 1)

    listed = _done(result_of(rig.call("decisions", {}, call_id="c1"))).result
    marked = _done(
        result_of(rig.call("mark_read", {"through": answer_seq}, call_id="c2"))
    ).result
    given = _done(result_of(rig.call("standing", {"text": "r"}, call_id="c3"))).result
    withdrawn = _done(
        result_of(
            rig.call(
                "withdraw",
                {"standing_id": given["standing_id"], "reason": "x"},
                call_id="c4",
            )
        )
    ).result
    retracted = result_of(
        rig.call("retract", {"answer_seq": 999, "reason": "x"}, call_id="c5")
    )
    dismissed = result_of(
        rig.call("dismiss", {"run_id": "nope", "paused_at": "x"}, call_id="c6")
    )

    assert listed["outcome"] == "listed"
    assert marked["outcome"] == "moved"
    assert given["outcome"] == "given"
    assert withdrawn["outcome"] == "withdrawn"
    assert _done(retracted).result["outcome"] == "rejected"
    assert _done(dismissed).result["outcome"] == "rejected"


@pytest.mark.parametrize("token", [None, "not-a-known-token"])
def test_no_token_and_an_unknown_token_are_bad_token(
    rig: HubRig, token: str | None
) -> None:
    reply = rig.call("hello", {}, token=token)

    assert _refused(result_of(reply), RefusalCode.BAD_TOKEN)
    assert reply.status == 401


def test_a_wrong_door_version_is_refused_and_still_touches_the_machine(
    rig: HubRig,
) -> None:
    reply = rig.call("hello", {}, headers={HEADER_DOOR_VERSION: str(DOOR_VERSION + 1)})

    refused = _refused(result_of(reply), RefusalCode.DOOR_VERSION)
    assert str(DOOR_VERSION) in refused.message
    assert reply.status == 426
    assert rig.rows(
        "SELECT client_version, last_called_at FROM machines WHERE name = 'alpha'"
    ) == [("0.2.3", rig.clock_now.isoformat())]


@pytest.mark.parametrize(
    "header", [HEADER_CLIENT_VERSION, HEADER_CALL_ID], ids=["version", "call_id"]
)
@pytest.mark.parametrize(
    "value", ["bad\x1b[2Jvalue", "has space", "x" * 65, ""], ids=repr
)
def test_a_client_header_with_odd_characters_or_length_is_malformed_and_not_stored(
    rig: HubRig, header: str, value: str
) -> None:
    reply = rig.call("hello", {}, headers={header: value})

    assert _refused(result_of(reply), RefusalCode.MALFORMED_CALL)
    assert rig.rows("SELECT client_version FROM machines WHERE name = 'alpha'") == [
        ("0.2.3",) if header == HEADER_CALL_ID else (None,)
    ]
    assert rig.rows("SELECT COUNT(*) FROM call_results") == [(0,)]


def test_a_door_version_with_control_characters_is_shown_quoted(rig: HubRig) -> None:
    reply = rig.call("hello", {}, headers={HEADER_DOOR_VERSION: "9\x1b[2J" + "9" * 200})

    refused = _refused(result_of(reply), RefusalCode.DOOR_VERSION)
    assert "\x1b" not in refused.message
    assert len(refused.message) < 200


@pytest.mark.parametrize(
    "body",
    [b"not json", b'{"nodocument": 1}', b"[1, 2]", b"x" * (MAX_CALL_BYTES + 1)],
)
def test_a_bad_or_oversized_body_is_malformed(rig: HubRig, body: bytes) -> None:
    reply = rig.call("hello", {}, body=body)

    assert _refused(result_of(reply), RefusalCode.MALFORMED_CALL)
    assert reply.status == 400


def test_an_unserved_name_is_not_served(rig: HubRig) -> None:
    reply = rig.call("answer", {})

    assert _refused(result_of(reply), RefusalCode.NOT_SERVED)
    assert reply.status == 404


def test_a_reused_call_id_with_another_body_or_operation_is_refused(
    rig: HubRig,
) -> None:
    rig.call("standing", {"text": "first"}, call_id="same")

    other_body = rig.call("standing", {"text": "second"}, call_id="same")
    other_operation = rig.call(
        "withdraw", {"standing_id": 1, "reason": "x"}, call_id="same"
    )

    assert _refused(result_of(other_body), RefusalCode.CALL_ID_REUSED)
    assert _refused(result_of(other_operation), RefusalCode.CALL_ID_REUSED)
    assert _standing_count(rig) == 1


def test_a_missing_config_for_standing_is_hub_error(rig: HubRig) -> None:
    def no_config() -> object:
        raise ConfigError("no config at /nowhere")

    rig.config = no_config  # type: ignore[assignment]

    refused = _refused(
        result_of(rig.call("standing", {"text": "r"})), RefusalCode.HUB_ERROR
    )

    assert "ConfigError" in refused.message
    assert _standing_count(rig) == 0


def test_a_repeated_writing_call_returns_the_stored_reply_and_applies_once(
    rig: HubRig,
) -> None:
    first = rig.call("standing", {"text": "r"}, call_id="c1")
    again = rig.call("standing", {"text": "r"}, call_id="c1")

    assert again.body == first.body
    assert _done(result_of(again)).result["outcome"] == "given"
    assert _standing_count(rig) == 1


def test_the_same_call_id_from_a_second_machine_runs_as_a_new_call(
    rig: HubRig,
) -> None:
    rig.call("standing", {"text": "r"}, call_id="c1")

    other = rig.call("standing", {"text": "r"}, call_id="c1", token=BETA_TOKEN)

    assert _done(result_of(other)).result["outcome"] == "unchanged"
    assert rig.rows("SELECT COUNT(*) FROM call_results") == [(2,)]


def test_a_kept_result_older_than_the_lifetime_is_deleted_by_the_next_call(
    rig: HubRig,
) -> None:
    rig.call("standing", {"text": "r"}, call_id="old")
    rig.advance(seconds=CALL_RESULT_LIFETIME_SECONDS + 1)

    rig.call("decisions", {}, call_id="read")

    assert rig.rows("SELECT call_id FROM call_results") == []


def test_decisions_keeps_nothing(rig: HubRig) -> None:
    rig.call("decisions", {}, call_id="read")

    assert rig.rows("SELECT COUNT(*) FROM call_results") == [(0,)]


def test_a_bug_on_the_hub_is_hub_fault_with_the_traceback_logged(
    rig: HubRig, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("a bug on the hub")

    monkeypatch.setattr(calls, "run_served", broken)
    with caplog.at_level(logging.INFO):
        reply = rig.call("standing", {"text": "r"}, call_id="c1")

    refused = _refused(result_of(reply), RefusalCode.HUB_FAULT)
    assert "RuntimeError" in refused.message
    assert "a bug on the hub" not in refused.message
    assert any(
        record.exc_info and "a bug on the hub" in str(record.exc_info[1])
        for record in caplog.records
    )
    assert _standing_count(rig) == 0
    assert rig.rows("SELECT COUNT(*) FROM call_results") == [(0,)]
    monkeypatch.undo()
    assert _done(result_of(rig.call("standing", {"text": "r"}, call_id="c2")))


def test_a_token_removed_between_the_read_and_the_scope_is_bad_token(
    rig: HubRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = calls.machine_for_token

    def read_then_remove(transaction: object, token_hash: str) -> object:
        found = real(transaction, token_hash)  # type: ignore[arg-type]
        with open_hub_store(rig.layout) as other, other.write() as tx:
            remove_machine(tx, "alpha")
        return found

    monkeypatch.setattr(calls, "machine_for_token", read_then_remove)

    reply = rig.call("hello", {})

    assert _refused(result_of(reply), RefusalCode.BAD_TOKEN)


def test_a_run_with_act_as_skipped_fails_the_first_insert_as_hub_error(
    rig: HubRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def skip_act_as(_store: Store, _machine: ActingMachine) -> None:
        return None

    monkeypatch.setattr(Store, "act_as", skip_act_as)

    refused = _refused(
        result_of(rig.call("standing", {"text": "r"})), RefusalCode.HUB_ERROR
    )

    assert NoActingMachineError.__name__ in refused.message
    assert _standing_count(rig) == 0


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (StoreError("store is gone"), RefusalCode.HUB_ERROR),
        (RuntimeError("boom"), RefusalCode.HUB_FAULT),
    ],
)
def test_a_store_that_does_not_open_is_refused_and_touches_nothing(
    rig: HubRig, error: Exception, code: RefusalCode
) -> None:
    before = rig.rows("SELECT last_called_at FROM machines ORDER BY name")

    def failing() -> Store:
        raise error

    reply = handle_call(
        make_request("hello", {}, ALPHA_TOKEN, "c1"),
        open_store=failing,
        clock=rig.clock,
        load_config=rig.config,
    )

    assert _refused(result_of(reply), code)
    assert rig.rows("SELECT last_called_at FROM machines ORDER BY name") == before


def test_no_log_line_holds_a_token(
    rig: HubRig, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        rig.call("hello", {}, token="a-bad-token-value")
        rig.call("answer", {})
        rig.call("hello", {}, headers={HEADER_DOOR_VERSION: "99"})

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "refused" in text
    for token in (ALPHA_TOKEN, "a-bad-token-value"):
        assert token not in text


def test_a_seventh_operation_is_served_by_adding_to_the_list_and_the_registry(
    rig: HubRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def run_stub(
        store: Store, document: object, edges: object, values: object
    ) -> served.ServedResult:
        return served.MarkReadResult.model_validate(
            {"outcome": "unchanged", "previous": 1, "current": 1}
        )

    monkeypatch.setitem(
        SERVED, "stub", ServedOperation(run_stub, served.MarkReadResult)
    )
    monkeypatch.setattr(calls, "SERVED_OPERATIONS", (*SERVED_OPERATIONS, "stub"))

    reply = rig.call("stub", {"anything": 1})

    assert _done(result_of(reply)).result["outcome"] == "unchanged"


def test_hello_with_an_empty_document_keeps_no_result_and_answer_is_not_served(
    rig: HubRig,
) -> None:
    hello = rig.call("hello", {})
    unserved = rig.call("answer", {"x": 1})

    assert _done(result_of(hello)).result == {"machine": "alpha"}
    assert _refused(result_of(unserved), RefusalCode.NOT_SERVED)
    assert rig.rows("SELECT COUNT(*) FROM call_results") == [(0,)]


def test_a_store_removed_before_the_call_is_hub_error_and_no_store_is_made(
    rig: HubRig,
) -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{rig.layout.store_path}{suffix}").unlink(missing_ok=True)

    refused = _refused(result_of(rig.call("hello", {})), RefusalCode.HUB_ERROR)

    assert "HubStoreMissingError" in refused.message
    assert not rig.layout.store_path.exists()


def test_the_after_commit_hook_runs_after_the_commit_and_its_error_passes_out(
    rig: HubRig,
) -> None:
    class DropTheReply(Exception):
        pass

    def drop() -> None:
        raise DropTheReply

    with pytest.raises(DropTheReply):
        rig.call("standing", {"text": "r"}, hooks=DoorHooks(after_commit=drop))

    assert _standing_count(rig) == 1


def test_the_per_call_open_is_not_a_second_lock_wait(rig: HubRig) -> None:
    with closing(Store.open(rig.layout.store_path)) as holder, holder.write():
        began = time.monotonic()
        with open_hub_store(rig.layout) as store, store.read() as transaction:
            count = transaction.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
        elapsed = time.monotonic() - began

    assert count == 1
    assert elapsed < 1.0
