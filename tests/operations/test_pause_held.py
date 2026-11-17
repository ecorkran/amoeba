"""``handle_pause`` for a question that names a request (slice 242, D1, D4, 5.3)."""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from amoeba.answering.values import DeclineReason
from amoeba.operations import pause_held
from amoeba.operations.handle_pause import handle_pause
from amoeba.operations.pause_models import (
    HandlePauseOutcome,
    HandlePauseResult,
    SkipReason,
)
from amoeba.store.errors import StoreBusyError
from amoeba.store.models import QuestionRecord
from amoeba.store.notes import NewNote, insert_note
from amoeba.store.questions import get_question
from amoeba.store.store import Store
from amoeba.store.vocabulary import QuestionState, RequestState
from amoeba.upstream.squadron.run_outcome import RunOutcomeDocument, RunPoll
from operations.handle_rig import (
    KEY,
    PAUSE,
    PROJECT_ID,
    QUESTION,
    RUN,
    RUNNING_DOC,
    World,
    world,
)
from operations.held_support import (
    ADDRESSEE,
    REQUEST_ID,
    add_addressee,
    hold,
    seed_request,
)
from operations.pause_support import START, FakeChild, SpawnRecorder

BARRIER_TIMEOUT_SECONDS = 30.0


def _pause_asking(question: str) -> RunOutcomeDocument:
    """The recorded pause with ``question`` as its text."""
    assert PAUSE.checkpoint is not None
    checkpoint = PAUSE.checkpoint.model_copy(update={"question": question})
    return PAUSE.model_copy(update={"checkpoint": checkpoint})


def _marked(request_id: str = REQUEST_ID) -> str:
    return f"{QUESTION}\namoeba-request: {request_id}"


HELD_PAUSE = _pause_asking(_marked())
#: Eligibility, the resume's first look, then the run running.
HELD_POLLS: tuple[RunPoll, ...] = (HELD_PAUSE, HELD_PAUSE, RUNNING_DOC)


def _record(w: World) -> QuestionRecord:
    with w.store.read() as transaction:
        record = get_question(transaction, KEY)
    assert record is not None
    return record


def _waiting(result: HandlePauseResult, reason: DeclineReason) -> None:
    assert result.outcome is HandlePauseOutcome.WAITING_ON_PM, result
    assert result.waiting_reason is reason, result


# Holding


def test_an_accepted_request_holds_the_question_and_starts_nothing(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=(HELD_PAUSE,)) as w:
        add_addressee(w.store)
        seed_request(w.store, RequestState.ACCEPTED)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.HELD, result
        assert result.request_id == REQUEST_ID
        assert result.detail is not None and result.detail.startswith("accepted")
        record = _record(w)
        assert record.state is QuestionState.WAITING_ON_REQUEST
        assert record.request_id == REQUEST_ID
        assert w.spawned.argvs == []


def test_a_second_call_reads_the_request_again_and_stays_held(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=(HELD_PAUSE,)) as w:
        add_addressee(w.store)
        seed_request(w.store, RequestState.OPEN)
        w.handle()

        again = w.handle()

        assert again.outcome is HandlePauseOutcome.HELD, again
        assert _record(w).state is QuestionState.WAITING_ON_REQUEST
        assert w.spawned.argvs == []


def test_a_request_already_done_resumes_the_run_in_the_first_call(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=HELD_POLLS) as w:
        add_addressee(w.store)
        seed_request(w.store, RequestState.DONE)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert result.request_id == REQUEST_ID
        assert len(w.spawned.answering) == 1
        assert len(w.spawned.resumes) == 1
        assert _record(w).request_id == REQUEST_ID


def test_a_question_naming_a_request_only_in_words_takes_the_ordinary_path(
    tmp_path: Path,
) -> None:
    words = _pause_asking(f"{QUESTION} Is the {REQUEST_ID} request done yet?")
    with world(tmp_path, paused_polls=(words, words, RUNNING_DOC)) as w:
        add_addressee(w.store)
        seed_request(w.store, RequestState.OPEN)

        result = w.handle()

        assert result.outcome is HandlePauseOutcome.RESUMED, result
        assert result.request_id is None
        assert _record(w).request_id is None


# The request ends without a result


@pytest.mark.parametrize(
    ("state", "reason", "expected"),
    [
        (RequestState.DECLINED, "not now", DeclineReason.REQUEST_DECLINED),
        (RequestState.CANCELLED, "member_removed", DeclineReason.REQUEST_CANCELLED),
        (RequestState.DECLINED, None, DeclineReason.REQUEST_DECLINED),
    ],
)
def test_a_request_that_ended_sends_the_question_to_the_pm(
    tmp_path: Path, state: RequestState, reason: str | None, expected: DeclineReason
) -> None:
    with world(tmp_path, paused_polls=(HELD_PAUSE,)) as w:
        add_addressee(w.store)
        seed_request(w.store, state, reason=reason)

        result = w.handle()

        _waiting(result, expected)
        assert result.request_id == REQUEST_ID
        record = _record(w)
        assert record.state is QuestionState.WAITING_ON_PM
        assert record.waiting_reason is expected
        shown = reason or pause_held.NO_REASON_DETAIL
        assert record.waiting_detail == shown
        assert w.spawned.argvs == []


