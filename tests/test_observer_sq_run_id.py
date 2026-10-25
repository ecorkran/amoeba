"""Recovery of an ``sq_run`` entry by its run id, and the dispatcher (slice 120).

``poll_run`` is replaced by a fake that returns queued answers, the clock is
fixed, and ``sleep`` only records, so each test states exactly what Squadron
said and when.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sq_run_fixtures import sq_run_parameters

import amoeba.process.observers.sq_run_id as sq_run_id
from amoeba.process.observers.sq_run_id import (
    REASON_RESUME_RUN_MISSING,
    STATE_BEARING_OUTCOMES,
    SquadronRunIdObserver,
    SquadronRunObserver,
)
from amoeba.process.observers.sq_runs import RunsDirectoryScan, SquadronRunsObserver
from amoeba.process.recovery import Adopt, InFlight, NotApplied, Observation, Unknown
from amoeba.process.sq_outcome import PollFailure, RunOutcome, RunOutcomeDocument
from amoeba.store.journal_models import (
    PARAM_CONTINUATION,
    PARAM_CONTINUES,
    PARAM_RUN_ID,
    CommandKind,
    JournalEntry,
)

RUN_ID = "run-20261022-p5-aaaa1111"
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
GRACE_SECONDS = 60.0
POLL_TIMEOUT_SECONDS = 7.0
ENTRY_ID = "entry-1"


class FakePoll:
    """Stands in for ``poll_run``: answers from a queue and records the calls."""

    def __init__(self, *answers: RunOutcomeDocument | PollFailure) -> None:
        self._answers = list(answers)
        self.calls: list[tuple[str, float]] = []

    def __call__(
        self, run_id: str, *, timeout_seconds: float
    ) -> RunOutcomeDocument | PollFailure:
        self.calls.append((run_id, timeout_seconds))
        assert self._answers, "poll_run was called more often than the test queued"
        return self._answers.pop(0)


def _document(outcome: RunOutcome, status: str | None = None) -> RunOutcomeDocument:
    return RunOutcomeDocument(run_id=RUN_ID, outcome=outcome, status=status)


def _entry(
    *,
    issued_at: datetime | None = NOW - timedelta(seconds=600),
    parameters: dict[str, object] | None = None,
) -> JournalEntry:
    return JournalEntry(
        id=ENTRY_ID,
        project_id="demo",
        node_id="node-1",
        kind=CommandKind.SQ_RUN,
        parameters=(
            parameters
            if parameters is not None
            else sq_run_parameters({"pipeline": "p5", "params": {}}, run_id=RUN_ID)
        ),
        issued_at=issued_at,
    )


class Rig:
    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *answers: RunOutcomeDocument | PollFailure,
        claimed: dict[str, str] | None = None,
        claimed_nodes: dict[str, str] | None = None,
    ) -> None:
        self.poll = FakePoll(*answers)
        self.sleeps: list[float] = []
        monkeypatch.setattr(sq_run_id, "poll_run", self.poll)
        self.observer = SquadronRunIdObserver(
            launch_grace_seconds=GRACE_SECONDS,
            poll_timeout_seconds=POLL_TIMEOUT_SECONDS,
            claimed_run_ids=claimed,
            claimed_run_nodes=claimed_nodes,
            now=lambda: NOW,
            sleep=self.sleeps.append,
        )

    def observe(self, entry: JournalEntry) -> Observation:
        return self.observer.observe(entry)


# 1. State-bearing outcomes are left in flight ----


def test_six_outcomes_are_state_bearing() -> None:
    assert STATE_BEARING_OUTCOMES == {
        RunOutcome.COMPLETED,
        RunOutcome.FAILED,
        RunOutcome.PAUSED,
        RunOutcome.TIMED_OUT,
        RunOutcome.UNKNOWN_STATUS,
        RunOutcome.ORPHANED,
    }


@pytest.mark.parametrize("outcome", sorted(STATE_BEARING_OUTCOMES))
def test_every_state_bearing_outcome_is_left_in_flight(
    monkeypatch: pytest.MonkeyPatch, outcome: RunOutcome
) -> None:
    rig = Rig(monkeypatch, _document(outcome, status="some-status"))

    observation = rig.observe(_entry())

    assert observation == InFlight(run_id=RUN_ID, status=outcome.value)
    assert rig.poll.calls == [(RUN_ID, POLL_TIMEOUT_SECONDS)]
    assert rig.sleeps == []


# 2. Unreadable and poll failures escalate ---------------------------------


def test_unreadable_escalates(monkeypatch: pytest.MonkeyPatch) -> None:
    rig = Rig(monkeypatch, _document(RunOutcome.UNREADABLE))

    observation = rig.observe(_entry())

    assert isinstance(observation, Unknown)
    assert RUN_ID in observation.reason
    assert "unreadable" in observation.reason


def test_a_poll_failure_escalates_with_its_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(monkeypatch, PollFailure("`sq` was not found on PATH (run x)"))

    observation = rig.observe(_entry())

    assert observation == Unknown(reason="`sq` was not found on PATH (run x)")
    assert rig.sleeps == []


# 3. Unusable run ids escalate ---------------------------------------------


@pytest.mark.parametrize("bad_value", [42, "", None, ["run-x"]])
def test_a_run_id_that_is_not_a_non_empty_string_escalates_naming_it(
    monkeypatch: pytest.MonkeyPatch, bad_value: object
) -> None:
    rig = Rig(monkeypatch)
    entry = _entry(parameters={"pipeline": "p5", "params": {}, PARAM_RUN_ID: bad_value})

    observation = rig.observe(entry)

    assert isinstance(observation, Unknown)
    assert repr(bad_value) in observation.reason
    assert rig.poll.calls == []


# 4. A claimed id is never adopted twice -----------------------------------


def test_a_run_claimed_by_another_entry_escalates_without_polling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(monkeypatch, claimed={RUN_ID: "some-other-entry"})

    observation = rig.observe(_entry())

    assert isinstance(observation, Unknown)
    assert "some-other-entry" in observation.reason
    assert rig.poll.calls == []


# 5. not_found past grace, and without issued_at ---------------------------


def test_not_found_past_the_grace_period_is_not_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(monkeypatch, _document(RunOutcome.NOT_FOUND))

    observation = rig.observe(_entry(issued_at=NOW - timedelta(seconds=61)))

    assert observation == NotApplied(
        f"no run state for {RUN_ID} after the launch grace period"
    )
    assert rig.sleeps == []
    assert len(rig.poll.calls) == 1


def test_not_found_exactly_at_the_end_of_grace_is_not_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(monkeypatch, _document(RunOutcome.NOT_FOUND))

    observation = rig.observe(_entry(issued_at=NOW - timedelta(seconds=60)))

    assert isinstance(observation, NotApplied)
    assert rig.sleeps == []


def test_not_found_with_a_naive_issued_at_escalates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(monkeypatch, _document(RunOutcome.NOT_FOUND))

    observation = rig.observe(_entry(issued_at=NOW.replace(tzinfo=None)))

    assert isinstance(observation, Unknown)
    assert "naive" in observation.reason
    assert rig.sleeps == []


def test_not_found_with_no_issued_at_escalates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(monkeypatch, _document(RunOutcome.NOT_FOUND))

    observation = rig.observe(_entry(issued_at=None))

    assert isinstance(observation, Unknown)
    assert "issued_at" in observation.reason
    assert rig.sleeps == []


# 6. not_found inside grace: wait out the remainder, ask once more ---------


def test_in_grace_it_sleeps_the_remainder_then_leaves_a_run_that_appeared_in_flight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(
        monkeypatch,
        _document(RunOutcome.NOT_FOUND),
        _document(RunOutcome.TIMED_OUT, status="running"),
    )

    observation = rig.observe(_entry(issued_at=NOW - timedelta(seconds=45)))

    assert observation == InFlight(run_id=RUN_ID, status=RunOutcome.TIMED_OUT.value)
    assert rig.sleeps == [15.0]
    assert len(rig.poll.calls) == 2


def test_in_grace_it_is_not_applied_when_the_second_poll_still_finds_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(
        monkeypatch, _document(RunOutcome.NOT_FOUND), _document(RunOutcome.NOT_FOUND)
    )

    observation = rig.observe(_entry(issued_at=NOW - timedelta(seconds=45)))

    assert isinstance(observation, NotApplied)
    assert rig.sleeps == [15.0]
    assert len(rig.poll.calls) == 2


def test_in_grace_it_escalates_when_the_second_poll_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(
        monkeypatch, _document(RunOutcome.NOT_FOUND), PollFailure("sq hung (run x)")
    )

    observation = rig.observe(_entry(issued_at=NOW - timedelta(seconds=45)))

    assert observation == Unknown(reason="sq hung (run x)")
    assert len(rig.poll.calls) == 2


def test_in_grace_it_never_polls_a_third_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(
        monkeypatch, _document(RunOutcome.NOT_FOUND), _document(RunOutcome.NOT_FOUND)
    )

    rig.observe(_entry(issued_at=NOW))

    assert len(rig.poll.calls) == 2
    assert len(rig.sleeps) == 1


# 7. issued_at ahead of the clock ------------------------------------------


def test_an_issued_at_ahead_of_the_clock_cannot_stretch_the_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(
        monkeypatch, _document(RunOutcome.NOT_FOUND), _document(RunOutcome.NOT_FOUND)
    )

    rig.observe(_entry(issued_at=NOW + timedelta(hours=2)))

    assert rig.sleeps == [GRACE_SECONDS]


# The dispatcher ------------------------------------------------------------


class RecordingObserver:
    def __init__(self, answer: Observation) -> None:
        self._answer = answer
        self.seen: list[str] = []

    def observe(self, entry: JournalEntry) -> Observation:
        self.seen.append(entry.id)
        return self._answer


class ScanTrap(SquadronRunsObserver):
    """A legacy matcher that records use and fails if its scan is touched."""

    def __init__(self, answer: Observation) -> None:
        super().__init__(Path("/nonexistent"), clock_tolerance_seconds=0.0)
        self._answer = answer
        self.seen: list[str] = []

    @property
    def scan(self) -> RunsDirectoryScan:
        raise AssertionError("the legacy scan was touched")

    def observe(self, entry: JournalEntry) -> Observation:
        self.seen.append(entry.id)
        return self._answer


def test_the_dispatcher_routes_by_the_presence_of_the_run_id_key() -> None:
    by_id = RecordingObserver(Adopt(result={"via": "id"}))
    legacy = ScanTrap(Unknown(reason="legacy"))
    dispatcher = SquadronRunObserver(by_id=by_id, legacy=legacy)

    with_id = dispatcher.observe(_entry())
    without_id = dispatcher.observe(_entry(parameters={"pipeline": "p5", "params": {}}))

    assert with_id == Adopt(result={"via": "id"})
    assert without_id == Unknown(reason="legacy")
    assert by_id.seen == [ENTRY_ID]
    assert legacy.seen == [ENTRY_ID]


def test_an_id_bearing_entry_never_touches_the_legacy_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(monkeypatch, _document(RunOutcome.COMPLETED, status="completed"))
    legacy = ScanTrap(Unknown(reason="legacy"))
    dispatcher = SquadronRunObserver(by_id=rig.observer, legacy=legacy)

    observation = dispatcher.observe(_entry())

    assert isinstance(observation, InFlight)
    assert legacy.seen == []


# 7. Continuation entries (slice 127) ---------------------------------------


def _continuation(**overrides: object) -> JournalEntry:
    parameters = sq_run_parameters({"pipeline": "p5", "params": {}}, run_id=RUN_ID)
    parameters.update({PARAM_CONTINUATION: "retry", PARAM_CONTINUES: "entry-0"})
    parameters.update(overrides)
    return _entry(parameters=parameters)


def test_a_continuation_ignores_a_claim_on_its_own_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(
        monkeypatch,
        _document(RunOutcome.PAUSED),
        claimed={RUN_ID: "entry-0"},
        claimed_nodes={RUN_ID: "node-1"},
    )

    assert isinstance(rig.observe(_continuation()), InFlight)


def test_a_continuation_still_escalates_on_a_claim_from_another_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(
        monkeypatch,
        claimed={RUN_ID: "entry-0"},
        claimed_nodes={RUN_ID: "node-2"},
    )

    answer = rig.observe(_continuation())

    assert isinstance(answer, Unknown)
    assert rig.poll.calls == []


def test_an_entry_without_the_key_keeps_the_guard_on_its_own_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(
        monkeypatch,
        claimed={RUN_ID: "entry-0"},
        claimed_nodes={RUN_ID: "node-1"},
    )

    assert isinstance(rig.observe(_entry()), Unknown)


@pytest.mark.parametrize("continuation", ["retry", "accept", "observe"])
def test_continuation_never_reissued(
    monkeypatch: pytest.MonkeyPatch, continuation: str
) -> None:
    """No run state after the grace period is Unknown: NotApplied reissues."""
    rig = Rig(monkeypatch, _document(RunOutcome.NOT_FOUND))

    answer = rig.observe(_continuation(**{PARAM_CONTINUATION: continuation}))

    assert isinstance(answer, Unknown)
    assert REASON_RESUME_RUN_MISSING in answer.reason
    assert not isinstance(answer, NotApplied)


def test_a_continuation_in_grace_waits_then_is_unknown_if_still_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(
        monkeypatch,
        _document(RunOutcome.NOT_FOUND),
        _document(RunOutcome.NOT_FOUND),
    )
    entry = _continuation()
    entry = replace(entry, issued_at=NOW - timedelta(seconds=10))

    answer = rig.observe(entry)

    assert isinstance(answer, Unknown)
    assert rig.sleeps == [50.0]
    assert len(rig.poll.calls) == 2


def test_a_continuation_with_a_state_is_in_flight_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig = Rig(monkeypatch, _document(RunOutcome.COMPLETED))

    assert isinstance(rig.observe(_continuation()), InFlight)
