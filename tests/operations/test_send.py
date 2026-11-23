"""``send``: the stored request, resend, chains and every refusal (slice 240, D2, D8,
D9)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from cf_fixtures import OUTSIDE_ANY_PROJECT, fake_cf_run
from store.message_support import count, delivery_rows
from user_configs import user_config

from amoeba.config.user_config import UserConfig
from amoeba.operations import send_write
from amoeba.operations.deps import Deps
from amoeba.operations.errors import ContextForgeError
from amoeba.operations.message_models import (
    MAX_BODY_LENGTH,
    MAX_ID_LENGTH,
    MAX_RECORDED_LENGTH,
    MAX_REJECTIONS_PER_MEMBER,
    MAX_SUBJECT_LENGTH,
    SendOutcome,
)
from amoeba.operations.message_results import SendResult
from amoeba.operations.reject_codes import RejectCode
from amoeba.operations.send import send
from amoeba.store.message_transitions import StateFields, change_state
from amoeba.store.messages import get_message
from amoeba.store.programs import remove_member
from amoeba.store.store import Store
from amoeba.store.vocabulary import DeliveryEvent, RequestState
from operations.message_support import (
    RECIPIENT,
    RECIPIENT_NAME,
    SENDER,
    SENDER_NAME,
    STRANGER,
    THIRD_NAME,
    message_cf,
    message_deps,
    message_ids,
    open_message_store,
    rejection_rows,
    send_note_as_sender,
)
from operations.release_support import SettableClock
from operations.set_up_support import DIRECTORY

CONFIG = user_config()
#: How long the config keeps a request open.
TTL = timedelta(hours=CONFIG.request_open_ttl_hours)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    yield from open_message_store(tmp_path)


@pytest.fixture
def clock() -> SettableClock:
    return SettableClock()


@pytest.fixture
def deps(tmp_path: Path, clock: SettableClock) -> Deps:
    return message_deps(tmp_path, clock)


def _document(request_id: str = "ask-1", **fields: Any) -> dict[str, Any]:
    return {
        "id": request_id,
        "to": RECIPIENT_NAME,
        "subject": f"subject of {request_id}",
        "body": f"body of {request_id}",
        **fields,
    }


def _send(
    store: Store,
    deps: Deps,
    document: object,
    *,
    config: UserConfig = CONFIG,
) -> SendResult:
    return send(store, config, document, directory=DIRECTORY, deps=deps)


def _end(store: Store, request_id: str, state: RequestState, deps: Deps) -> None:
    """Move a stored request to ``state`` the way an operation would."""
    with store.write() as transaction:
        message = get_message(transaction, request_id)
        assert message is not None
        change_state(
            transaction,
            message,
            state,
            DeliveryEvent(state.value),
            RECIPIENT,
            deps.clock(),
            StateFields(),
        )


def test_a_request_is_stored_open_with_one_sent_delivery(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    result = _send(store, deps, _document())

    assert result.outcome is SendOutcome.SENT
    assert result.rejection is None
    assert result.problems == ()
    assert result.request is not None
    assert result.request.state is RequestState.OPEN
    assert (result.request.from_member, result.request.to_member) == (SENDER, RECIPIENT)
    assert result.request.depth == 1
    assert result.request.created_at == clock.now
    assert result.request.expires_at == clock.now + TTL
    with store.read() as transaction:
        assert delivery_rows(transaction) == [(1, RECIPIENT, "ask-1", "sent")]


def test_the_notice_is_on_every_result(store: Store, deps: Deps) -> None:
    sent = _send(store, deps, _document())
    rejected = _send(store, deps, {"id": "x"})

    assert sent.notice == rejected.notice
    assert sent.notice


def test_a_child_has_its_parents_depth_plus_one(store: Store, deps: Deps) -> None:
    _send(store, deps, _document("root"))

    child = _send(store, deps, _document("child", parent="root"))

    assert child.request is not None
    assert (child.request.depth, child.request.parent_id) == (2, "root")


def test_a_chain_may_go_max_chain_depth_deep_and_no_deeper(
    store: Store, deps: Deps
) -> None:
    previous = None
    for depth in range(1, CONFIG.max_chain_depth + 1):
        extra = {} if previous is None else {"parent": previous}
        previous = f"link-{depth}"
        result = _send(store, deps, _document(previous, **extra))
        assert result.outcome is SendOutcome.SENT

    too_deep = _send(store, deps, _document("one-more", parent=previous))

    assert too_deep.rejection is RejectCode.CHAIN_TOO_DEEP
    assert "one-more" not in message_ids(store)
    assert rejection_rows(store) == [
        (SENDER, "send", RECIPIENT_NAME, "one-more", previous or "-", "chain_too_deep")
    ]


def test_a_retry_whose_parent_was_pruned_since_is_unchanged(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _send(store, deps, _document("root"))
    _send(store, deps, _document("child", parent="root"))
    _end(store, "root", RequestState.DONE, deps)
    _end(store, "child", RequestState.ACCEPTED, deps)
    clock.now += timedelta(days=CONFIG.prune_after_days + 1)

    again = _send(store, deps, _document("child", parent="root"))

    assert again.outcome is SendOutcome.UNCHANGED
    assert "root" not in message_ids(store)
    assert rejection_rows(store) == []


def test_an_unknown_parent_is_refused_and_recorded(store: Store, deps: Deps) -> None:
    result = _send(store, deps, _document(parent="nowhere"))

    assert result.rejection is RejectCode.PARENT_UNKNOWN
    assert "nowhere" in result.problems[0]
    assert message_ids(store) == []
    assert rejection_rows(store) == [
        (SENDER, "send", RECIPIENT_NAME, "ask-1", "nowhere", "parent_unknown")
    ]


@pytest.mark.parametrize("to", [STRANGER, "no-such-name"])
def test_an_unknown_recipient_is_refused_and_recorded(
    store: Store, deps: Deps, to: str
) -> None:
    result = _send(store, deps, _document(to=to))

    assert result.rejection is RejectCode.UNKNOWN_RECIPIENT
    assert message_ids(store) == []
    assert rejection_rows(store) == [
        (SENDER, "send", to, "ask-1", "-", "unknown_recipient")
    ]


def test_a_removed_recipient_is_refused(store: Store, deps: Deps) -> None:
    with store.write() as transaction:
        remove_member(transaction, RECIPIENT, deps.clock())

    result = _send(store, deps, _document())

    assert result.rejection is RejectCode.UNKNOWN_RECIPIENT


def test_the_same_request_again_changes_nothing(store: Store, deps: Deps) -> None:
    first = _send(store, deps, _document())

    again = _send(store, deps, _document())

    assert again.outcome is SendOutcome.UNCHANGED
    assert again.request == first.request
    assert message_ids(store) == ["ask-1"]
    with store.read() as transaction:
        assert count(transaction, "deliveries") == 1
        assert count(transaction, "message_rejections") == 0


@pytest.mark.parametrize(
    "state", [RequestState.DONE, RequestState.DECLINED, RequestState.CANCELLED]
)
def test_a_resend_after_the_request_ended_names_the_state(
    store: Store, deps: Deps, state: RequestState
) -> None:
    _send(store, deps, _document())
    _end(store, "ask-1", state, deps)

    result = _send(store, deps, _document())

    assert result.rejection is RejectCode.REQUEST_ENDED
    assert state.value in result.problems[0]
    assert "new id" in result.problems[0]
    assert rejection_rows(store) == [
        (SENDER, "send", RECIPIENT_NAME, "ask-1", "-", "request_ended")
    ]


def test_a_resend_after_the_request_expired_names_expired(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _send(store, deps, _document())
    clock.now += TTL

    result = _send(store, deps, _document())

    assert result.rejection is RejectCode.REQUEST_ENDED
    assert RequestState.EXPIRED.value in result.problems[0]


def test_different_content_under_the_same_id_is_refused(
    store: Store, deps: Deps
) -> None:
    _send(store, deps, _document())

    result = _send(store, deps, _document(body="another body"))

    assert result.rejection is RejectCode.ID_REUSED
    with store.read() as transaction:
        stored = get_message(transaction, "ask-1")
    assert stored is not None
    assert stored.body == "body of ask-1"


def test_the_same_id_from_another_sender_is_refused(
    store: Store, tmp_path: Path, clock: SettableClock
) -> None:
    sender_deps = message_deps(tmp_path, clock)
    _send(store, sender_deps, _document())
    outside = message_deps(tmp_path, clock, message_cf(OUTSIDE_ANY_PROJECT))

    result = _send(
        store,
        outside,
        _document(to=SENDER_NAME, subject="mine", member=THIRD_NAME),
    )

    assert result.rejection is RejectCode.ID_REUSED


@pytest.mark.parametrize(
    ("field", "limit"),
    [("subject", MAX_SUBJECT_LENGTH), ("body", MAX_BODY_LENGTH)],
)
def test_over_limit_text_is_malformed_with_one_row_and_no_message(
    store: Store, deps: Deps, field: str, limit: int
) -> None:
    result = _send(store, deps, _document(**{field: "x" * (limit + 1)}))

    assert result.rejection is RejectCode.MALFORMED
    assert str(limit) in result.problems[0]
    assert message_ids(store) == []
    assert rejection_rows(store) == [
        (SENDER, "send", RECIPIENT_NAME, "ask-1", "-", "malformed")
    ]


def test_an_over_long_id_is_malformed_naming_the_limit(
    store: Store, deps: Deps
) -> None:
    result = _send(store, deps, _document("a" * (MAX_ID_LENGTH + 1)))

    assert result.rejection is RejectCode.MALFORMED
    assert str(MAX_ID_LENGTH) in result.problems[0]
    assert len(rejection_rows(store)) == 1


def test_a_missing_id_is_malformed_and_the_row_has_no_message_id(
    store: Store, deps: Deps
) -> None:
    document = _document()
    del document["id"]

    result = _send(store, deps, document)

    assert result.rejection is RejectCode.MALFORMED
    assert rejection_rows(store) == [
        (SENDER, "send", RECIPIENT_NAME, "-", "-", "malformed")
    ]


def test_a_document_that_is_not_an_object_is_malformed(
    store: Store, deps: Deps
) -> None:
    result = _send(store, deps, ["not", "an", "object"])

    assert result.rejection is RejectCode.MALFORMED
    assert rejection_rows(store) == [(SENDER, "send", "-", "-", "-", "malformed")]


def test_not_a_member_writes_no_row(
    store: Store, tmp_path: Path, clock: SettableClock
) -> None:
    outside = message_deps(tmp_path, clock, message_cf(OUTSIDE_ANY_PROJECT))

    result = _send(store, outside, _document())

    assert result.rejection is RejectCode.NOT_A_MEMBER
    assert rejection_rows(store) == []
    assert message_ids(store) == []


def test_a_member_mismatch_leaves_a_row_under_the_directorys_member(
    store: Store, deps: Deps
) -> None:
    result = _send(store, deps, _document(member=THIRD_NAME))

    assert result.rejection is RejectCode.MEMBER_MISMATCH
    assert message_ids(store) == []
    assert rejection_rows(store) == [
        (SENDER, "send", RECIPIENT_NAME, "ask-1", "-", "member_mismatch")
    ]


def test_an_explicit_member_sends_from_a_directory_in_no_member(
    store: Store, tmp_path: Path, clock: SettableClock
) -> None:
    outside = message_deps(tmp_path, clock, message_cf(OUTSIDE_ANY_PROJECT))

    result = _send(store, outside, _document(member=THIRD_NAME))

    assert result.outcome is SendOutcome.SENT
    assert result.request is not None
    assert result.request.from_member != SENDER


def test_a_config_change_does_not_move_an_existing_expiry(
    store: Store, deps: Deps
) -> None:
    first = _send(store, deps, _document())
    longer = CONFIG.model_copy(
        update={"request_open_ttl_hours": CONFIG.request_open_ttl_hours * 2}
    )

    again = _send(store, deps, _document(), config=longer)

    assert again.outcome is SendOutcome.UNCHANGED
    assert again.request is not None and first.request is not None
    assert again.request.expires_at == first.request.expires_at


def test_a_new_request_takes_the_configs_ttl(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    longer = CONFIG.model_copy(
        update={"request_open_ttl_hours": CONFIG.request_open_ttl_hours * 2}
    )

    result = _send(store, deps, _document(), config=longer)

    assert result.request is not None
    assert result.request.expires_at == clock.now + TTL * 2


def test_the_sweep_runs_first_so_an_expired_request_is_recorded(
    store: Store, deps: Deps, clock: SettableClock
) -> None:
    _send(store, deps, _document("old"))
    clock.now += TTL

    _send(store, deps, _document("fresh"))

    with store.read() as transaction:
        old = get_message(transaction, "old")
    assert old is not None and old.state is RequestState.EXPIRED


def test_a_send_makes_at_most_three_cf_lookups(
    store: Store, tmp_path: Path, clock: SettableClock
) -> None:
    cf = message_cf()
    counted = message_deps(tmp_path, clock, cf)

    _send(store, counted, _document(member=SENDER_NAME))

    assert len(cf.calls) == 3


def test_a_cf_failure_raises_and_writes_nothing(
    store: Store, tmp_path: Path, clock: SettableClock
) -> None:
    down = message_deps(tmp_path, clock, fake_cf_run(None))

    with pytest.raises(ContextForgeError):
        _send(store, down, _document())

    assert message_ids(store) == []
    assert rejection_rows(store) == []


def _recorded_rows(store: Store) -> list[tuple[Any, ...]]:
    with store.read() as transaction:
        return [
            tuple(row)
            for row in transaction.execute(
                "SELECT to_ref, message_id, parent_id, detail FROM message_rejections"
            )
        ]


def test_a_very_long_recipient_is_recorded_cut_and_marked(
    store: Store, deps: Deps
) -> None:
    result = _send(store, deps, _document(to="r" * 5000))

    assert result.rejection is RejectCode.UNKNOWN_RECIPIENT
    ((to_ref, message_id, parent_id, detail),) = _recorded_rows(store)
    assert len(to_ref) == MAX_RECORDED_LENGTH and to_ref.endswith("…")
    assert len(detail) <= MAX_RECORDED_LENGTH and detail.endswith("…")
    assert (message_id, parent_id) == ("ask-1", None)


def test_a_very_long_id_and_parent_are_recorded_cut_and_marked(
    store: Store, deps: Deps
) -> None:
    result = _send(store, deps, _document("i" * 5000, parent="p" * 5000))

    assert result.rejection is RejectCode.MALFORMED
    ((_, message_id, parent_id, detail),) = _recorded_rows(store)
    for kept in (message_id, parent_id):
        assert len(kept) == MAX_RECORDED_LENGTH and kept.endswith("…")
    assert len(detail) <= MAX_RECORDED_LENGTH


def test_text_within_the_recorded_bound_is_kept_whole(store: Store, deps: Deps) -> None:
    _send(store, deps, _document(to="short-name"))

    assert _recorded_rows(store)[0][0] == "short-name"


def test_a_member_keeps_only_its_newest_rejection_rows(
    store: Store, deps: Deps
) -> None:
    for number in range(MAX_REJECTIONS_PER_MEMBER + 3):
        _send(store, deps, _document(f"ask-{number}", to=f"nobody-{number}"))

    rows = _recorded_rows(store)
    assert len(rows) == MAX_REJECTIONS_PER_MEMBER
    assert rows[0][1] == "ask-3"
    assert rows[-1][1] == f"ask-{MAX_REJECTIONS_PER_MEMBER + 2}"


def test_a_sender_at_the_cap_drops_its_oldest_finished_request_to_send_another(
    store: Store, deps: Deps, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(send_write, "MAX_REQUESTS_PER_SENDER", 3)
    for name in ("a", "b", "c"):
        assert _send(store, deps, _document(name)).outcome is SendOutcome.SENT
    _end(store, "a", RequestState.DONE, deps)

    result = _send(store, deps, _document("d"))

    assert result.outcome is SendOutcome.SENT
    assert sorted(message_ids(store)) == ["b", "c", "d"]
    with store.read() as transaction:
        assert {row[2] for row in delivery_rows(transaction)} == {"b", "c", "d"}


def test_a_sender_whose_requests_are_all_live_is_refused_and_loses_nothing(
    store: Store, deps: Deps, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(send_write, "MAX_REQUESTS_PER_SENDER", 3)
    for name in ("a", "b", "c"):
        _send(store, deps, _document(name))

    result = _send(store, deps, _document("d"))

    assert result.rejection is RejectCode.TOO_MANY_OPEN
    assert sorted(message_ids(store)) == ["a", "b", "c"]
    assert rejection_rows(store) == [
        (SENDER, "send", RECIPIENT_NAME, "d", "-", "too_many_open")
    ]


def test_a_refused_send_drops_no_finished_request(
    store: Store, deps: Deps, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(send_write, "MAX_REQUESTS_PER_SENDER", 3)
    for name in ("a", "b", "c"):
        _send(store, deps, _document(name))
    _end(store, "a", RequestState.DONE, deps)

    refused = _send(store, deps, _document("d", parent="nowhere"))

    assert refused.rejection is RejectCode.PARENT_UNKNOWN
    assert sorted(message_ids(store)) == ["a", "b", "c"]


def test_finishing_a_request_frees_its_slot_at_the_cap(
    store: Store, deps: Deps, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(send_write, "MAX_REQUESTS_PER_SENDER", 2)
    for name in ("a", "b"):
        _send(store, deps, _document(name))
    assert _send(store, deps, _document("c")).rejection is RejectCode.TOO_MANY_OPEN
    _end(store, "a", RequestState.CANCELLED, deps)

    assert _send(store, deps, _document("c")).outcome is SendOutcome.SENT


def test_a_parent_that_is_a_notes_id_is_parent_unknown_naming_a_note(
    store: Store, deps: Deps
) -> None:
    send_note_as_sender(store, deps, "a-note")

    result = _send(store, deps, _document(parent="a-note"))

    assert result.rejection is RejectCode.PARENT_UNKNOWN
    assert "note" in result.problems[0]
    assert message_ids(store) == ["a-note"]


def test_wake_problem_is_null_on_a_normal_send(store: Store, deps: Deps) -> None:
    result = send(
        store,
        CONFIG,
        {"id": "plain", "to": RECIPIENT_NAME, "subject": "s", "body": "b"},
        directory=DIRECTORY,
        deps=deps,
    )

    assert result.outcome is SendOutcome.SENT
    assert result.wake_problem is None