def test_an_open_request_past_its_ttl_is_expired_with_no_sweep(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=(HELD_PAUSE,)) as w:
        add_addressee(w.store)
        seed_request(
            w.store,
            RequestState.OPEN,
            now=START - timedelta(days=2),
            ttl=timedelta(days=1),
        )

        result = w.handle()

        _waiting(result, DeclineReason.REQUEST_EXPIRED)
        assert _record(w).waiting_detail == pause_held.NO_REASON_DETAIL


def test_a_held_question_whose_request_was_pruned_waits_as_unknown(
    tmp_path: Path,
) -> None:
    with world(tmp_path, paused_polls=(HELD_PAUSE,)) as w:
        hold(w)

        result = w.handle()

        _waiting(result, DeclineReason.REQUEST_UNKNOWN)
        assert "pruned" in (_record(w).waiting_detail or "")
        assert w.spawned.argvs == []


# Bad links


def _seed_note(store: Store, note_id: str) -> None:
    with store.write() as transaction:
        transaction.execute(
            "INSERT INTO messages (message_id, kind, from_member, to_member, depth, "
            "subject, body, created_at, state_changed_at) "
            "VALUES (?, 'note', ?, ?, 1, 's', 'b', ?, ?)",
            (note_id, PROJECT_ID, ADDRESSEE, START.isoformat(), START.isoformat()),
        )


@pytest.mark.parametrize("case", ["unknown", "foreign", "note", "two"])
def test_a_marker_that_resolves_to_no_one_request_waits_as_unknown(
    tmp_path: Path, case: str
) -> None:
    question = {
        "unknown": _marked("no-such-request"),
        "foreign": _marked("theirs"),
        "note": _marked("a-note"),
        "two": f"{_marked()}\namoeba-request: second-request",
    }[case]
    with world(tmp_path, paused_polls=(_pause_asking(question),)) as w:
        add_addressee(w.store)
        seed_request(w.store, RequestState.DONE)
        seed_request(w.store, RequestState.DONE, request_id="second-request")
        seed_request(
            w.store,
            RequestState.DONE,
            request_id="theirs",
            from_member=ADDRESSEE,
            to_member=PROJECT_ID,
        )
        _seed_note(w.store, "a-note")

        result = w.handle()

        _waiting(result, DeclineReason.REQUEST_UNKNOWN)
        assert result.detail
        record = _record(w)
        assert record.state is QuestionState.WAITING_ON_PM
        assert record.request_id is None
        assert w.spawned.argvs == []


def test_a_question_naming_a_note_the_members_own_agent_sent_waits_as_unknown(
    tmp_path: Path,
) -> None:
    """243 D4: a note written by ``insert_note`` is not a request, so the marker
    resolves to nothing even though the question's own member sent it."""
    with world(tmp_path, paused_polls=(_pause_asking(_marked("a-note")),)) as w:
        add_addressee(w.store)
        note = NewNote("a-note", PROJECT_ID, ADDRESSEE, None, "subject", "body")
        with w.store.write() as transaction:
            insert_note(transaction, note, [ADDRESSEE], START)

        result = w.handle()

        _waiting(result, DeclineReason.REQUEST_UNKNOWN)
        assert _record(w).state is QuestionState.WAITING_ON_PM
        assert w.spawned.argvs == []


# Races and errors


def test_two_calls_racing_on_a_done_request_claim_once(tmp_path: Path) -> None:
    with world(tmp_path, paused_polls=HELD_POLLS) as w:
        add_addressee(w.store)
        seed_request(w.store, RequestState.DONE)
        hold(w)
        both_prepared = threading.Barrier(2, timeout=BARRIER_TIMEOUT_SECONDS)
        real_cf = w.deps.cf_run
        seen: set[int] = set()

        def meet_once_per_thread(
            argv: Sequence[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            me = threading.get_ident()
            if argv[:3] == ["cf", "config", "get"] and me not in seen:
                seen.add(me)
                both_prepared.wait()
            return real_cf(argv, **kwargs)

        deps = replace(w.deps, cf_run=meet_once_per_thread)
        results: list[HandlePauseResult] = []
        errors: list[BaseException] = []

        def call() -> None:
            try:
                with Store.open(tmp_path / "amoeba.sqlite3") as own:
                    results.append(
                        handle_pause(
                            own, w.config, RUN, directory=w.directory, deps=deps
                        )
                    )
            except BaseException as error:  # noqa: BLE001 - reported by the test
                errors.append(error)

        threads = [threading.Thread(target=call) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        skips = [r for r in results if r.outcome is HandlePauseOutcome.SKIPPED]
        assert [r.skip_reason for r in skips] == [SkipReason.ALREADY_CLAIMED]
        assert len(w.spawned.answering) == 1


def test_a_store_error_on_the_request_read_raises_and_leaves_the_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with world(tmp_path, paused_polls=(HELD_PAUSE,)) as w:
        add_addressee(w.store)
        seed_request(w.store, RequestState.DONE)
        hold(w)
        before = _record(w)

        def busy(*_arguments: object) -> None:
            raise StoreBusyError("the store is busy")

        monkeypatch.setattr(pause_held, "get_message", busy)
        recorder = SpawnRecorder([FakeChild(0)])
        w.deps = replace(
            w.deps, amoeba_script=lambda: Path("/bin/amoeba"), spawn=recorder
        )

        with pytest.raises(StoreBusyError):
            w.handle()

        after = _record(w)
        assert replace(after, start_attempted_at=None) == before
        # The failed call still hands the ended request on (242 D7): one start of
        # ``handle-pause`` for this run, and no answering run.
        assert [call.argv[-1] for call in recorder.calls] == [RUN]
